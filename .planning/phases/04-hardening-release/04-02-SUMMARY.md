<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 04-hardening-release
plan: 02
subsystem: api
tags: [asyncio, concurrency, capacity, reconciler, sqlite, adr]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: createWorkspace saga (capacity guard + VMID partial-unique reservation), stopWorkspace, _safe redaction
provides:
  - Atomic capacity-check+reserve critical section (one process-wide asyncio.Lock) closing the capacity-overcommit race (Pitfall 5)
  - stopWorkspace(reason=) threading reason into the workspace.stopped event data
  - reconciler_period_s / creating_timeout_s / idle_window_s Settings keys
  - Deterministic two-concurrent-create capacity-race integration test
  - ADR-0010 (in-process reconciler + capacity-lock architecture decision)
affects: [04-01 reconciler plan, 04-hardening-release]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Process-wide asyncio.Lock serializing a read+reserve critical section, released before slow saga work"
    - "Two-party asyncio.Event barrier inside a Fake to make a concurrency regression test deterministic and non-tautological"

key-files:
  created:
    - api/tests/integration/test_capacity_race.py
    - docs/adr/ADR-0010-in-process-reconciler-and-capacity-lock.md
  modified:
    - api/services/workspaceService.py
    - api/config.py
    - api/tests/unit/test_state_machine.py

key-decisions:
  - "v1 capacity race closed with a per-process asyncio.Lock (--workers 1 assumption); BEGIN IMMEDIATE is the documented --workers >1 upgrade path (ADR-0010)"
  - "The create-lock spans ONLY step-0 capacity guard + step-1 reservation; released before the multi-second clone so concurrent creates still parallelize"
  - "stopWorkspace reason is a keyword-only, fixed non-secret literal (None | 'idle'); no user/topology input flows into the event data (T-04-02B)"

patterns-established:
  - "Capacity-read serialization layered on top of the unchanged VMID partial-unique INSERT (the cross-process uniqueness arbiter stays the durable guarantee)"
  - "Anti-tautology proof: the race test fails with the lock bypassed (2 successes) and passes with it (1 success + 1 CapacityError)"

requirements-completed: [CAP-02]

# Metrics
duration: 38min
completed: 2026-06-11
---

# Phase 4 Plan 02: Capacity-lock + reconciler-readiness Summary

**Atomic capacity-check+reserve under one process-wide asyncio.Lock closes the node-overcommit race, stopWorkspace(reason=) threads `reason: idle` into the event log, and ADR-0010 records the in-process-reconciler + capacity-lock decision.**

## Performance

- **Duration:** ~38 min
- **Started:** 2026-06-11T22:44:33Z
- **Completed:** 2026-06-11T23:05:00Z
- **Tasks:** 3
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments
- Wrapped the create saga's step-0 capacity guard and step-1 VMID reservation in one `self._create_lock` critical section, released before the clone — two concurrent creates can no longer both pass a stale node-RAM read and overcommit a node (Pitfall 5 / CAP-02).
- Added a keyword-only `reason` param to `stopWorkspace`; the `workspace.stopped` event now carries `{"reason": "idle"}` for the reconciler's auto-stop and `{}` for operator stops (FROZEN guardrail 3 — the UI badge keys on `data.reason`).
- Added three non-secret reconciler cadence keys (`reconciler_period_s`, `creating_timeout_s`, `idle_window_s`) so Plan 04-01's reconciler has its config.
- Authored a deterministic, non-tautological capacity-race integration test that fails without the lock and passes with it.
- Wrote ADR-0010 recording the single in-process asyncio reconciler and the capacity-lock-vs-`BEGIN IMMEDIATE` decision in the repo's Nygard format.

## Task Commits

Each task was committed atomically (Task 1 was TDD: RED → GREEN):

1. **Task 1 (RED): failing stopWorkspace(reason=) tests** - `9742908` (test)
2. **Task 1 (GREEN): atomic capacity check+reserve + stopWorkspace(reason=) + Settings keys** - `81f94a1` (feat)
3. **Task 2: deterministic capacity-race integration test** - `a6ee94a` (test)
4. **Task 3: ADR-0010 in-process reconciler + capacity lock** - `15db872` (docs)

_Note: Task 1 followed the TDD RED/GREEN cycle (two commits); no refactor commit was needed (the GREEN diff was already minimal)._

## Files Created/Modified
- `api/services/workspaceService.py` - Added `self._create_lock = asyncio.Lock()`; wrapped step-0 guard + step-1 reservation in `async with self._create_lock`; added keyword-only `reason` to `stopWorkspace` and emit `{"reason": reason}` when set.
- `api/config.py` - Added the `# Reconciler (reaper + idle auto-stop, CAP-02/03)` block with `reconciler_period_s=60`, `creating_timeout_s=300`, `idle_window_s=1800`.
- `api/tests/unit/test_state_machine.py` - Added `test_operator_stop_carries_no_reason` ({} data) and `test_idle_stop_carries_reason_idle` ({"reason": "idle"} data).
- `api/tests/integration/test_capacity_race.py` (new) - Two concurrent creates over a barriered Fake + temp SQLite; asserts exactly one `Workspace` + one `CapacityError` and no overcommit.
- `docs/adr/ADR-0010-in-process-reconciler-and-capacity-lock.md` (new) - Nygard ADR (Status/Context/Decision/Consequences/Revisit trigger).

## Decisions Made
- **Capacity-read serialization via the live DB row count, not `_containers`.** The race test's Fake derives node memory from `listWorkspaces()` (which reflects the reserved `creating` row the instant it lands) rather than `_containers` (which only updates after the post-lock clone). This is the state the lock actually serializes the second create's check against.
- **Two-party `asyncio.Event` barrier for determinism.** A naive `asyncio.gather` + `sleep(0)` interleaving was scheduler-dependent and produced a false green (a tautology). A barrier where the first reader parks until a second arrives — satisfiable only when the lock is ABSENT, with a bounded timeout so the with-lock path never deadlocks — makes the test a true regression guard. Proven: bypassing the lock yields 2 successes (the bug); with the lock, 1 success + 1 CapacityError.
- **VMID INSERT untouched.** The 002 partial-unique index remains the cross-process VMID-uniqueness arbiter; only the capacity read was serialized.

## Deviations from Plan

None - plan executed exactly as written.

The three deviation-adjacent points below are within-plan engineering choices the plan explicitly delegated to Claude's discretion (the locking mechanism and the test's determinism strategy), not unplanned scope:
- The race test's barrier-based determinism strategy is the plan's "deterministic" requirement realized; the plan named the `asyncio.gather` shape but left the interleaving mechanism open.
- No new runtime dependency was added (RESEARCH Standard Stack: NONE), honoring the no-new-dependency constraint.

## Issues Encountered
- **First race-test design was a tautology.** The initial `getNodeMemory`-counts-from-DB + `sleep(0)` yields version passed even with the lock bypassed, because `asyncio.gather` let the first create fully reserve before the second read (aiosqlite connection-open latency dominated the interleaving). Resolved by replacing the yield-based interleaving with the two-party `asyncio.Event` barrier and verifying the bypassed-lock case fails (2 successes) before committing.

## Verification

- `cd api && uv run pytest tests/unit -q` — green (unit tier, including the two new reason tests).
- `cd api && uv run pytest tests/integration/test_capacity_race.py -x -q` — green; bypassing the lock makes it fail (anti-tautology proven).
- `cd api && uv run pytest -q` — **155 passed** (full api suite, no regression; existing saga/stop/compensation tests still green with the new optional `reason` param and the create-lock).
- `cd api && uv run mypy . --strict` — clean (61 source files).
- `cd api && uv run ruff check . && uv run ruff format --check .` — clean (61 files).
- `uvx --with charset-normalizer reuse lint` — 100% compliant (255/255 files; ADR-0010 + the new test carry SPDX headers).

_Tooling note: the bare `uvx reuse lint-file` invocation fails in this Windows env (`NoEncodingModuleError` — the optional charset module is absent). `uvx --with charset-normalizer reuse lint` is the working equivalent and reports the repo fully compliant; the SPDX headers were also byte-verified against ADR-0002's format._

## Next Phase Readiness
- **Plan 04-01 (reconciler) unblocked:** the three cadence Settings keys exist, `stopWorkspace(reason="idle")` is ready for the idle auto-stop to call, and ADR-0010 records the architecture the reconciler implements.
- **Deferred (per ADR-0010 / CONTEXT, dev-homelab smoke not CI):** real-Proxmox acceptance of capacity-under-concurrency; the `--workers >1` `BEGIN IMMEDIATE` backstop (only needed if a multi-process self-host topology is ever deployed).

## Self-Check: PASSED

- FOUND: api/tests/integration/test_capacity_race.py
- FOUND: docs/adr/ADR-0010-in-process-reconciler-and-capacity-lock.md
- FOUND: .planning/phases/04-hardening-release/04-02-SUMMARY.md
- FOUND commit: 9742908 (test RED), 81f94a1 (feat GREEN), a6ee94a (test), 15db872 (docs ADR)

---
*Phase: 04-hardening-release*
*Completed: 2026-06-11*
