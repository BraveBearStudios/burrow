<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

---
phase: 08-release-hardening-release-please-harden-runner
plan: 01
subsystem: infra
tags: [release-please, harden-runner, github-actions, supply-chain, sha-pin, reuse, spdx]

# Dependency graph
requires:
  - phase: 04-release-supply-chain
    provides: "release.yml — the v* tag-triggered GHCR publish job this workflow chains into via the tag"
  - phase: 06-ci-tooling-robustness
    provides: "REUSE.toml comment-less-JSON annotation convention (CICD-08) + reuse pinned --with charset-normalizer"
provides:
  - "release-please-config.json (release-type simple, single root package '.', bootstrap-sha = v1.1 COMMIT 9bccec85)"
  - ".release-please-manifest.json (seed root version 1.1.0 so the first release PR proposes v1.2.0)"
  - ".github/workflows/release-please.yml (push:main, harden-runner audit step 0, release-please action, SHA-pinned)"
  - "REUSE.toml registration for the two new comment-less JSON config files"
  - "verified-SHA record (harden-runner v2.19.4, release-please-action v4.4.1, amannn v5.5.3) for Plan 02 to re-assert"
affects: [08-02, release, ci]

# Tech tracking
tech-stack:
  added:
    - "googleapis/release-please-action@5c625bf (v4.4.1) — Conventional-Commit release PR + tag-on-merge"
    - "step-security/harden-runner@9af89fc (v2.19.4) — runner egress monitoring (audit mode)"
  patterns:
    - "Manifest-mode release-please (v4): config-file + manifest-file in repo root, tiny action surface"
    - "harden-runner as the literal step 0 of every job (observes all egress)"
    - "Tag-based workflow chain (release-please tags v* → release.yml fires; no trigger edit, no shared file)"
    - "Live SHA-verification gate before any uses: line is written (research SHAs are hints, not values to trust)"

key-files:
  created:
    - "release-please-config.json"
    - ".release-please-manifest.json"
    - ".github/workflows/release-please.yml"
  modified:
    - "REUSE.toml"

key-decisions:
  - "bootstrap-sha = the v1.1 COMMIT 9bccec85 (re-derived via git rev-parse v1.1^{commit}), NOT the f900a95 tag object that git rev-parse v1.1 returns"
  - "manifest seed = 1.1.0 (NOT the research-recommended 1.2.0) so the first release PR captures the in-progress v1.2 work and proposes v1.2.0"
  - "release-please job permissions = EXACTLY contents:write + pull-requests:write (no issues:write) — least privilege"
  - "Built-in GITHUB_TOKEN only (no PAT, no new secret) — preserves the v1 LAN/no-stored-secret posture"
  - "No changelog-sections override — the locked 'defaults' decision is achieved by omission"
  - "Two comment-less JSON files licensed via REUSE.toml (CICD-08), NOT an inline header; the YAML workflow carries the 2-line inline SPDX header"

patterns-established:
  - "Pattern 1: A merge to main maintains an automated release PR; merging it tags v* which chains into the existing release.yml publish via the tag only"
  - "Pattern 2: harden-runner audit-then-block — audit ships now (observes egress), the block flip + discovered allowlist is the deferred ACC-02 on-runner step"

requirements-completed: [RELX-01, RELX-02]

# Metrics
duration: 12min
completed: 2026-06-15
---

# Phase 8 Plan 01: release-please Surface + Live SHA-Pin Summary

**release-please manifest-mode surface (config + manifest seeded 1.1.0 + push:main workflow) with harden-runner audit step 0, every action pinned to a live-verified upstream commit SHA, and the corrected v1.1-COMMIT bootstrap-sha.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-06-15
- **Completed:** 2026-06-15
- **Tasks:** 3 (Task 1 is a no-file verification gate)
- **Files modified:** 4 (3 created, 1 edited)

## Accomplishments

- Ran the load-bearing live SHA-verification gate (Task 1): all three action tags resolved live from upstream via `git ls-remote`; all match the research hints exactly, and the v1.1 bootstrap COMMIT (`9bccec85`) was confirmed distinct from the v1.1 tag object (`f900a95`).
- Authored `release-please-config.json` (release-type simple, single root `.`, the corrected `bootstrap-sha = 9bccec85`) and `.release-please-manifest.json` (the corrected seed `1.1.0`), both pure JSON, both registered in `REUSE.toml`.
- Authored `.github/workflows/release-please.yml`: push:main, workflow-default `contents: read`, the `release-please` job elevated to exactly `contents: write` + `pull-requests: write`, harden-runner `egress-policy: audit` as the literal step 0, the release-please action SHA-pinned, SPDX header on lines 1-2.
- Full wave-merge gate green: JSON parse + all 3 workflows YAML parse + `reuse lint` 328/328 compliant.

## Verified-SHA Record (Task 1 — for Plan 02 to re-assert against)

All three action SHAs were resolved **live** from the canonical upstream repos via `git ls-remote --tags`. Every resolved value matched the RESEARCH.md hint exactly (no upstream drift).

| Action (repo) | Tag | Resolved 40-hex commit SHA | Research hint | Match | Consumed by |
|---------------|-----|----------------------------|---------------|-------|-------------|
| step-security/harden-runner | v2.19.4 | `9af89fc71515a100421586dfdb3dc9c984fbf411` | `9af89fc…` | ✓ | Plan 01 (this) + Plan 02 (all-job harden-runner) |
| googleapis/release-please-action | v4.4.1 | `5c625bfb5d1ff62eadeeb3772007f7f66fdcf071` | `5c625bf…` | ✓ | Plan 01 (this) |
| amannn/action-semantic-pull-request | v5.5.3 | `0723387faaf9b38adef4775cd42cfd5155ed6017` | `0723387…` | ✓ | Plan 02 (repin off the moving v5 tag) |

**Bootstrap COMMIT (release-please-config.json `bootstrap-sha`):**

| Lookup | Object kind | SHA | Use |
|--------|-------------|-----|-----|
| `git rev-parse "v1.1^{commit}"` (== `git rev-list -n1 v1.1`) | **commit** | `9bccec8518900518588ec11300151e44fed259e0` | ✓ CORRECT — written to `bootstrap-sha` |
| `git rev-parse v1.1` | annotated tag object | `f900a95556d4d82498008a126f3a2cf507e5f3c1` | ✗ WRONG kind — NOT used (the research/PATTERNS error this plan corrected) |

All three action tags are lightweight (the direct `git ls-remote` line is already the commit; no `^{}` deref line was emitted), so the direct SHA is the commit SHA in each case.

## Task Commits

1. **Task 1: [BLOCKING] Resolve real action SHAs + v1.1 bootstrap COMMIT** — no file (verification gate); `SHAS_VERIFIED` printed.
2. **Task 2: Write the two JSON config files + register in REUSE.toml** — `7063e46` (feat)
3. **Task 3: Author release-please.yml (push:main, harden-runner audit step 0, SHA-pinned)** — `bae6299` (feat)

**Plan metadata:** (final docs commit — see below)

## Files Created/Modified

- `release-please-config.json` — release-please manifest-mode config: `release-type: simple`, `include-v-in-tag: true`, `bootstrap-sha: 9bccec85` (the v1.1 commit), single package `.`; no `changelog-sections` (defaults by omission). Pure JSON, no inline header.
- `.release-please-manifest.json` — `{ ".": "1.1.0" }`, the corrected seed. Pure JSON, no inline header.
- `.github/workflows/release-please.yml` — push:main release-please workflow; harden-runner audit step 0; release-please action under `contents:write`+`pull-requests:write`; built-in `GITHUB_TOKEN`; SPDX header lines 1-2; every `uses:` SHA-pinned.
- `REUSE.toml` — added `release-please-config.json` and `.release-please-manifest.json` to the existing comment-less-JSON `[[annotations]]` block (no new block, no `*.json` glob).

## Decisions Made

The two authoritative corrections drove the load-bearing decisions:

- **bootstrap-sha = the v1.1 COMMIT `9bccec85`, not the tag object `f900a95`.** Re-derived live with `git rev-parse "v1.1^{commit}"` and cross-checked with `git rev-list -n1 v1.1`; confirmed `git rev-parse v1.1` returns the different `f900a95` tag-object SHA (the wrong object kind for release-please bootstrap-sha). The RESEARCH.md / PATTERNS.md `f900a95` value was overridden.
- **manifest seed = `1.1.0`, not the research-recommended `1.2.0`.** Git has only `v1.0`/`v1.1` tagged; `v1.2` is the in-progress milestone and is not tagged. Seeding `1.1.0` makes the first release PR capture the merged v1.2 work and propose `v1.2.0`.
- **Job permissions kept to exactly `contents:write` + `pull-requests:write`** (no `issues:write`) and the built-in `GITHUB_TOKEN` only — least privilege + the v1 no-stored-secret posture (Pitfall 4 / T-08-02).

## Deviations from Plan

None - plan executed exactly as written. All three action SHAs matched the research hints on live verification (no drift), so no discrepancy-surfacing checkpoint was needed.

## Issues Encountered

None. The Windows dev box ran `git`, Python `yaml`/`json`, and `uvx --with charset-normalizer reuse lint` cleanly. `actionlint` is unavailable on this host (known — RESEARCH Environment Availability); the Python YAML parse covered structural validity, and full action-schema lint is the first CI run (ACC-02-adjacent).

## Threat Surface

The plan's `<threat_model>` `mitigate` dispositions were all implemented:

- **T-08-01 / T-08-SC (action tampering / supply chain):** every `uses:` pinned to a live-`git ls-remote`-verified 40-hex commit SHA; no floating `@vN` tag. The trailing `# vX.Y.Z` is documentation only.
- **T-08-02 (token scope):** workflow default `contents: read`; the job elevates to exactly `contents:write` + `pull-requests:write`; built-in `GITHUB_TOKEN`, no new secret.
- **T-08-03 (runner egress):** harden-runner is the literal step 0 in `egress-policy: audit`. The block flip + discovered allowlist is the explicitly-deferred ACC-02.
- **T-08-04 (secret leakage):** only `${{ secrets.GITHUB_TOKEN }}` is referenced; no literal token, hostname, VMID, or PAT. `reuse lint` green.

No new threat surface beyond the plan's register was introduced.

## User Setup Required

None - no external service configuration required on the dev box. The first live release-please PR + the `v*`-tag-fires-release.yml check + the harden-runner block flip are the deferred **ACC-02** on-runner acceptance (NOT a dev-box step). The first releaser should confirm that the release-please tag (pushed by `GITHUB_TOKEN`) re-triggers `release.yml`; if suppressed, the remediation is a scoped token or a manual re-run on the tag (Open Q1).

## Next Phase Readiness

- The verified-SHA record above is captured for **Plan 02** to re-assert against (Plan 02 adds harden-runner step 0 to ci.yml/release.yml's jobs and repins the amannn PR-title gate off its moving `v5` tag to `0723387 # v5.5.3`).
- `release.yml`'s trigger is untouched — the chain is tag-based, as locked.
- No baseline-architecture deviation emerged; no ADR required for this plan.

## Self-Check: PASSED

All created files present (`release-please-config.json`, `.release-please-manifest.json`, `.github/workflows/release-please.yml`, `08-01-SUMMARY.md`) and both task commits (`7063e46`, `bae6299`) exist in the git log.

---
*Phase: 08-release-hardening-release-please-harden-runner*
*Completed: 2026-06-15*
