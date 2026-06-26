<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

---
phase: 14-first-real-infra-acceptance
plan: 02
subsystem: acceptance
tags: [acceptance, human-uat, release, cosign, attestation, harden-runner, acc-01, acc-02, acc-03]

# Dependency graph
requires:
  - phase: 14-01
    provides: "actionlint static gate (reviewdog/action-actionlint) + harden-runner allowlist-prep comments referencing 14-ACCEPTANCE.md"
  - phase: 04
    provides: "release.yml publish job + verification runbook comment (cosign verify + gh attestation verify by digest)"
  - phase: 03
    provides: "PRIMING.md STEP 4 H9 five-step homelab gate"
provides:
  - "14-ACCEPTANCE.md: operator release/verify runbook for ACC-02/03 (cosign + attestation verify by @sha256: digest, the gh-attestation exit-0 output-assertion trap, the harden-runner audit->block flip with the discovered allowlist, the exactly-4-perms + SHA-pin standing checklist, the actionlint gate)"
  - "14-HUMAN-UAT.md: consolidated ACC-01/02/03 operator checklist (H9 five-step gate + reaper/auto-stop/capacity/node + persistent stop->start with disk + scrollback + live release verify), all 16 items result: [pending], rolling up Phase 03/04"
  - "03/04-HUMAN-UAT.md superseded-by-v1.3-Phase-14 markers (additive, items + results unchanged)"
affects: [v1.3-go-live-operator-acceptance]

# Tech tracking
tech-stack:
  added: []
  patterns: ["operator runbook: each ACC item gives EXACT command + EXPECTED output + explicit PASS/FAIL line; verify BY DIGEST not tag; assert on attestation OUTPUT not exit code"]

key-files:
  created:
    - .planning/phases/14-first-real-infra-acceptance/14-ACCEPTANCE.md
    - .planning/phases/14-first-real-infra-acceptance/14-HUMAN-UAT.md
    - .planning/phases/14-first-real-infra-acceptance/14-02-SUMMARY.md
  modified:
    - .planning/milestones/v1.0-phases/03-reproducible-workers/03-HUMAN-UAT.md
    - .planning/milestones/v1.0-phases/04-hardening-release/04-HUMAN-UAT.md

key-decisions:
  - "Referenced reviewdog/action-actionlint (the action 14-01 actually wired) in the actionlint gate sections, NOT the plan/CONTEXT's rhysd/actionlint (which ships no action.yml). Mirrors the 14-01 substitution so the runbook matches the real ci.yml step."
  - "Scrubbed the pre-existing em dashes in 03/04-HUMAN-UAT.md to colons/commas while adding the superseded note. The plan's Task 3 verify gates 0 em dashes in BOTH files AND requires the original items + result values unchanged; punctuation substitution satisfies both (no item deleted, no Status value changed). Tracked as a Rule 1 fix."
  - "ACC-01/02/03 documented as MANUAL-ONLY / human_needed throughout; nothing in this plan claims them auto-passed. All 16 UAT items land result: [pending]."

patterns-established:
  - "Acceptance runbook format: Preconditions table, then per-ACC Steps each with a fenced command, an Expected output paragraph, and a bold PASS/FAIL line; closes with a standing-invariants table."

requirements-completed: []

# Metrics
duration: 8min
completed: 2026-06-26
---

# Phase 14 Plan 02: Acceptance Runbook + Consolidated Human-UAT Summary

**Authored the operator-run acceptance slice of ACC-01/02/03: a trap-aware release/verify runbook (14-ACCEPTANCE.md), a single consolidated 16-item human-UAT checklist (14-HUMAN-UAT.md) all pending, and additive superseded markers on the rolled-up Phase 03/04 HUMAN-UAT files. No em dashes anywhere.**

## Performance

- **Duration:** ~8 min
- **Tasks:** 3
- **Files created:** 2 (14-ACCEPTANCE.md, 14-HUMAN-UAT.md)
- **Files modified:** 2 (03-HUMAN-UAT.md, 04-HUMAN-UAT.md)

## Accomplishments

- **14-ACCEPTANCE.md** (Task 1): the operator release/verify runbook. Gives the exact `cosign verify` and `gh attestation verify` commands BY `@sha256:` digest (mirroring release.yml :166-178), documents the `gh attestation verify` exit-0 trap (assert on OUTPUT / inspect the JSON, not `$?`; pair with the loud-failing cosign verify), states verify-by-digest-not-tag, lays out the harden-runner `audit` to `block` flip procedure (discover the live allowlist from Step Security insights, fill `allowed-endpoints` with the seven Fulcio/Rekor/TUF/OIDC/GHCR/github.com/objects endpoints, flip all five jobs, re-run green), the actionlint gate (reviewdog/action-actionlint), and the exactly-4-publish-perms + SHA-pin + by-digest + dual-SBOM standing checklist. Each ACC item carries command + expected output + PASS/FAIL.
- **14-HUMAN-UAT.md** (Task 2): the single consolidated ACC-01/02/03 operator checklist. 16 items covering the H9 five-step homelab gate (create / live terminal / stop / start / destroy), reaper / idle auto-stop / capacity / real least-loaded node selection, the real persistent stop->start with disk intact AND scrollback restored (the tmux -A reattach, WSX-02/03) and the reaper-spares-persistent-stopped proof (WSX-04), the ACC-02 live release-please merge + actionlint + harden-runner block flip, and the ACC-03 cosign + attestation verify by digest. Every item is `result: [pending]`. A Supersedes table maps each Phase 03 (5) and Phase 04 (5) item to its new home.
- **03/04-HUMAN-UAT.md superseded** (Task 3): added a short additive note after the frontmatter pointing to 14-HUMAN-UAT.md as the consolidated v1.3 Phase 14 gate. Original items and all `Status: ⬜ pending` values preserved unchanged (5 pending in each, verified).

## Task Commits

1. **Task 1: Author 14-ACCEPTANCE.md** - `f5f162e` (docs)
2. **Task 2: Author consolidated 14-HUMAN-UAT.md** - `354e823` (docs)
3. **Task 3: Mark Phase 03/04 HUMAN-UAT superseded** - `f0f4255` (docs)

**Plan metadata:** committed with this SUMMARY (docs: complete plan).

## Files Created/Modified

- `.planning/phases/14-first-real-infra-acceptance/14-ACCEPTANCE.md` (created) - operator release/verify runbook for ACC-02/03.
- `.planning/phases/14-first-real-infra-acceptance/14-HUMAN-UAT.md` (created) - consolidated ACC-01/02/03 human-UAT checklist (16 items, all pending).
- `.planning/milestones/v1.0-phases/03-reproducible-workers/03-HUMAN-UAT.md` (modified) - additive superseded note; pre-existing em dashes scrubbed; results unchanged.
- `.planning/milestones/v1.0-phases/04-hardening-release/04-HUMAN-UAT.md` (modified) - additive superseded note; pre-existing em dashes scrubbed; results unchanged.

## Verification

All three per-task `<automated>` structural greps pass:

- Task 1: file exists; contains `cosign verify`, `gh attestation verify`, `@sha256:`, `egress-policy: block`, `fulcio.sigstore.dev`, `packages: write`; the exit-0 trap (assert on OUTPUT not exit code) is documented; the four publish-perm names appear; em-dash count 0; each ACC item has command + expected + PASS/FAIL.
- Task 2: file exists; contains the H9 verbs `create`/`stop`/`start`/`destroy`/`scrollback`, plus `persistent`, `reaper`, `cosign`, `attestation`; every item `result: [pending]` (0 passed); references Phase 03 + Phase 04 / 03-HUMAN-UAT + 04-HUMAN-UAT; em-dash count 0.
- Task 3: both files contain `superseded` + a Phase 14 reference; em-dash count 0 in both; all 5 `Status: ⬜ pending` values intact in each (no result changed).

Phase 14 verification itself remains `human_needed` by design: ACC-01/02/03 are real-infra / live-release and are NOT auto-passed by this plan. This plan delivers only the artifacts that let the operator run and record them.

## Decisions Made

See `key-decisions` in the frontmatter. The load-bearing ones: (1) referencing `reviewdog/action-actionlint` (what 14-01 actually wired) instead of the plan's `rhysd/actionlint`; (2) scrubbing pre-existing em dashes in 03/04 to satisfy the 0-em-dash gate without deleting items or changing results.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pre-existing em dashes in 03/04-HUMAN-UAT.md violated the Task 3 0-em-dash gate**
- **Found during:** Task 3
- **Issue:** The plan's Task 3 `<automated>` check requires the em-dash count (byte sequence `\xe2\x80\x94`) to be 0 in BOTH `03-HUMAN-UAT.md` and `04-HUMAN-UAT.md`, while also requiring the original items and their `result:` values to stay unchanged. The two files already contained 13 and 9 em dashes respectively (authored in the v1.0 milestone, before the repo-wide no-em-dash rule), so a purely additive note would have left the gate failing.
- **Fix:** Replaced each pre-existing em dash with a colon, comma, or parenthetical restructure (meaning preserved). Also converted three stray right-arrow glyphs in 03 item 1 to commas for consistency. No test item was deleted; no `Status:` value was changed (5 `⬜ pending` remain in each file, verified).
- **Files modified:** `03-HUMAN-UAT.md`, `04-HUMAN-UAT.md`
- **Verification:** em-dash count 0 in both; `Status: ⬜ pending` count = 5 in each; superseded + Phase 14 reference present.
- **Committed in:** `f0f4255`

**2. [Accuracy correction, per plan_specifics] actionlint action reference**
- **Found during:** Task 1
- **Issue:** The plan/CONTEXT named `rhysd/actionlint`, but 14-01 correctly substituted `reviewdog/action-actionlint` (rhysd/actionlint ships no action.yml). The runbook must match the real ci.yml step.
- **Fix:** Referenced `reviewdog/action-actionlint` in the 14-ACCEPTANCE.md actionlint gate sections and noted it as the SHA-pinned step in ci.yml `static-gates`. This is the explicitly instructed accuracy fix from the plan's `plan_specifics`, not a free deviation.
- **Files modified:** `14-ACCEPTANCE.md`
- **Committed in:** `f5f162e`

**Total deviations:** 2 (1 Rule 1 em-dash gate fix; 1 instructed accuracy correction).
**Impact on plan:** Both keep the deliverables correct and gate-passing. No scope creep: still 2 created + 2 modified docs, no source/runtime code touched.

## Known Stubs

None. These are acceptance docs; no code, no data wiring, no placeholder UI.

## Threat Flags

None. No new runtime surface, ingress, auth path, or schema change. The only security-relevant content is the release-verify procedure, which documents (does not weaken) the already-hardened publish path. The T-14-01 exit-0 trap, T-14-02 premature-flip, and T-14-03 secret-leak threats from the plan's threat_model are all mitigated by the runbook content (assert-on-output + cosign pairing; flip-only-after-live-audit; no secret in the docs).

## Issues Encountered

The plan's em-dash grep targets byte sequence `\xe2\x80\x94`; the dev-box shell needed the explicit byte form for a reliable count. Resolved by using `grep -c $'\xe2\x80\x94'` for verification.

## Next Phase Readiness

- The operator now has the complete, trap-aware procedure to run the real homelab smoke (ACC-01), the first live signed release + harden-runner block flip + actionlint (ACC-02), and the cosign/attestation verify by digest (ACC-03), and a single consolidated checklist to flip from pending to passed.
- Phase 14 verification stays `human_needed`: the autonomous run stops at the human gate. Do NOT run the milestone lifecycle (audit/complete/cleanup) until the operator passes the real-infra UAT.

## Self-Check: PASSED
