<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 09-auto-node-selection
plan: 02
subsystem: api
tags: [capacity, node-selection, create-saga, asyncio-lock, fastapi, fake-provider, seam-discipline, pydantic]

# Dependency graph
requires:
  - phase: 09-auto-node-selection
    plan: 01
    provides: FakeComputeProvider node_fractions kwarg, settings.worker_nodes topology list, lib.capacity._fits shared comparator
provides:
  - WorkspaceCreate.node is Optional[str]=None (None/omitted = auto placement; explicit string = unchanged manual path)
  - WorkspaceService.selectNode() returning the least-loaded fitting node (tie by name asc, raising-node skip, _fits boundary eligible, no-fit -> CapacityError)
  - createWorkspace resolves the node ONCE inside _create_lock (select -> guard -> reserve atomic), persisting the chosen node on the row
  - CapacityError additive keyword-only message= for the no-fit manual-pick hint (single-arg CapacityError(node) callers unchanged)
affects: [09-03 new-workspace modal (auto-default + node dropdown)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Auto-placement resolved ONCE inside the existing _create_lock critical section so select->guard->reserve run on the same node (no overcommit window, ADR-0010 preserved)"
    - "Optional request field as the auto/manual signal (node: str|None=None) with no separate flag/sentinel; CamelModel still serializes camelCase"
    - "Additive keyword-only error message (CapacityError(message=...)) preserving existing positional callers and the invariant .code"
    - "End-to-end auto/manual integration via class-level monkeypatch of FakeComputeProvider.getNodeMemory + settings monkeypatch (no Fake-injection seam)"

key-files:
  created:
    - api/tests/unit/test_node_selection.py
    - api/tests/integration/test_create_auto_node.py
  modified:
    - api/models/workspace.py
    - api/lib/errors.py
    - api/services/workspaceService.py

key-decisions:
  - "selectNode runs INSIDE _create_lock, before the step-0 guard; node resolved to a guaranteed str so all downstream seam calls (getNodeMemory/cloneCt/startCt/getIp/_compensate) type-check and the persisted row never carries None"
  - "The existing step-0 capacity guard stays as the single authoritative threshold check both auto and manual paths pass through (auto already guaranteed _fits, but the guard is not bypassed)"
  - "_reserve_vmid_and_row takes an explicit node: str param and persists it (instead of payload.node) so the NOT NULL workspaces.node column always receives a concrete node"
  - "Manual path skips selectNode entirely (gated on payload.node is None) so it is byte-for-byte the prior behavior"

patterns-established:
  - "Auto-placement atomicity (T-09-01): selection + guard + reservation in one _create_lock section; no-fit refuses before reservation so no orphan row"
  - "Seam-clean selectNode (T-09-02): references only getNodeMemory, settings.worker_nodes, _fits, CapacityError — seam-leakage guard stays green"

requirements-completed: [WSX-01]

# Metrics
duration: ~20min
completed: 2026-06-16
---

# Phase 9 Plan 02: Auto Node Selection in the Create Saga Summary

**`WorkspaceCreate.node` becomes optional and `createWorkspace` auto-selects the least-loaded fitting node (via `selectNode`) once inside `_create_lock` — select → capacity guard → VMID reserve stay one atomic critical section, the manual pick is unchanged, and a no-fit refuses with the `capacity_exceeded` envelope before any row is reserved.**

## Performance

- **Duration:** ~20 min (excluding the 2m53s full-suite run)
- **Started:** 2026-06-16T07:10Z (approx; continuation of a prior executor's Task 1)
- **Completed:** 2026-06-16
- **Tasks:** 2 (both TDD: failing-first). Task 1 was completed-but-uncommitted by a prior executor; this executor verified it, did Task 2, and committed both atomically.
- **Files modified:** 5 (3 source modified, 2 test files created)

## Accomplishments
- Wired auto node selection into the create saga: inside the existing `async with self._create_lock:` block, `node = payload.node if payload.node is not None else await self.selectNode()` resolves the target node ONCE to a guaranteed `str`, then threads it through the step-0 capacity guard, `_reserve_vmid_and_row`, clone, start, `getIp`, and compensation. Selection is explicitly commented as do-not-move-outside-the-lock.
- Resolved all 5 mypy `str | None` → `str` errors that the Optional model field (Task 1) had introduced, by replacing every downstream `payload.node` with the resolved local `node`.
- Persisted the chosen node on the reserved row: `_reserve_vmid_and_row` now takes an explicit `node: str` and writes it to the NOT NULL `workspaces.node` column (was `payload.node`, which is now nullable).
- Added the end-to-end integration matrix (`test_create_auto_node.py`, criterion 5): auto picks least-loaded over the app; manual pick unchanged (with `selectNode` asserted never-called); auto no-fit → `capacity_exceeded` envelope + zero persisted rows; persisted row's node == the selected node.

## Task Commits

1. **Task 1 (model + errors + selectNode + unit matrix) and Task 2 (saga wiring + integration matrix)** — `15e6db6` (feat)

**Plan metadata:** (this commit) `docs(09-02): complete auto node selection plan`

_Note: Both tasks were TDD (RED confirmed, then GREEN). Task 1's model/errors/selectNode/unit-test were completed-but-uncommitted by a prior executor. Because the Optional model field makes mypy RED until the saga is wired (Task 2), the two slices were committed together as ONE atomic commit so the commit boundary is mypy + pytest GREEN (never a RED-mypy intermediate)._

## Files Created/Modified
- `api/models/workspace.py` — `WorkspaceCreate.node` is `str | None = None` (None/omitted = auto). [Task 1, verified]
- `api/lib/errors.py` — `CapacityError.__init__(self, node=None, *, message=None)`: additive keyword-only `message` for the no-fit hint; positional `CapacityError(node)` and `.code = "capacity_exceeded"` unchanged. [Task 1, verified]
- `api/services/workspaceService.py` — `selectNode()` (Task 1, verified) + saga wiring (Task 2): resolve `node` once inside `_create_lock` before the step-0 guard; thread `node` through guard/reserve/clone/start/getIp/compensate; `_reserve_vmid_and_row(payload, node)` persists the chosen node.
- `api/tests/unit/test_node_selection.py` — NEW. The seven-behavior selection matrix (least-loaded, over-threshold skip, boundary eligible, tie→name asc, no-fit→CapacityError+no row, raising-node skip, all-raising→CapacityError) + the Optional-model cases. [Task 1, verified — 10 passed]
- `api/tests/integration/test_create_auto_node.py` — NEW. End-to-end over `integration_client`: auto least-loaded, manual unchanged, auto no-fit→`capacity_exceeded`+no orphan, persisted-node==selected.

## Test Results
- **Criterion-5 unit + integration** (`test_node_selection.py` + `test_create_auto_node.py`): **14 passed**.
- **Task-2 verify gate** (`test_create_auto_node` + `test_node_selection` + `test_create_saga` + `test_capacity_guard` + `test_capacity_race` + `test_seam_leakage`): **30 passed** (manual path, in-lock atomicity, concurrent-create serialization, and seam guard all unbroken).
- **Full api suite** (`uv run pytest -q`): **199 passed** (baseline 185 from Plan 01 + Task 1's 10 unit + 4 new integration tests; zero regressions). 11 warnings are a pre-existing websockets `ws_handler` DeprecationWarning, out of scope.
- **Typecheck:** `uv run mypy services/workspaceService.py models/workspace.py lib/errors.py lib/capacity.py` → 0 errors (the 5 `str | None` errors resolved).
- **Lint:** `uv run ruff check .` → clean.

## Decisions Made
None beyond the LOCKED contract — plan executed as specified. The in-lock placement, the resolve-once-to-str approach, the additive `CapacityError(message=...)`, and the explicit-`node`-param to `_reserve_vmid_and_row` were all dictated by the plan's `<interfaces>` and `<task_2>` and implemented exactly.

## Deviations from Plan

None - plan executed exactly as written.

The plan's verify commands say `python -m pytest` / `python -m mypy`; per the invocation's environment note these were run as `uv run pytest` / `uv run mypy` (the uv-managed env; bare python lacks `aiosqlite`/mypy). This is an environment invocation detail, not a code deviation. The integration no-fit test asserts HTTP `409` (the capacity router's mapped status for `capacity_exceeded`), confirmed against the live error-mapping rather than the plan's generic "4xx".

## Issues Encountered
None. RED was confirmed for both the unit matrix (Task 1, already present) and the integration matrix (3 auto-path tests failed with `NOT NULL constraint failed: workspaces.node`, proving the saga did not yet auto-select; the manual-path test passed, proving the manual path was already correct). The saga wiring turned all GREEN with no debugging iterations.

## Known Stubs
None. The wiring is live end-to-end: an omitted node is resolved by `selectNode`, the chosen node passes the real capacity guard, is persisted on the row, and drives the real clone/start/getIp tail over the Fake.

## Threat Surface Scan
No new security-relevant surface beyond the plan's `<threat_model>`. The change introduces no new endpoint, auth path, or trust boundary: `node` (client input) flows through the EXISTING step-0 guard and the seam-confined `getNodeMemory`; the no-fit path fails closed before reservation (T-09-01); `selectNode` references no driver symbol (T-09-02, seam guard green); a manual node string still surfaces the typed `capacity_exceeded` envelope, never a 500 oracle (T-09-03).

## User Setup Required
None - no external service configuration required. `worker_nodes` (from Plan 01) is the optional operator topology override; the derived single-node default keeps existing configs auto-selecting their one node unchanged.

## Next Phase Readiness
- **Plan 03 (new-workspace modal)** is unblocked: the backend now accepts `node: null` to mean auto, returns the auto-selected node on the created row, and `/nodes` (Plan 01) enumerates the candidate list — so the modal can default to "Auto (least-loaded)" with an explicit node dropdown and round-trip both paths.
- WSX-01 backend is complete: auto-select + manual pick + no-overcommit + seam-clean + in-lock atomic, all proven unit + end-to-end.

## Self-Check: PASSED

All created files verified present on disk (`api/tests/unit/test_node_selection.py`, `api/tests/integration/test_create_auto_node.py`, this SUMMARY) and the task commit (`15e6db6`) verified in git log.

---
*Phase: 09-auto-node-selection*
*Completed: 2026-06-16*
