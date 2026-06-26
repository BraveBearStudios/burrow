<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

---
phase: 14-first-real-infra-acceptance
plan: 01
subsystem: infra
tags: [ci, github-actions, actionlint, harden-runner, supply-chain, cosign, sha-pin, acc-02]

# Dependency graph
requires:
  - phase: 08-release-hardening
    provides: "harden-runner audit on all CI/release jobs + every uses: SHA-pinned (RELX-02)"
  - phase: 04
    provides: "release.yml publish job (4 perms, by-digest, cosign keyless + SLSA attest)"
provides:
  - "SHA-pinned fail-fast actionlint static gate in ci.yml static-gates (workflow schema/expression lint, ACC-02 actionlint half, structurally landed)"
  - "Commented harden-runner allowlist-prep block on all 5 CI/release jobs (Fulcio/Rekor/TUF/OIDC/GHCR endpoints + 14-ACCEPTANCE.md flip pointer; egress stays audit)"
affects: [14-02-acceptance-runbook, ACC-02-operator-flip]

# Tech tracking
tech-stack:
  added: ["reviewdog/action-actionlint (actionlint upstream Actions integration), SHA-pinned to v1.72.0"]
  patterns: ["allowlist-prep as inert YAML comments below egress-policy: audit (no functional egress change until the operator flips to block)"]

key-files:
  created:
    - .planning/phases/14-first-real-infra-acceptance/14-01-SUMMARY.md
  modified:
    - .github/workflows/ci.yml
    - .github/workflows/release.yml
    - .github/workflows/release-please.yml

key-decisions:
  - "Plan named rhysd/actionlint as the action to pin; rhysd/actionlint ships NO action.yml (it is the CLI binary repo), so a bare uses: rhysd/actionlint@<sha> would fail at runtime. Substituted reviewdog/action-actionlint (actionlint's own README-documented GitHub Actions integration), SHA-pinned to a 40-hex git commit per repo convention. Rule 3 (named action non-existent, blocking)."
  - "Made the actionlint gate fail-fast and non-advisory: reporter github-check (works on push AND PR, unlike the default github-pr-check) + fail_level error (the action defaults to fail_level none = always exit 0)."
  - "actionlint RUN is intentionally deferred to the first live Linux runner. actionlint is not installable on the Windows dev box (Phase 8 RELX-02), so the local proof is STRUCTURAL only: workflows parse, the step is present + SHA-pinned, SPDX clean. This is NOT a claim that actionlint passed locally."
  - "All 5 harden-runner egress-policy values stay audit (no block flip). The allowlist is added as inert YAML comments so the policy is unchanged; the operator discovers the real allowlist from the first live audit run and flips to block per 14-ACCEPTANCE.md."

patterns-established:
  - "Allowlist-prep comment block: a commented allowed-endpoints list (host:443) directly below egress-policy: audit, ending in a one-line pointer to the audit->block flip runbook."

requirements-completed: [ACC-02]

# Metrics
duration: 18min
completed: 2026-06-26
---

# Phase 14 Plan 01: CI Hardening (ACC-02 automatable slice) Summary

**SHA-pinned fail-fast actionlint static gate added to ci.yml plus inert Fulcio/Rekor/TUF/OIDC/GHCR allowlist-prep comments on all 5 harden-runner steps; egress stays audit, publish path untouched.**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-06-26T09:07:00Z (approx)
- **Completed:** 2026-06-26T09:25:00Z
- **Tasks:** 3
- **Files modified:** 3 (ci.yml, release.yml, release-please.yml)

## Accomplishments

- Wired a SHA-pinned, fail-fast `actionlint` step into `ci.yml`'s `static-gates` job, positioned after `Checkout` and before `Install uv` so a GitHub Actions workflow schema/expression error fails the build before the slower uv/npm install gates.
- Added a commented `allowed-endpoints` allowlist-prep block below each of the 5 `egress-policy: audit` lines (ci.yml static-gates/pr-title/build-scan, release.yml publish, release-please.yml), listing the cosign/OIDC/GHCR endpoints the audit->block flip will need, each pointing to the `14-ACCEPTANCE.md` flip procedure.
- Verified structurally: all 3 workflows `yaml.safe_load`; every `uses:` (including the new actionlint) is a full 40-hex SHA; `reuse lint` is REUSE-3.3 compliant (428/428 files); the release.yml publish path (4 perms, by-digest, cosign keyless + SLSA attest) is byte-unchanged (0 lines removed).

## Task Commits

Each task was committed atomically:

1. **Task 1: Add SHA-pinned actionlint step to ci.yml static-gates** - `89b2eba` (ci)
2. **Task 2: Add harden-runner allowlist-prep comments to all five jobs** - `de088aa` (ci)
3. **Task 3: SHA-pin + parse + SPDX structural sweep** - verification-only (no source edit; proof recorded here)

**Plan metadata:** committed with this SUMMARY (docs: complete plan)

## Files Created/Modified

- `.github/workflows/ci.yml` - actionlint static-gate step (SHA-pinned, fail-fast) + allowlist-prep comments on all 3 harden-runner steps.
- `.github/workflows/release.yml` - allowlist-prep comment on the publish harden-runner step (notes Fulcio/Rekor/TUF are keyless-signing-critical); publish steps + 4-perm block byte-unchanged.
- `.github/workflows/release-please.yml` - allowlist-prep comment on the release-please harden-runner step.

## actionlint action chosen + pinned SHA

- **Action:** `reviewdog/action-actionlint@6fb7acc99f4a1008869fa8a0f09cfca740837d9d # v1.72.0`
- **Why not `rhysd/actionlint@<sha>` as the plan literally specified:** `rhysd/actionlint` is the actionlint CLI binary repository and ships NO `action.yml`/`action.yaml` (verified via the GitHub API at the resolved v1.7.12 commit `914e7df21a07ef503a81201c76d2b11c789d3fca`), so `uses: rhysd/actionlint@<sha>` would fail at runtime with "action.yml not found". `reviewdog/action-actionlint` is actionlint's own upstream-README-documented GitHub Actions integration, runs the same actionlint binary, has a valid `action.yml`, and is pinnable to a 40-hex git commit SHA per the repo's SHA-pin convention (matches the plan's `actionlint@[0-9a-f]{40}` verify regex and the `# vX.Y.Z` comment style).
- **Configured fail-fast:** `reporter: github-check` (works on push and PR; the action's default `github-pr-check` only annotates on PRs) + `fail_level: error` (the action defaults to `fail_level: none` = always exit 0, which would make it advisory, not a gate).

## Allowlist endpoints seeded (all 5 jobs, commented)

`fulcio.sigstore.dev`, `rekor.sigstore.dev`, `tuf.sigstore.dev`, `token.actions.githubusercontent.com`, `ghcr.io`, `github.com`, `objects.githubusercontent.com` (each with `:443`). Egress-policy stays `audit` on all 5 steps; the block flip with the operator-discovered real allowlist is the deferred ACC-02 on-runner step, documented in `14-ACCEPTANCE.md` (authored in plan 14-02).

## actionlint proof contract (structural-local + live-CI)

The actionlint lint RUN is intentionally deferred to the first live GitHub Linux runner. actionlint is not installable on the Windows dev box (Phase 8 RELX-02). The local proof is STRUCTURAL only and was satisfied:

- All 3 workflows `yaml.safe_load` cleanly.
- The actionlint step is present in `static-gates`, named `actionlint - workflow schema/expression lint`, SHA-pinned (`actionlint@[0-9a-f]{40}` matches), positioned after `Checkout` (index 1) and before `Install uv` (index 3).
- Every `uses:` across all 3 workflows is a full 40-hex SHA.
- `uvx --with charset-normalizer reuse lint` reports the repo REUSE-3.3 compliant (428/428).

This is NOT a claim that actionlint passed locally; live CI is the real proof.

## Decisions Made

See `key-decisions` in the frontmatter. The load-bearing one: substituting `reviewdog/action-actionlint` for the plan's non-existent `rhysd/actionlint` action, configured to be a real fail-fast gate.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Plan-named actionlint action `rhysd/actionlint` does not exist as a GitHub Action**
- **Found during:** Task 1 (resolving the actionlint SHA)
- **Issue:** The plan instructed `uses: rhysd/actionlint@<40-hex-sha>`. The GitHub API shows `rhysd/actionlint` is the CLI binary repo with no `action.yml`/`action.yaml` at the latest release commit (v1.7.12 / `914e7df...`); a `uses: rhysd/actionlint@<sha>` step would fail at runtime. The plan's literal instruction was unimplementable.
- **Fix:** Used `reviewdog/action-actionlint@6fb7acc99f4a1008869fa8a0f09cfca740837d9d # v1.72.0` (actionlint's upstream-documented Actions integration; runs the same binary; has a valid `action.yml`; pinnable to a 40-hex git SHA per repo convention). Configured `reporter: github-check` + `fail_level: error` to make it a fail-fast gate on push and PR.
- **Files modified:** `.github/workflows/ci.yml`
- **Verification:** action.yml confirmed present at the pinned commit; `uses:` matches `actionlint@[0-9a-f]{40}`; workflow parses; step positioned after Checkout, before Install uv.
- **Committed in:** `89b2eba` (Task 1 commit)

**2. [Rule 1 - Verification bug] Plan's Task 2 verify script false-positives on a pre-existing comment**
- **Found during:** Task 2
- **Issue:** The plan's Task 2 `<automated>` check asserts `'egress-policy: block' not in t`. release-please.yml has a PRE-EXISTING top-of-file narrative comment (line 13, from Phase 8) reading "flipping to egress-policy: block is the deferred ACC-02 on-runner step", which is documentation prose, not a policy setting. The naive substring check fails on it even though no harden-runner step is set to block.
- **Fix:** Verified Task 2 structurally instead: parsed each workflow and walked every harden-runner step's `with.egress-policy` value, asserting all 5 are `audit`. This is the correct, equivalent check (the requirement is "no harden-runner step is set to block," not "the string never appears in a comment"). No file change was needed; the pre-existing comment is out of scope and left untouched.
- **Files modified:** none (verification method only)
- **Verification:** 5 harden-runner steps, all `egress-policy: audit` (structural YAML walk).
- **Committed in:** n/a (verification approach, not a code change)

---

**Total deviations:** 2 (1 Rule 3 blocking action substitution, 1 Rule 1 verify-script false-positive worked around structurally)
**Impact on plan:** Both necessary for a working, correct result. The actionlint substitution is the only way to land a SHA-pinned fail-fast actionlint gate (the named action does not exist); the egress check was re-expressed structurally to match the real requirement. No scope creep: still 3 files, comment + one-step additions only, publish path and all existing SHA pins byte-unchanged.

## Issues Encountered

- `uvx ... reuse lint-file` did not return output on the dev box; the repo-standard `uvx --with charset-normalizer reuse lint` (full-tree, the exact ci.yml gate) was used instead and reports compliant.

## User Setup Required

None for this plan. The operator-run ACC-02 steps (flip harden-runner egress audit->block with the discovered allowlist; confirm actionlint passes on the live runner) are deferred to the live runner and documented in `14-ACCEPTANCE.md` (plan 14-02).

## Threat Flags

None. No new security surface: the only new third-party action (`reviewdog/action-actionlint`) is SHA-pinned to a 40-hex commit (T-14-01 mitigation holds); egress stays audit (T-14-02); no permission change (T-14-03); no package-manager install (T-14-SC).

## Next Phase Readiness

- The automatable CI-hardening half of ACC-02 is structurally landed; live CI proves the actionlint RUN.
- Ready for plan 14-02 (acceptance runbook + consolidated UAT). The allowlist-prep comments reference `14-ACCEPTANCE.md`, which 14-02 authors.
- Phase 14 verification remains `human_needed` by design (ACC-01/02/03 are real-infra / live-release; not CI-provable).

## Self-Check: PASSED

- FOUND: .planning/phases/14-first-real-infra-acceptance/14-01-SUMMARY.md
- FOUND: .github/workflows/ci.yml, release.yml, release-please.yml
- FOUND commit 89b2eba (Task 1), de088aa (Task 2)

---
*Phase: 14-first-real-infra-acceptance*
*Completed: 2026-06-26*
