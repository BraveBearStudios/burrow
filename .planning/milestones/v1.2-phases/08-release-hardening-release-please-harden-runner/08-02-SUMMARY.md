<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

---
phase: 08-release-hardening-release-please-harden-runner
plan: 02
subsystem: infra
tags: [harden-runner, github-actions, ci, supply-chain, sha-pin, docs, reuse]

# Dependency graph
requires:
  - phase: 08-release-hardening-release-please-harden-runner
    plan: 01
    provides: "live-verified action SHAs (harden-runner v2.19.4 = 9af89fc, amannn v5.5.3 = 0723387) re-asserted here"
  - phase: 04-release-supply-chain
    provides: "release.yml publish job (the runner this plan hardens with step-0 harden-runner)"
provides:
  - "ci.yml: harden-runner (audit) step 0 on all three jobs (static-gates, pr-title, build-scan) + amannn PR-title gate repinned to the immutable v5.5.3 SHA"
  - "release.yml: harden-runner (audit) step 0 on the publish job"
  - "CONTRIBUTING.md: Release process & runner hardening section (release-please chain, squash-merge PR-title linkage, audit-then-block policy, GITHUB_TOKEN-retrigger caveat)"
  - "cross-workflow invariant: every uses: across all three workflows is a 40-hex SHA, no floating @vN tag remains"
affects: [release, ci]

# Tech tracking
tech-stack:
  added:
    - "step-security/harden-runner@9af89fc (v2.19.4) — runner egress monitoring (audit) on ci.yml + release.yml jobs"
  patterns:
    - "harden-runner as the literal step 0 of every job (before actions/checkout) so it observes all egress"
    - "Every third-party action pinned to an immutable 40-hex commit SHA; the trailing # vX.Y.Z is documentation only"
    - "audit-then-block: audit ships now; the allowlist + egress-policy block flip is the deferred ACC-02 on-runner step"

key-files:
  created: []
  modified:
    - ".github/workflows/ci.yml"
    - ".github/workflows/release.yml"
    - "CONTRIBUTING.md"

key-decisions:
  - "Re-asserted the harden-runner v2.19.4 (9af89fc71515a100421586dfdb3dc9c984fbf411) and amannn v5.5.3 (0723387faaf9b38adef4775cd42cfd5155ed6017) SHAs against Plan 08-01's live-verified record before writing them — no drift; research hints were not trusted directly"
  - "harden-runner is the FIRST step in each of the four jobs (before actions/checkout) so it observes all subsequent egress; placing it after a network step is the anti-pattern this avoids"
  - "Only the amannn PR-title gate (the one live moving-tag defect on @v5) was repinned; every other pre-existing pin (checkout, setup-uv, setup-node, buildx, build-push, Trivy, codeql, login, metadata, sbom, cosign-installer, attest) is untouched"
  - "release.yml on: trigger (push tags v* + release published) and the four-scope publish permissions block were NOT touched — only a step-0 insertion (the tag-based chain stays as locked in 08-01)"

patterns-established:
  - "Cross-workflow SHA-pin invariant gate: a regex over all three workflow files asserts every uses: is a 40-hex SHA with no surviving @vN floating tag"

requirements-completed: [RELX-02]

# Metrics
duration: 5min
completed: 2026-06-15
---

# Phase 8 Plan 02: CI Surface Hardening + SHA-Pin Closeout Summary

**harden-runner (audit) inserted as the literal step 0 of all four CI/release jobs, the PR-title gate repinned off its moving `v5` tag onto the immutable `v5.5.3` SHA, and the release process documented — closing the one live moving-tag defect so every `uses:` across all three workflows is now a 40-hex commit SHA.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-06-15
- **Completed:** 2026-06-15
- **Tasks:** 3
- **Files modified:** 3 (0 created, 3 edited)

## Accomplishments

- **ci.yml** — inserted `step-security/harden-runner@9af89fc # v2.19.4` (`egress-policy: audit`) as the literal step 0 of all three jobs (`static-gates`, `pr-title`, `build-scan`), each before its prior first step (Checkout for static-gates/build-scan, Validate PR title for pr-title). Repinned the PR-title gate off the moving `v5` major tag (`e32d7e60…`) onto the immutable `v5.5.3` SHA `0723387faaf9b38adef4775cd42cfd5155ed6017` with an honest `# v5.5.3` comment. The `on:` trigger, the `contents: read` default, and every other SHA pin are unchanged.
- **release.yml** — inserted the identical harden-runner audit step 0 on the `publish` job before Checkout, so it observes the GHCR push / SBOM / cosign / attestation egress from job start. The `v*`-tag trigger and the four-scope (`contents:read`, `packages:write`, `id-token:write`, `attestations:write`) permissions block are untouched.
- **CONTRIBUTING.md** — added a `## Release process` section (after `## Submitting changes`, before `## Architecture decisions`) documenting the release-please tag-based chain, the squash-merge PR-title linkage that makes release-please versioning work, the harden-runner audit-then-block policy with ACC-02 deferral, and the `GITHUB_TOKEN`-retrigger caveat. No em dashes, no horizontal rules.
- **Full Phase 8 static suite green:** all 3 workflows parse, both JSON configs parse, the cross-workflow SHA-pin assertion passes (25 `uses:` across the 3 files, all 40-hex, no `@vN`), and `uvx --with charset-normalizer reuse lint` is 329/329 compliant.

## Re-asserted Action SHAs (against Plan 08-01's live-verified record)

| Action (repo) | Tag | 40-hex commit SHA written | Plan 08-01 record | Match |
|---------------|-----|----------------------------|-------------------|-------|
| step-security/harden-runner | v2.19.4 | `9af89fc71515a100421586dfdb3dc9c984fbf411` | `9af89fc71515a100421586dfdb3dc9c984fbf411` | yes |
| amannn/action-semantic-pull-request | v5.5.3 | `0723387faaf9b38adef4775cd42cfd5155ed6017` | `0723387faaf9b38adef4775cd42cfd5155ed6017` | yes |

No drift from the Plan 08-01 live `git ls-remote` record; the research hints were re-asserted, not trusted directly.

## Final Cross-Workflow SHA-Pin State

Every `uses:` ref across `release-please.yml`, `ci.yml`, and `release.yml` (25 total) is a 40-hex commit SHA. No floating `@vN` tag survives anywhere. The one live moving-tag defect (the amannn `@v5` gate) is closed.

## Jobs Hardened (harden-runner audit step 0)

| Workflow | Job | Step-0 action | egress-policy |
|----------|-----|---------------|---------------|
| ci.yml | static-gates | step-security/harden-runner@9af89fc | audit |
| ci.yml | pr-title | step-security/harden-runner@9af89fc | audit |
| ci.yml | build-scan | step-security/harden-runner@9af89fc | audit |
| release.yml | publish | step-security/harden-runner@9af89fc | audit |

## Task Commits

1. **Task 1: Harden ci.yml (harden-runner step 0 on all 3 jobs) + repin the PR-title gate** — `e0d5b0e` (ci)
2. **Task 2: Harden release.yml (harden-runner step 0 on the publish job)** — `4c5f2ac` (ci)
3. **Task 3: Document the release process + runner hardening in CONTRIBUTING.md** — `daffa32` (docs)

**Plan metadata:** (final docs commit — see git log)

## Files Created/Modified

- `.github/workflows/ci.yml` — harden-runner audit step 0 on static-gates / pr-title / build-scan; PR-title gate repinned to the immutable v5.5.3 SHA; every `uses:` a 40-hex pin.
- `.github/workflows/release.yml` — harden-runner audit step 0 on the publish job; trigger + four-scope permissions + every existing pin unchanged.
- `CONTRIBUTING.md` — new `## Release process` section (release chain, PR-title linkage, audit-then-block, retrigger caveat); SPDX HTML header on line 1 unmoved.

## Decisions Made

- **SHAs re-asserted, not invented.** Both action SHAs were cross-checked against Plan 08-01's live-`git ls-remote`-verified table before any `uses:` line was written; both matched exactly (no drift).
- **harden-runner is step 0 in every job.** It precedes `actions/checkout` (or the first step where no checkout exists, as in pr-title) so it observes all subsequent egress. Placing it later is the documented anti-pattern.
- **Only the one moving-tag defect was repinned.** The amannn `@v5` gate was the single floating tag across the touched workflows; every other action was already SHA-pinned and stays so. No step-0 insertion changed a pre-existing pin.
- **release.yml trigger + permissions untouched.** Only a step-0 insertion; the tag-based chain and the already-reviewed least-privilege four-scope block (T-08-02 accept) are preserved.

## Deviations from Plan

None - plan executed exactly as written. Both action SHAs matched the Plan 08-01 verified record on re-assertion (no drift), so no discrepancy-surfacing checkpoint was needed.

## Issues Encountered

None. The Windows dev box ran Python `yaml`/`json` parse, the cross-workflow SHA regex, and `uvx --with charset-normalizer reuse lint` cleanly. `actionlint` remains unavailable on this host (known — the Python YAML parse covered structural validity); full action-schema lint is the first live CI run (ACC-02-adjacent).

## Threat Surface

The plan's `<threat_model>` `mitigate` dispositions were all implemented:

- **T-08-01 (action tampering — the live moving-tag defect):** the amannn PR-title gate repinned off `@v5` onto the immutable `v5.5.3` SHA `0723387…`; the old `e32d7e60…` moving SHA is gone. The cross-file regex gate confirms no `@vN` survives across all three workflows.
- **T-08-03 (runner egress on static-gates / pr-title / build-scan / publish):** harden-runner is the literal step 0 (before checkout) on every job in `egress-policy: audit`. The block flip + discovered allowlist is the explicitly-deferred ACC-02, documented in CONTRIBUTING.
- **T-08-02 (publish token scope):** accept (unchanged) — the four-scope publish permissions block was not touched; this plan adds no privilege.
- **T-08-04 / T-08-SC (secret leakage / SHAs written this plan):** only `${{ secrets.GITHUB_TOKEN }}` is referenced (pre-existing); the harden-runner step needs no secret in audit mode; CONTRIBUTING.md adds no literal token / hostname / VMID; both SHAs re-asserted against the Plan 08-01 verified record. `reuse lint` 329/329 green.

No new threat surface beyond the plan's register was introduced.

## User Setup Required

None - no external service configuration on the dev box. The deferred **ACC-02** on-runner acceptance remains: (1) the first live release-please PR + the `v*`-tag-fires-release.yml check (the `GITHUB_TOKEN`-retrigger caveat now documented in CONTRIBUTING.md), and (2) the harden-runner `block` flip with the discovered `allowed-endpoints` allowlist after audit telemetry accrues (`build-scan` / `publish` carry the widest latent egress).

## Next Phase Readiness

- Phase 8 is plan-complete (2/2). Every `uses:` across all three workflows is a 40-hex SHA; the release process is documented; the full Phase 8 static suite is green.
- No baseline-architecture deviation emerged; no ADR required for this plan.

## Self-Check: PASSED

All modified files present and committed; both task patterns confirmed in the workflows; all three task commits (`e0d5b0e`, `4c5f2ac`, `daffa32`) exist in the git log.

*Phase: 08-release-hardening-release-please-harden-runner*
*Completed: 2026-06-15*
