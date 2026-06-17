---
phase: 08-release-hardening-release-please-harden-runner
reviewed: 2026-06-15T00:00:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - .github/workflows/ci.yml
  - .github/workflows/release-please.yml
  - .github/workflows/release.yml
  - .release-please-manifest.json
  - CONTRIBUTING.md
  - REUSE.toml
  - release-please-config.json
findings:
  critical: 0
  warning: 2
  info: 2
  total: 4
status: issues_found
---

# Phase 8: Code Review Report

**Reviewed:** 2026-06-15T00:00:00Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Reviewed the Phase 8 release-hardening surface: three GitHub Actions workflows
(`ci.yml`, `release-please.yml`, `release.yml`), the release-please config +
manifest, `REUSE.toml`, and `CONTRIBUTING.md`. This is CI-config + docs only,
no application code.

The supply-chain hardening is solid and verifiable. I independently confirmed:

- **All 24 `uses:` references are SHA-pinned to full 40-hex commit SHAs** (15
  distinct SHAs, each exactly 40 hex chars). No floating `@v5` / `@main` /
  `@latest` tags remain. The PR-title gate is correctly repinned off the moving
  `@v5` tag to `0723387…` (v5.5.3).
- **`harden-runner` is step 0 of all 5 jobs** (ci: static-gates / pr-title /
  build-scan; release: publish; release-please: release-please), all in
  `egress-policy: audit` (by design — block flip is deferred ACC-02, not a bug).
- **`bootstrap-sha` `9bccec85…` is the v1.1 *commit*, not the tag object.**
  Verified: `git rev-list -n1 v1.1` == `9bccec85…`, and `git cat-file -t` on it
  returns `commit`. This matches the design intent exactly.
- **Manifest seed `1.1.0`** will make the first release PR propose `v1.2.0`
  (intentional — v1.2 is not yet tagged).
- **JSON configs parse** (both `release-please-config.json` and the manifest).
- **Secret hygiene clean:** no literal tokens, hostnames, VMIDs, or node names;
  only `${{ secrets.GITHUB_TOKEN }}` / `github.*` contexts are used. No PAT.
- **Permissions are least-privilege** on every job (root default `contents:read`;
  jobs add exactly the scopes they need and nothing broader).
- **REUSE.toml** licenses both comment-less JSON configs (`release-please-config.json`
  and `.release-please-manifest.json`) and all three YAML workflows carry the
  two-line SPDX header.
- All CI-referenced paths resolve on disk (`Dockerfile.api`, `Dockerfile.ui`,
  both boot scripts, all 5 pytest targets).

No blockers. Two warnings and two info items below — none of them contradict the
locked design decisions; they flag a release-please behavioral surprise, a
permission edge for SARIF upload, and two minor consistency notes.

## Warnings

### WR-01: `simple` release-type will create an unexpected `version.txt` at repo root

**File:** `release-please-config.json:3`
**Issue:** `"release-type": "simple"` uses release-please's *Generic* updater,
whose default version-tracking file is `version.txt` at the package root (`.`).
No `version.txt` exists in the repo today (verified: `ls version.txt` → not
found), and the config declares no `extra-files` / `version-file` override. On
the first release PR, release-please will *add* a new `version.txt` containing
the bumped version. The version source of truth is intended to be
`.release-please-manifest.json`, so a freshly-materialized `version.txt` is a
behavioral surprise that may confuse maintainers and adds a second place the
version string lives (DRY drift between `version.txt` and the manifest).

This is additive and will not break the release chain, hence WARNING not
BLOCKER — but it is unexpected and undocumented in `CONTRIBUTING.md`'s release
section.
**Fix:** Decide explicitly. Either (a) document that `simple` materializes a
root `version.txt` and accept it, or (b) if no on-disk version file is wanted,
switch the package to track only the manifest by pointing the version file at a
file you control, e.g.:
```json
"packages": {
  ".": {
    "release-type": "simple",
    "version-file": "version.txt"
  }
}
```
and add a `version.txt` seeded to `1.1.0` so the first PR *updates* (not
silently creates) a tracked file, keeping the change reviewable. Confirm the
intended behavior on the first live release.

### WR-02: `build-scan` SARIF upload may fail on private/internal repos without `actions: read`

**File:** `ci.yml:141-143, 194-199`
**Issue:** The `build-scan` job grants `security-events: write` for
`github/codeql-action/upload-sarif`, which is correct for the upload itself.
However, on **private or internal** repositories the CodeQL `upload-sarif`
action also reads workflow/run metadata and can require `actions: read` to
resolve the analysis context; without it the upload step can fail with a
permissions error. On public repos this is implicitly granted, so it will pass
today if the repo is public — but the repo's stated posture (`CLAUDE.md`:
"Never make a repo public unless explicitly instructed") means it is likely
private, where the missing scope bites.
**Fix:** Add the read scope to the `build-scan` job permissions block so the
upload works regardless of repo visibility:
```yaml
    permissions:
      contents: read
      security-events: write # github/codeql-action/upload-sarif
      actions: read          # upload-sarif run/workflow metadata (private repos)
```

## Info

### IN-01: New 3-component tags diverge from existing 2-component tags (`v1.0`, `v1.1`)

**File:** `release.yml:86-90`, existing tags `v1.0` / `v1.1`
**Issue:** Existing git tags are 2-component (`v1.0`, `v1.1`), but `simple` +
`include-v-in-tag: true` + manifest `1.1.0` will produce a **3-component**
semver tag (`v1.2.0`) on the first release. `docker/metadata-action`'s
`type=semver` patterns require valid semver and will work for `v1.2.0`, but the
old `v1.1` tag is not valid semver — if `release.yml` is ever manually re-run on
the legacy `v1.1` tag (e.g. to test the publish path), `type=semver` will
silently emit no semver tags. This is a forward-only concern, not a defect in
the new path.
**Fix:** No code change required. Optionally note in `CONTRIBUTING.md` that the
canonical tag format going forward is 3-component `vX.Y.Z` and that the legacy
2-component tags are not re-publishable via the semver metadata path.

### IN-02: REUSE.toml lists `.planning/config.json` individually and via glob

**File:** `REUSE.toml:23` and `REUSE.toml:56-58`
**Issue:** `.planning/config.json` is annotated both explicitly in the
comment-less-JSON block (line 23) and again by the `.planning/**/*.json` glob in
the GSD-planning block (lines 56-58). With `precedence = "aggregate"` this is
harmless (no conflict), but the explicit line is redundant now that the planning
tree is globbed wholesale, and redundant entries drift over time.
**Fix:** Remove `.planning/config.json` from the comment-less-JSON `path` array
(line 23); the `.planning/**/*.json` glob already covers it. Leave the genuine
source-config entries (`ui/*.json`, `cc-worker-config/plugins/*.json`,
`release-please-config.json`, `.release-please-manifest.json`) in place.

---

_Reviewed: 2026-06-15T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
