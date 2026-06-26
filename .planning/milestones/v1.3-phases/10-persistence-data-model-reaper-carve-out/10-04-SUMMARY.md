<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

---
phase: 10-persistence-data-model-reaper-carve-out
plan: 04
subsystem: testing
tags: [reconciler, reaper, persistence, regression-test, pytest, wsx-04, wsx-02]

# Dependency graph
requires:
  - phase: 10-03
    provides: "the persistent column threaded through DTOs/provider/create-saga (required to create persistent rows in the tests)"
  - phase: 10-01
    provides: "the mocked-proxmoxer integration tier gate (the persistence-compute work was unblocked behind it)"
provides:
  - "WSX-04 reaper carve-out comment locking the ownership-keyed safety bound (comment only, predicate byte-for-byte unchanged)"
  - "two RED-if-regressed negative-control reaper tests (persistent-stopped spared; soft-deleted-persistent reclaimed)"
  - "three WSX-02 persistence behavioral round-trip tests (persistent create camelCase round-trip; default ephemeral; persistent stop->start same id/vmid)"
affects: [phase-13-setup-wizard-ui, phase-14-real-infra-acceptance]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Negative-control regression test: a discriminating test proven RED by injecting the exact regression it guards against, not a tautological always-pass"
    - "Carve-out comment over the single safety bound: document intent at the predicate without adding a code branch (one loop, ownership-keyed)"

key-files:
  created: []
  modified:
    - api/services/reconciler.py
    - api/tests/unit/test_reconciler.py
    - api/tests/integration/test_workspaces_api.py

key-decisions:
  - "WSX-04 is 'lock what already works' — the orphan predicate already keys on ownership (vmid in live_vmids), never on stopped state, so the Phase 10 deliverable is a carve-out COMMENT plus negative-control tests, with ZERO predicate logic change"
  - "The negative-control tests were proven discriminating by temporarily injecting a status==stopped reaping branch and confirming Test A fails (the persistent stopped CT got destroyed); reconciler then restored"
  - "_create's **overrides annotation widened str->object so persistent=True (a bool) type-checks under mypy (PATTERNS-noted)"

patterns-established:
  - "RED-if-regressed proof: verify a guard test is discriminating by reproducing the regression locally and confirming the test fails, then restore"
  - "Persistence survives stop->start via the existing live-row bound (a stopped persistent workspace keeps a live row); explicit delete drops the row -> orphan-eligible (delete is not a persistence shield)"

requirements-completed: [WSX-04]

# Metrics
duration: 12min
completed: 2026-06-25
---

# Phase 10 Plan 04: WSX-04 Reaper Carve-out + Persistence Round-trip Lock Summary

**Locked the safety-critical reaper carve-out (WSX-04) with a comment-only edit and two RED-if-regressed negative-control tests, plus three WSX-02 persistence round-trip proofs — the v1.3 hard gate against irreversible persistent-workspace data loss, with the orphan predicate left byte-for-byte unchanged.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-06-25T10:44Z
- **Completed:** 2026-06-25T10:54Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Added the WSX-04 carve-out comment at the orphan predicate (`reconciler.py`) documenting that the bound keys on OWNERSHIP, never on `stopped` state — predicate logic unchanged (verified comment-only via `git diff`).
- Added two negative-control reaper tests, proven discriminating by injecting the exact `status == "stopped"` regression and confirming Test A fails (the persistent stopped CT was destroyed: `assert 220 in {}`), then restoring the reconciler.
- Added three WSX-02 persistence behavioral round-trip tests over the real app: persistent create camelCase round-trip, default-ephemeral, and persistent stop->start preserving the same id/vmid with `persistent` still true.
- Full backend suite green: **215 passed** (up from 210 at Plan 03; +5 new tests). ruff + mypy clean on all three changed files.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add the reaper carve-out comment (comment only)** - `63208ad` (docs)
2. **Task 2: Negative-control reaper tests (RED-if-regressed)** - `420ae69` (test)
3. **Task 3: Persistence behavioral round-trip tests (WSX-02 SC2)** - `1fe5c28` (test)

_Note: Tasks 2 and 3 are TDD-typed but lock already-correct behavior (the predicate was already ownership-keyed from Plan 04 v1.0; the `persistent` column was wired in Plan 03), so each is a single GREEN-passing `test(...)` commit. Their RED-if-regressed property was verified out-of-band (Task 2) rather than via a separate failing commit, since adding a real RED commit would require deliberately regressing committed production logic._

## Files Created/Modified

- `api/services/reconciler.py` - Added a 13-line WSX-04 carve-out comment above the orphan predicate; the `for ... if vmid in live_vmids or vmid not in pool: continue` bound is byte-for-byte unchanged.
- `api/tests/unit/test_reconciler.py` - Added `test_persistent_stopped_workspace_is_never_reaped` (Test A) and `test_soft_deleted_persistent_workspace_becomes_orphan_eligible` (Test B), using the direct-create idiom to pass `status` + `persistent`.
- `api/tests/integration/test_workspaces_api.py` - Widened `_create(**overrides)` annotation `str -> object`; added `test_persistent_create_round_trips_camelcase`, `test_default_create_is_ephemeral`, and `test_persistent_workspace_survives_stop_start_round_trip`.

## Decisions Made

- **Carve-out is comment-only.** Per the plan and RESEARCH Pitfall 1, the orphan predicate already satisfies WSX-04 (it keys on `vmid in live_vmids`, never on state), so adding any `status`/`persistent` branch would BE the regression. The edit is purely a `#` comment block.
- **Proved the negative-control tests are discriminating.** Rather than trust that the tests would fail under regression, I locally injected a `status == "stopped"` reaping branch and confirmed `test_persistent_stopped_workspace_is_never_reaped` failed, then restored the reconciler (`git diff --stat` showed no residual change). This is the RED-if-regressed evidence the phase requires.
- **Widened the `_create` override annotation** from `str` to `object` so the bool override `persistent=True` type-checks under mypy (the plan flagged this).

## Deviations from Plan

None - plan executed exactly as written. No Rule 1-4 deviations were needed; all three changed files were clean of bugs, missing functionality, and blockers.

## Issues Encountered

- The `rtk pytest` wrapper collected no tests in this repo (proxmoxer/uv-managed venv); ran the suite via `uv run pytest` directly, which is the project's documented runner. No impact on correctness.

## Deferred Issues

- `api/tests/unit/test_node_selection.py:156-158` — 3 pre-existing mypy `"LogRecord" has no attribute` errors. NOT touched by this plan (verified via `git diff --name-only`), already tracked in `deferred-items.md` and prior summaries (10-01, 10-03). Out of scope per the SCOPE BOUNDARY rule; ruff and the full pytest suite are unaffected (both green).

## Threat Surface Scan

No new security-relevant surface. T-10-04A/B (the reaper destroying a persistent stopped workspace; a future state-based branch) are mitigated exactly as the threat register specifies: the predicate is unchanged and Test A is RED-if-regressed. T-10-04C (information disclosure into `reaper.*` events) is unchanged — no new field is read into any event; `persistent` is a bool. No threat flags.

## Next Phase Readiness

- WSX-04 hard gate is GREEN and locked: the reaper cannot destroy a persistent stopped workspace without failing a committed test.
- WSX-02 behavioral half (stop->start persistence) is proven over the Fake; Phase 13 adds the `persistent` checkbox UI onto the create modal against this same backend.
- Phase 14 (real-infra acceptance) remains the only non-CI-provable validation; nothing here depends on real Proxmox.

## Self-Check: PASSED

- FOUND: `.planning/phases/10-persistence-data-model-reaper-carve-out/10-04-SUMMARY.md`
- FOUND: `api/services/reconciler.py`, `api/tests/unit/test_reconciler.py`, `api/tests/integration/test_workspaces_api.py`
- FOUND commits: `63208ad` (Task 1), `420ae69` (Task 2), `1fe5c28` (Task 3)

---
*Phase: 10-persistence-data-model-reaper-carve-out*
*Completed: 2026-06-25*
