<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

---
phase: 10-persistence-data-model-reaper-carve-out
plan: 01
subsystem: testing
tags: [proxmoxer, responses, integration-test, upid, compute-provider, mock]

# Dependency graph
requires:
  - phase: 00-foundation
    provides: ProxmoxComputeProvider + ComputeProvider ABC + ComputeTask model
  - phase: 01
    provides: real-clone saga whose UPID-block + idempotent-destroy paths this tier exercises
provides:
  - "Mocked-proxmoxer integration tier (TEST-01 hard gate) closing the Fake-vs-real proxmoxer gap"
  - "mock_proxmox factory module: make_upid / register_task_poll / resource_exception over the responses substrate"
  - "Self-tests driving the REAL ProxmoxComputeProvider through running->stopped UPID polling + ResourceException 404/500 branches"
affects: [10-persistence-data-model, persistence-compute, plan-10-03, plan-10-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "responses (NOT respx) mocks the proxmoxer requests leg; factories register N running -> 1 stopped status GETs to model an async UPID task"
    - "responses.add(..., body=<ResourceException>) raises a factory-built proxmoxer error at the transport leg to drive the provider's defensive inspector branches"

key-files:
  created:
    - api/tests/integration/mock_proxmox.py
    - api/tests/integration/test_mock_proxmox.py
  modified: []

key-decisions:
  - "Factories only (no shared pytest fixture) — YAGNI/CONTEXT-locked until a second consumer appears"
  - "ResourceException branches driven via responses body=<exc> (factory object raised at transport) rather than an HTTP status code proxmoxer would reconstruct — exercises the exact factory shape against _is_not_found / _is_running_or_locked"
  - "startCt's non-OK exitstatus surfaces TaskFailedError (not LxcNotReadyError) — _block runs outside startCt's POST-only try/except, so the typed _block error propagates directly"

patterns-established:
  - "Mocked-proxmoxer tier: 9-segment UPID via make_upid + ordered running->stopped status GETs is the canonical way to exercise real _block polling under responses"

requirements-completed: [TEST-01]

# Metrics
duration: 8min
completed: 2026-06-25
---

# Phase 10 Plan 01: Mocked-Proxmoxer Integration Tier (TEST-01) Summary

**A `responses`-backed factory module + self-tests that drive the REAL `ProxmoxComputeProvider` through running->stopped UPID polling and `proxmoxer.core.ResourceException` 404/500 branches — the exact paths the in-memory Fake never triggers.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-06-25T09:48:43Z
- **Completed:** 2026-06-25T09:56:54Z
- **Tasks:** 2
- **Files modified:** 2 (both created)

## Accomplishments

- Closed the v1.3 HARD GATE (STATE blockers gate #2): the structural Fake-vs-real proxmoxer gap. The Fake returns `ComputeTask(upid=None, status="ok")` instantly; this tier exercises the real `_block` UPID polling and `ResourceException` inspector branches over mocked HTTP.
- `mock_proxmox.py` factory module: `make_upid` (verified 9-colon-segment UPID `decode_upid` accepts), `register_task_poll` (N `running` then one `stopped` status GET, modeling an async task completing after N polls), `resource_exception` (verified `ResourceException(status_code, message, content)` constructor).
- Four self-tests over `@responses.activate` driving the REAL provider: (1) `startCt` blocks on a `running`x2 -> `stopped` UPID and returns ok/OK/upid; (2) a 404 `ResourceException` drives `destroyCt`'s idempotent `_is_not_found` branch; (3) a 500 "CT is running" `ResourceException` drives the stop-then-destroy `_is_running_or_locked` retry; (4) a non-OK exitstatus surfaces a typed `TaskFailedError` from `_block`.
- `responses` only, never `respx` (proxmoxer rides `requests`); both files ruff- and mypy-clean. Unblocks the persistence-compute work in Plans 03/04.

## Task Commits

Each task was committed atomically:

1. **Task 1: mock_proxmox.py factory module** - `a5f732c` (test)
2. **Task 2: test_mock_proxmox.py self-tests (drive REAL provider)** - `1826d77` (test)

**Plan metadata:** see final docs commit.

_Note: This is a `type: tdd` task pair authoring tests against an already-correct, pre-existing real provider — the deliverable is the gate-proving test, so both commits are `test(...)`. No new `feat` was required because the provider implementation already exists and is correct._

## Files Created/Modified

- `api/tests/integration/mock_proxmox.py` - Factory module: `make_upid` / `register_task_poll` / `resource_exception` over the `responses` substrate; imports `from proxmoxer.core import ResourceException`; never `respx`.
- `api/tests/integration/test_mock_proxmox.py` - Self-tests driving the REAL `ProxmoxComputeProvider.startCt`/`destroyCt` through `_block` UPID polling + 404/500 `ResourceException` branches; `_Settings` stub + `_provider(host)` helper mirror the verified analog.

## Decisions Made

- **Factories only, no shared fixture** — YAGNI / CONTEXT-locked; promote to a pytest fixture only when a second consumer appears.
- **ResourceException via `body=<exc>`** — Registering the factory-built exception as the `responses` body raises that exact object at the transport leg, so the provider's `_is_not_found` / `_is_running_or_locked` inspectors run against the precise factory shape (a stronger gate-proof than an HTTP status code proxmoxer would reconstruct into its own exception).
- **Non-OK exitstatus expects `TaskFailedError`** — `_block` is called outside `startCt`'s POST-only `try/except`, so its typed `TaskFailedError` propagates directly rather than being wrapped as `LxcNotReadyError`. This is correct existing provider behavior (verified against `proxmoxProvider.py:241-248, 67-96`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected expected exception type in the non-OK exitstatus self-test**
- **Found during:** Task 2 (self-tests)
- **Issue:** The initial draft of `test_real_provider_start_raises_on_non_ok_exitstatus` asserted `pytest.raises(LxcNotReadyError)`, but the real `startCt` only wraps its POST leg in that try/except; the subsequent `_block` call raises `TaskFailedError` directly on a stopped-but-non-OK task. The test failed against the (correct) existing provider.
- **Fix:** Imported `TaskFailedError` instead of `LxcNotReadyError` and asserted on it; updated the test docstring to record why (`_block` runs outside the POST-only guard).
- **Files modified:** `api/tests/integration/test_mock_proxmox.py`
- **Verification:** `uv run pytest tests/integration/test_mock_proxmox.py -x` -> 4 passed; ruff + mypy clean.
- **Committed in:** `1826d77` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 test-author bug)
**Impact on plan:** The fix aligned the test's expectation with the existing-correct provider's typed-error contract. No production code changed; no scope creep.

## Issues Encountered

None beyond the deviation above. The two extra ResourceException self-tests and the UPID round-trip passed on first run; only the fourth (exception-type) assertion needed correction.

## Deferred Issues

Pre-existing, out of scope for this plan (logged in `deferred-items.md`):
- `api/tests/unit/test_node_selection.py:156-158` — 3 mypy `LogRecord has no attribute` errors from Phase 9 commit `759a5d6`. Not caused by Plan 10-01; both new files are ruff- and mypy-clean. `uv run ruff check .` is fully green; the only mypy hits in the package are this pre-existing file.

## User Setup Required

None - no external service configuration required (hermetic, zero outbound network; illustrative placeholders only, no real host/secret).

## Next Phase Readiness

- TEST-01 gate is GREEN: the mocked-proxmoxer tier exists and drives the REAL provider through UPID `running`->`stopped` polling + `ResourceException` shapes the Fake never reaches. Plans 03/04 (persistence-compute) are unblocked.
- The `mock_proxmox` factories are the canonical substrate for any later test needing real proxmoxer UPID/error paths in this phase.
- Remaining Phase 10 work (003 migration, model/provider/saga `persistent` threading, reaper carve-out comment + negative-control tests, ADRs, e2e W2/W3) is independent of this tier and can proceed.

---
*Phase: 10-persistence-data-model-reaper-carve-out*
*Completed: 2026-06-25*

## Self-Check: PASSED

- FOUND: `api/tests/integration/mock_proxmox.py`
- FOUND: `api/tests/integration/test_mock_proxmox.py`
- FOUND: `.planning/phases/10-persistence-data-model-reaper-carve-out/10-01-SUMMARY.md`
- FOUND commit: `a5f732c` (Task 1 — factory module)
- FOUND commit: `1826d77` (Task 2 — self-tests)
