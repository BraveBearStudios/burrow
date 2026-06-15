<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
# Phase 8: Release Hardening (release-please + harden-runner) - Pattern Map

**Mapped:** 2026-06-15
**Files analyzed:** 7 (2 new workflow/config-adjacent, 2 new root JSON, 3 modified existing)
**Analogs found:** 7 / 7 (every new/modified file has an in-repo analog)

This is a CI-config + docs phase. There is no application code surface. Every "pattern" below is an existing structure in `.github/workflows/`, `REUSE.toml`, or `CONTRIBUTING.md` that the executor must mirror verbatim (SHA-pin convention, permissions defaults, SPDX header style, annotation-block shape). The action SHAs and bootstrap anchor are fixed by RESEARCH.md and re-verified against the live repo (`git for-each-ref` confirms `v1.1` = `f900a95556d4d82498008a126f3a2cf507e5f3c1`).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `.github/workflows/release-please.yml` | new workflow (CI) | event-driven (push:main → action) | `.github/workflows/release.yml` (single-job, SHA-pinned, contents-default workflow) | role + flow exact |
| `release-please-config.json` | new config (root, comment-less JSON) | config (read by action) | existing comment-less JSON paths in `REUSE.toml` block (e.g. `ui/biome.json`, `manifest.schema.json`) | role match (no inline-header JSON config is the precedent) |
| `.release-please-manifest.json` | new config (root, comment-less JSON) | config (read by action) | same comment-less JSON precedent | role match |
| `.github/workflows/ci.yml` | workflow edit | event-driven (insert step 0 in 3 jobs + repin SHA) | self — existing `static-gates` / `build-scan` step structure | self-analog (in-file pattern) |
| `.github/workflows/release.yml` | workflow edit | event-driven (insert step 0 in publish job) | self — existing `publish` job step structure | self-analog (in-file pattern) |
| `REUSE.toml` | license edit | transform (extend annotation `path` array) | self — existing comment-less-JSON `[[annotations]]` block (lines 21-32) | self-analog (in-file pattern) |
| `CONTRIBUTING.md` | docs edit | transform (append a section) | self — existing `## SPDX headers` / `## Submitting changes` sections | self-analog (in-file pattern) |

## Shared Patterns

These cross-cutting conventions apply to multiple files. The executor copies these into every relevant file rather than inventing per-file style.

### Shared Pattern A — SHA-pin convention (`@<40-hex> # vX.Y.Z`)

**Source:** `.github/workflows/ci.yml` lines 29-36, `.github/workflows/release.yml` lines 58-68
**Apply to:** every `uses:` line in `release-please.yml`, and every inserted/repinned `uses:` in `ci.yml` and `release.yml`.

Every third-party action is pinned to a full 40-char commit SHA with a trailing comment recording the human-readable version. Existing exemplars to copy the exact shape from:
```yaml
        uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4.3.1
        uses: astral-sh/setup-uv@d0cc045d04ccac9d8b7881df0226f9e82c39688e # v6.8.0
        uses: docker/setup-buildx-action@d7f5e7f509e45cec5c76c4d5afdd7de93d0b3df5 # v4.1.0
```
**Defect this phase fixes (the lone violation):** `ci.yml` line 116 carries `# v5` (a one-number major tag = a moving-tag smell per the convention). RESEARCH.md flags this as the `# TODO pin exact SHA` placeholder. The trailing comment MUST become `# v5.5.3` (three-part), honest to the immutable SHA.

The three action SHAs this phase introduces or repins (verified upstream via `git ls-remote`, RESEARCH.md Package Legitimacy Audit):
| Action | SHA | Trailing comment |
|--------|-----|------------------|
| `step-security/harden-runner` | `9af89fc71515a100421586dfdb3dc9c984fbf411` | `# v2.19.4` |
| `googleapis/release-please-action` | `5c625bfb5d1ff62eadeeb3772007f7f66fdcf071` | `# v4.4.1` |
| `amannn/action-semantic-pull-request` | `0723387faaf9b38adef4775cd42cfd5155ed6017` | `# v5.5.3` (replaces the moving `e32d7e60… # v5`) |

### Shared Pattern B — least-privilege permissions (`contents: read` default, per-job elevation)

**Source:** `.github/workflows/ci.yml` lines 19-20 (workflow default) + lines 26-27 / 112-113 / 131-133 (per-job blocks); `.github/workflows/release.yml` lines 30-31 (default) + lines 44-48 (the four-scope publish elevation)
**Apply to:** the new `release-please.yml` (workflow default `contents: read`; the `release-please` job elevates to exactly `contents: write` + `pull-requests: write`, nothing broader).

Existing default to mirror verbatim:
```yaml
permissions:
  contents: read
```
Existing per-job elevation precedent (release.yml lines 37-48 — note the inline comment documenting WHY each scope exists; copy this self-documenting style):
```yaml
    # EXACTLY these four — nothing broader (Pitfall 7 / ci-cd §5.5):
    #   contents:     read   — checkout the tagged source
    #   packages:     write  — push the image AND the provenance/SBOM to GHCR
    #   id-token:     write  — OIDC for cosign keyless + attest-build-provenance
    #   attestations: write  — actions/attest-build-provenance writes the attestation
    permissions:
      contents: read
      packages: write
      id-token: write
      attestations: write
```
For `release-please.yml` the job elevation is `contents: write` + `pull-requests: write` (NOT `issues: write` — omit it to stay least-privilege; RESEARCH.md Pitfall 4).

### Shared Pattern C — SPDX header style per file type

**Source:** `CONTRIBUTING.md` lines 59-79 (the canonical per-language header table); `ci.yml`/`release.yml` lines 1-2 (YAML `#` header in practice); `REUSE.toml` lines 1-2.
**Apply to:** `release-please.yml` (YAML `#` two-line header on lines 1-2). The two root JSON files take NO inline header (JSON has no comment syntax) and are covered by `REUSE.toml` instead (Shared Pattern D).

YAML header to copy verbatim as lines 1-2 of `release-please.yml`:
```yaml
# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
```

### Shared Pattern D — comment-less JSON licensed via REUSE.toml, never an inline header

**Source:** `REUSE.toml` lines 20-32 (the "Comment-less JSON config" `[[annotations]]` block)
**Apply to:** both `release-please-config.json` and `.release-please-manifest.json`.

Do NOT add `// SPDX` to the JSON (invalid JSON) and do NOT blanket-glob `*.json` (CICD-06 requires a missing inline header on a real source to still surface). Add the two explicit paths to the existing block (see Pattern Assignment for `REUSE.toml`).

### Shared Pattern E — inline "WHY" comment blocks at the top of workflows / above non-obvious steps

**Source:** `ci.yml` lines 3-10 (file-purpose header), lines 49-66 (multi-line `#` rationale above gate steps), lines 92-98 (shellcheck rationale); `release.yml` lines 3-20 + the per-step comments throughout.
**Apply to:** the `release-please.yml` file header and the harden-runner audit comment, and the CONTRIBUTING release section. Style rules from CLAUDE.md (user-global): no em dashes, no horizontal rules in authored prose; use the repo's existing `# ── label ──` divider style seen in `ci.yml` line 40 and `REUSE.toml` line 13 if a divider is wanted.

## Pattern Assignments

### `.github/workflows/release-please.yml` (new workflow, event-driven)

**Analog:** `.github/workflows/release.yml` (the closest existing single-purpose, SHA-pinned, `contents:read`-default workflow). Copy its skeleton (SPDX header → file rationale comment → `name:` → `on:` → workflow `permissions:` → `jobs:` with a per-job `permissions:` elevation → SHA-pinned steps).

**Imports / header pattern** (mirror `release.yml` lines 1-31 structure):
- Lines 1-2: SPDX YAML header (Shared Pattern C).
- A `#` rationale block describing the tag-based chain (release-please tags `v*` → existing `release.yml` publish fires) and the audit-mode harden-runner note (Shared Pattern E). RESEARCH.md Code Examples §`release-please.yml` lines 326-338 give the exact wording to adapt.
- `name: release-please`
- `on: push: branches: [main]`
- Workflow default `permissions: { contents: read }` (Shared Pattern B).

**Core pattern — single job, harden-runner as step 0, then the action** (RESEARCH.md Code Examples lines 349-369). The job-level `permissions` elevation and the two SHA-pinned steps:
```yaml
jobs:
  release-please:
    name: Maintain release PR
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write
    steps:
      - name: Harden the runner (audit egress)
        uses: step-security/harden-runner@9af89fc71515a100421586dfdb3dc9c984fbf411 # v2.19.4
        with:
          egress-policy: audit

      - name: Run release-please
        uses: googleapis/release-please-action@5c625bfb5d1ff62eadeeb3772007f7f66fdcf071 # v4.4.1
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          config-file: release-please-config.json
          manifest-file: .release-please-manifest.json
```

**Token pattern:** use `${{ secrets.GITHUB_TOKEN }}` — same built-in-token, no-PAT pattern as `release.yml` line 72 (`password: ${{ secrets.GITHUB_TOKEN }}`). No new repo secret (CLAUDE.md: never commit secrets; RESEARCH.md A5).

---

### `release-please-config.json` (new root config, comment-less JSON)

**Analog:** no exact JSON-content analog exists in-repo (release-please config is new to the tree). Closest precedent is the *licensing treatment* of other comment-less JSON config (`REUSE.toml` block, Shared Pattern D) and the locked field shape from RESEARCH.md Code Examples lines 296-308. The planner uses the RESEARCH.md content directly — it is the authority for the field set.

**Content the executor writes** (pure JSON, no comments in the real file):
```json
{
  "$schema": "https://raw.githubusercontent.com/googleapis/release-please/main/schemas/config.json",
  "release-type": "simple",
  "include-v-in-tag": true,
  "bootstrap-sha": "f900a95556d4d82498008a126f3a2cf507e5f3c1",
  "packages": {
    ".": {}
  }
}
```
**Anchors (re-verified against the live repo):**
- `bootstrap-sha` = the `v1.1` tag commit `f900a95556d4d82498008a126f3a2cf507e5f3c1` (confirmed via `git for-each-ref refs/tags`). Starts the first changelog after v1.1; ignored after the first release PR.
- `release-type: simple` + single package `"."` = the locked single-root release (no per-package api/ui versions).
- `include-v-in-tag: true` makes the cut tag `v1.2.0`, matching `release.yml` line 26 `tags: ["v*"]` — no edit to that trigger.
- Default changelog sections are achieved by OMITTING a `changelog-sections` override (locked decision is "defaults": feat→Features, fix→Bug Fixes, docs/chore hidden).
- **License:** no inline header; register in `REUSE.toml` (Shared Pattern D).

**Open decision the planner must resolve before merge:** RESEARCH.md A3 — the manifest seed (`1.2.0` vs `1.1.0`). This is a manifest-file value, not a config-file value; see next file.

---

### `.release-please-manifest.json` (new root config, comment-less JSON)

**Analog:** same comment-less-JSON licensing precedent (Shared Pattern D). Content from RESEARCH.md Code Examples lines 316-322.

**Content the executor writes** (pure JSON):
```json
{
  ".": "1.2.0"
}
```
- Single key `"."` = root package path; value = the current released version the next bump starts from.
- Seed value `1.2.0` is the RESEARCH.md recommendation (continue from the already-merged v1.2 baseline). RESEARCH.md A3 / Open Question 2 flags this as a product decision to confirm before the first real merge; the file is trivially editable.
- **License:** no inline header; register in `REUSE.toml` (Shared Pattern D).

---

### `.github/workflows/ci.yml` (workflow edit — 2 distinct changes)

**Analog:** the file itself. Both changes mirror in-file structure; do not introduce new style.

**Change 1 — insert harden-runner as step 0 of all three jobs** (`static-gates`, `pr-title`, `build-scan`). The identical block below goes BEFORE the current first step of each job (before `Checkout` in `static-gates` line 29 and `build-scan` line 143; before `Validate PR title` in `pr-title` line 115, where it becomes the new step 0):
```yaml
      - name: Harden the runner (audit egress)
        uses: step-security/harden-runner@9af89fc71515a100421586dfdb3dc9c984fbf411 # v2.19.4
        with:
          egress-policy: audit
```
harden-runner MUST be literally first (before `actions/checkout`) so it observes all subsequent egress (RESEARCH.md Pattern 2 / anti-pattern "harden-runner not first").

**Change 2 — repin the PR-title gate off the moving `v5` tag** (the lone SHA-pin defect). One-line edit at line 116:
```yaml
# BEFORE (moving v5 major tag — the placeholder / "# TODO pin exact SHA"):
        uses: amannn/action-semantic-pull-request@e32d7e603df1aa1ba07e981f2a23455dee596825 # v5
# AFTER (immutable v5.5.3 release SHA — honest trailing comment):
        uses: amannn/action-semantic-pull-request@0723387faaf9b38adef4775cd42cfd5155ed6017 # v5.5.3
```

**Unchanged:** the workflow `on:` trigger (lines 14-17), the `contents: read` default (lines 19-20), every existing gate step, every other SHA pin. Scope discipline — touch only step-0 insertions and line 116.

---

### `.github/workflows/release.yml` (workflow edit — 1 change)

**Analog:** the file itself.

**Change — insert harden-runner as step 0 of the `publish` job**, BEFORE the current first step (`Checkout`, line 58):
```yaml
      - name: Harden the runner (audit egress)
        uses: step-security/harden-runner@9af89fc71515a100421586dfdb3dc9c984fbf411 # v2.19.4
        with:
          egress-policy: audit
```
**Unchanged (locked):** the `on:` trigger (lines 24-28 — the tag-based chain; editing it reintroduces the collision the locked decision avoids), the four-scope `permissions` block (lines 44-48), every existing publish/SBOM/sign/attest step, every SHA pin. RESEARCH.md Pitfall 5 note: in audit mode nothing breaks; `build-scan` and `publish` have the widest latent egress (Docker/Trivy/GHCR), relevant only at the deferred block-flip (ACC-02).

---

### `REUSE.toml` (license edit — extend one array)

**Analog:** the file itself — the existing "Comment-less JSON config" `[[annotations]]` block at lines 20-32.

**Change — append the two new paths to the existing `path` array** (lines 22-29). Mirror the existing entry style exactly (quoted, comma-terminated, one per line). Do NOT create a new `[[annotations]]` block:
```toml
# ── Comment-less JSON config (JSON has no comment syntax) ───────────────
[[annotations]]
path = [
  ".planning/config.json",
  "ui/package.json",
  "ui/tsconfig.json",
  "ui/biome.json",
  "cc-worker-config/plugins/manifest.json",
  "cc-worker-config/plugins/manifest.schema.json",
  "release-please-config.json",
  ".release-please-manifest.json",
]
precedence = "aggregate"
SPDX-FileCopyrightText = "2026 Brave Bear Studios"
SPDX-License-Identifier = "AGPL-3.0-or-later"
```
The `precedence` / `SPDX-FileCopyrightText` / `SPDX-License-Identifier` lines (30-32) are unchanged — the two new files inherit the same Brave Bear Studios / AGPL-3.0-or-later annotation.

---

### `CONTRIBUTING.md` (docs edit — append a section)

**Analog:** the file itself — existing `## SPDX headers` (lines 58-84) and `## Submitting changes` (lines 86-98) sections set the heading depth (`##`), prose voice, and fenced-block style. The new "Release process" section follows the same shape.

**Change — add a new `## Release process` (and runner hardening) section.** Place it after `## Submitting changes` (after line 98) so it sits with the contribution-mechanics sections, before `## Architecture decisions`. RESEARCH.md Code Examples lines 404-405 specify the content; it must cover:
- (a) merges to `main` open an automated release PR via release-please; merging it tags `v*` and triggers the GHCR publish (`release.yml`).
- (b) the PR-title gate (already documented at line 97-98) is what makes release-please work under squash-merge — link the two.
- (c) CI runs under harden-runner in **audit** mode today; the discovered egress allowlist + the flip to `block` is the first on-runner acceptance (ACC-02).
- (d) the `GITHUB_TOKEN`-may-not-retrigger caveat (RESEARCH.md Open Question 1) so the first releaser knows to verify `release.yml` auto-fires on the release-please tag.

**Style constraints (CLAUDE.md user-global, enforced on this prose):** no em dashes, no horizontal rules. Use the existing CONTRIBUTING bold/inline-code/bullet style. The SPDX HTML header at lines 1-4 stays on line 1 (do not move it).

## No Analog Found

None. Every file has either an exact in-repo analog (the existing workflows for `release-please.yml`), a self-analog (the in-file structure for the four MODIFY targets), or an established licensing/style precedent (the comment-less-JSON `REUSE.toml` block for the two new root JSON files). The JSON *content* is supplied by RESEARCH.md Code Examples (the locked field shape), not invented.

## Metadata

**Analog search scope:** `.github/workflows/` (ci.yml, release.yml), repo root (`REUSE.toml`, `CONTRIBUTING.md`), and a glob for any pre-existing `release-please*.json` (none found — both NEW confirmed).
**Files scanned (read in full):** `08-CONTEXT.md`, `08-RESEARCH.md`, `.github/workflows/ci.yml` (185 lines), `.github/workflows/release.yml` (160 lines), `REUSE.toml` (62 lines), `CONTRIBUTING.md` (110 lines).
**Live-repo verification:** `git for-each-ref refs/tags` → `v1.1` = `f900a95556d4d82498008a126f3a2cf507e5f3c1` (bootstrap-sha anchor confirmed); `release-please*.json` glob empty (both config files are genuinely new).
**Pattern extraction date:** 2026-06-15
