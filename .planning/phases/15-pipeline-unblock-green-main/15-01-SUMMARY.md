<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

---
phase: 15-pipeline-unblock-green-main
plan: 01
subsystem: infra
tags: [ci, release, github-actions, ghcr, syft, sbom, cosign, slsa, supply-chain, relx-04, relx-06]

# Dependency graph
requires:
  - phase: 04
    provides: "release.yml publish job (4 perms, by-digest, cosign keyless + SLSA attest)"
  - phase: 08-release-hardening
    provides: "harden-runner audit on all CI/release jobs + every uses: SHA-pinned (RELX-02)"
  - phase: 14-first-real-infra-acceptance
    provides: "release.yml verify-runbook comment + 14-ACCEPTANCE.md Steps E/F cosign/attestation runbook"
provides:
  - "release.yml builds every ghcr.io image ref (metadata images, both SBOMs, cosign sign, SLSA attest subject) from ONE lowercased steps.imgref.outputs.base, so no ref is built from the raw mixed-case github.repository_owner"
  - "Both anchore/sbom-action steps authenticate to ghcr.io via SYFT_REGISTRY_AUTH_* so syft can pull the pushed-by-digest image (fixes the SBOM-step failure that shipped unsigned partial publishes)"
  - "release.yml push trigger narrowed to the semver glob v[0-9]+.[0-9]+.[0-9]+ so hand-pushed two-component milestone tags no longer fire the publish job (release-please owns release tags)"
  - "Lowercased GHCR image paths in the release.yml verify-runbook comment + 14-ACCEPTANCE.md, github.com identity kept canonical-case"
affects: [phase-16-merge-pr3, phase-20-signed-release, RELX-04, RELX-06, ACC-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single lowercased step-output (steps.imgref.outputs.base) as the one source of truth reused across metadata/SBOM/sign/attest"
    - "syft ghcr.io pull auth via SYFT_REGISTRY_AUTH_AUTHORITY/USERNAME/PASSWORD env on each anchore/sbom-action step"
    - "OWNER passed via env (not inline interpolation) so the runner shell does the ${VAR,,} lowercase"

key-files:
  created:
    - .planning/phases/15-pipeline-unblock-green-main/15-01-SUMMARY.md
  modified:
    - .github/workflows/release.yml
    - .planning/milestones/v1.3-phases/14-first-real-infra-acceptance/14-ACCEPTANCE.md

key-decisions:
  - "Chose a dedicated `Compute lowercased GHCR image base` step (id: imgref) over reusing docker/metadata-action outputs, because metadata-action exposes only full tag refs, not a bare ghcr.io/owner/image base. One step feeds all five refs (CONTEXT Claude's-Discretion: cleanest uniform fix)."
  - "OWNER is passed via an env block (not inline ${{ }}) so the shell (${OWNER,,}) does the lowercase, avoiding template-injection in the run: and keeping the raw github.repository_owner literal to exactly one occurrence."
  - "Kept the two github.com identities canonical-case (certificate-identity-regexp + gh attestation --owner): they are GitHub org OIDC identities, not registry paths, and lowercasing them would break verification. Added a case-distinction note to the runbook so an operator does not 'fix' the intended mismatch."
  - "The signed+attested GREEN proof is CI-gated: it needs a live vX.Y.Z tag run (Phase 20). This plan's proof is structural only (YAML parses, no raw-owner ref, syft auth present, SHA-pins intact)."

patterns-established:
  - "Reuse-one-lowercased-base: build every registry ref for an image from a single lowercased step output, never re-interpolate the raw owner per step."

requirements-completed: [RELX-04, RELX-06]

# Metrics
duration: 20min
completed: 2026-07-13
---

# Phase 15 Plan 01: release.yml Owner-Lowercase + syft Auth + Semver Tag Summary

**Every ghcr.io image ref in release.yml now builds from one lowercased steps.imgref.outputs.base, both SBOM steps carry syft registry auth, and the push trigger is the semver glob v[0-9]+.[0-9]+.[0-9]+; SHA-pins, the 4-perm publish block, and egress-policy audit are untouched.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-07-13T17:46:13Z
- **Completed:** 2026-07-13T18:06:00Z (approx)
- **Tasks:** 3
- **Files modified:** 2 (release.yml, 14-ACCEPTANCE.md) + 1 created (this SUMMARY)

## Accomplishments

- Added a `Compute lowercased GHCR image base` step (`id: imgref`) immediately after `Log in to GHCR` and before `Image metadata`: it takes `OWNER`/`IMAGE` via `env:` and appends `base=ghcr.io/${OWNER,,}/${IMAGE}` to `$GITHUB_OUTPUT` (RELX-04).
- Rewired all FIVE previously mixed-case GHCR refs to `${{ steps.imgref.outputs.base }}`: the metadata-action `images:` input, both `anchore/sbom-action` `image:` inputs (trailing `@<digest>` preserved), the `cosign sign` ref (trailing `@<digest>` preserved), and the attest `subject-name:`. The raw `github.repository_owner` literal now appears exactly once (the imgref env).
- Gave BOTH SBOM steps syft registry auth (`SYFT_REGISTRY_AUTH_AUTHORITY: ghcr.io`, `SYFT_REGISTRY_AUTH_USERNAME: ${{ github.actor }}`, `SYFT_REGISTRY_AUTH_PASSWORD: ${{ secrets.GITHUB_TOKEN }}`) so syft can pull the pushed-by-digest image (RELX-04).
- Narrowed `on.push.tags` from `["v*"]` to `["v[0-9]+.[0-9]+.[0-9]+"]` and documented release-please tag ownership in the header comment; left the `release: types: [published]` trigger unchanged (RELX-06).
- Lowercased the ghcr.io image PATHs in the release.yml verify-runbook comment and clarified the ghcr-lowercase / github-canonical distinction in 14-ACCEPTANCE.md; kept the github.com OIDC identity-regexp and `--owner BraveBearStudios` canonical-case.

## Task Commits

Each task was committed atomically (Conventional Commit + DCO sign-off):

1. **Task 1: Lowercase GHCR owner into one reused base + syft registry auth (RELX-04)** - `7f9b3af` (fix)
2. **Task 2: Narrow the push tag trigger to semver (RELX-06)** - `a77234d` (fix)
3. **Task 3: Lowercase the GHCR paths in the runbook comment + 14-ACCEPTANCE.md** - `2fb4232` (docs)

**Plan metadata:** committed with this SUMMARY (docs: complete plan).

## Files Created/Modified

- `.github/workflows/release.yml` - imgref lowercase-base step; 5 refs rewired to the base; syft auth env on both SBOM steps; semver tag glob; header + runbook-comment lowercase sweep. Publish 4-perm block, all SHA-pins, and egress-policy audit byte-unchanged.
- `.planning/milestones/v1.3-phases/14-first-real-infra-acceptance/14-ACCEPTANCE.md` - owner-substitution note + ACC-03 intro state the ghcr.io path uses the lowercase owner while `--owner` / identity-regexp stays canonical-case.
- `.planning/phases/15-pipeline-unblock-green-main/15-01-SUMMARY.md` - this file.

## Verification Results (structural; the `<verify>` one-liners)

All plan `<verify>` one-liners were run and PASS on the dev box (Python 3.13, PyYAML):

- **Task 1:** YAML parses; `github.repository_owner` count = 1 (imgref env only); `steps.imgref.outputs.base` count = 5; `SYFT_REGISTRY_AUTH_PASSWORD` count = 2 and `SYFT_REGISTRY_AUTH_USERNAME` count = 2 (one per SBOM step, no vacuous pass); no `uses:` fails the `@[0-9a-f]{40}` SHA-pin regex; publish permissions == `{contents:read, packages:write, id-token:write, attestations:write}`.
- **Task 2:** `on.push.tags == ['v[0-9]+.[0-9]+.[0-9]+']`; `release.types` still `['published']`.
- **Task 3:** no `ghcr.io/BraveBearStudios` remains; `github.com/BraveBearStudios/burrow` and `--owner BraveBearStudios` still present; `14-ACCEPTANCE.md` contains the lowercase clarification.
- **Consolidated:** 10 `uses:` pins all 40-hex; egress-policy audit unchanged (1 harden-runner step in release.yml); no em/en-dashes introduced in any added line.

## CI-gated / human_needed (deferred to Phase 20)

The signed + attested GREEN proof cannot run from the dev box: it requires a live `vX.Y.Z` tagged `release.yml` run on the GitHub-hosted runner (live GHCR + Sigstore/OIDC). Deferred to Phase 20 (ACC-06), which cuts the first green v1.4.0 signed release and verifies `cosign verify` + `gh attestation verify` against the published `@sha256:` digest, then flips harden-runner audit->block from that run's telemetry. This plan makes NO claim that a green release ran; the in-session proof is structural only.

## Decisions Made

See `key-decisions` in the frontmatter. Load-bearing: a dedicated `imgref` lowercase-output step (not metadata-action output reuse) as the single source of truth for all five refs; OWNER via env so the shell does `${VAR,,}` and the raw-owner literal stays at exactly one occurrence; the two github.com identities stay canonical-case by design.

## Deviations from Plan

None - plan executed exactly as written. One intra-task correction (not a plan deviation): the first draft of the imgref explanatory comment contained the literal string `github.repository_owner`, which inflated the `count('github.repository_owner') <= 1` guard to 2; reworded the comment to "the raw mixed-case owner" so the only occurrence is the imgref env. No behavior change.

## Additive-scope note

Added a short case-distinction NOTE to the release.yml verify-runbook comment (beyond the literal "lowercase the ghcr.io refs" instruction) so an operator does not lowercase the `--owner` / identity-regexp to match the now-lowercase ghcr.io path (which would break `cosign verify` / `gh attestation verify`). Rule 2 (correctness for the operator-facing runbook). Comment-only, no functional change.

## Threat Flags

None. No new security surface. T-15-01 (ref-case desync) is mitigated by the single lowercased base reused across sign/attest; T-15-02 (`GITHUB_TOKEN` -> syft) is the same run-scoped token docker/login-action already uses, scoped to the ghcr.io authority (accept); T-15-03 (trigger glob) is mitigated by the semver narrowing; T-15-SC: no package-manager install and no new `uses:` action, so no Package Legitimacy Audit required.

## Issues Encountered

None beyond the intra-task comment-count correction noted above.

## Next Phase Readiness

- RELX-04 + RELX-06 are structurally landed on `feat/gui-managed-secrets` (part of PR #3). The signed-release path is now correct for the first live tag.
- Phase 15 is not yet complete: 15-02 (Trivy green-main gate, RELX-05) and 15-03 (oss ruleset exclusion, RELX-03, operator-run) remain before PR #3 can merge onto a green main (Phase 16).
- The signed+attested live proof rides to Phase 20 (ACC-06).

## Self-Check: PASSED

- FOUND: .planning/phases/15-pipeline-unblock-green-main/15-01-SUMMARY.md
- FOUND: .github/workflows/release.yml
- FOUND: .planning/milestones/v1.3-phases/14-first-real-infra-acceptance/14-ACCEPTANCE.md
- FOUND commit 7f9b3af (Task 1), a77234d (Task 2), 2fb4232 (Task 3)

*Phase: 15-pipeline-unblock-green-main*
*Completed: 2026-07-13*
