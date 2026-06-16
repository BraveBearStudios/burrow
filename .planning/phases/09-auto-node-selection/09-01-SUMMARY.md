<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 09-auto-node-selection
plan: 01
subsystem: api
tags: [capacity, node-selection, pydantic-settings, fastapi, fake-provider, seam-discipline]

# Dependency graph
requires:
  - phase: 07-fast-reconcile
    provides: existing /nodes route, FakeComputeProvider, capacity guard, settings singleton
provides:
  - FakeComputeProvider optional node_fractions kwarg (per-node used-memory fraction with single-float fallback)
  - Settings.worker_nodes topology list (default derived from default_node via model_validator)
  - lib/capacity._fits(fraction, threshold) shared capacity comparator (strict > refuses, == eligible)
  - GET /api/v1/nodes enumerates worker_nodes via _fits, degrade-not-500 preserved per node
affects: [09-02 auto-select saga, 09-03 new-workspace modal]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shared pure-arithmetic capacity comparator (lib/capacity._fits) is the single source of truth for both the UI's displayed capacity and (Plan 02) the placement decision"
    - "Settings list default DERIVED from another field via pydantic model_validator(mode=after) + Field(default_factory=list) (never a shared mutable literal)"
    - "App-level Fake capacity varied in integration tests by class-level monkeypatch of getNodeMemory + settings monkeypatch (no Fake-injection kwarg seam)"

key-files:
  created:
    - api/lib/capacity.py
    - api/tests/unit/test_fake_node_fractions.py
    - api/tests/unit/test_node_capacity_helper.py
    - api/tests/integration/test_nodes_multinode.py
  modified:
    - api/compute/fakeProvider.py
    - api/config.py
    - api/routers/nodes.py

key-decisions:
  - "node_fractions is an OPTIONAL kwarg with single-float fallback (getNodeMemory does .get(node, self._node_memory)) so every existing Fake caller stays green"
  - "worker_nodes default is derived from default_node (not a hardcoded ['pve1']) so a BURROW_DEFAULT_NODE override propagates"
  - "_fits is fraction <= threshold (strict > refuses, boundary == eligible), pure arithmetic with no provider concrete import to keep the seam-leakage guard green"
  - "No new ComputeProvider ABC method, no listNodes, no ADR (LOCKED in 09-CONTEXT); /nodes iterates worker_nodes using only the existing getNodeMemory"

patterns-established:
  - "Single capacity comparator (T-09-01): /nodes and auto-select both call _fits so displayed capacity and placement decision cannot drift"
  - "Seam-clean helper module (T-09-02): lib/capacity is pure arithmetic, imports no driver symbol"

requirements-completed: [WSX-01]

# Metrics
duration: ~18min
completed: 2026-06-16
---

# Phase 9 Plan 01: Auto-Node-Selection Foundations Summary

**Per-node Fake fractions, a `worker_nodes` Settings list derived from `default_node`, and a shared `lib.capacity._fits` comparator wired into a multi-node `GET /api/v1/nodes` — the seam-clean primitives Plan 02 auto-select and Plan 03 modal build on.**

## Performance

- **Duration:** ~18 min (excluding full-suite runs)
- **Started:** 2026-06-16T06:41:08Z
- **Completed:** 2026-06-16
- **Tasks:** 2 (both TDD: failing-first)
- **Files modified:** 7 (3 source modified, 1 source created, 3 test files created)

## Accomplishments
- Extended `FakeComputeProvider` with an OPTIONAL `node_fractions: dict[str, float]` kwarg + per-node `getNodeMemory` lookup, with a single-float fallback so the multi-node selection matrix can be proven over the Fake — every existing caller unchanged.
- Added `Settings.worker_nodes` (a `Field(default_factory=list)` derived to `[default_node]` by a `model_validator(mode="after")`), the topology source auto-select iterates — with NO new `ComputeProvider` ABC method (LOCKED).
- Factored the single capacity comparator `_fits(fraction, threshold)` into `api/lib/capacity.py` (strict `>` refuses, boundary `==` eligible), pure arithmetic with no driver import.
- Refactored `GET /api/v1/nodes` to enumerate `settings.worker_nodes` and compute per-node `overThreshold` via the shared `_fits`, preserving the degrade-not-500 posture (a raising `getNodeMemory` → null fraction + `overThreshold=false` at HTTP 200).

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend FakeComputeProvider with optional per-node node_fractions** - `a6859f9` (feat)
2. **Task 2: worker_nodes Settings (derived) + shared _fits helper + multi-node /nodes** - `e984b66` (feat)

**Plan metadata:** (this commit) `docs(09-01): complete auto-node-selection foundations plan`

_Note: Both tasks were TDD (RED test written and confirmed failing, then GREEN implementation). Each task's failing-first test and its implementation were committed together as one atomic feature commit._

## Files Created/Modified
- `api/lib/capacity.py` - NEW. Shared `_fits(fraction, threshold)` comparator (`fraction <= threshold`); pure arithmetic, no provider/driver import; `__all__` exported.
- `api/compute/fakeProvider.py` - Added `node_fractions` optional kwarg + `_node_fractions` store; `getNodeMemory` returns `self._node_fractions.get(node, self._node_memory)`.
- `api/config.py` - Added `worker_nodes: list[str] = Field(default_factory=list)` + `model_validator(mode="after")` deriving the default from `default_node`; imported `model_validator`.
- `api/routers/nodes.py` - Imported `_fits`; `over_threshold = fraction is not None and not _fits(fraction, threshold)`; `list_nodes` iterates `settings.worker_nodes`; updated module docstring.
- `api/tests/unit/test_fake_node_fractions.py` - NEW. Per-node fraction + backward-compat (no-kwargs default, single-float fallback, absent-node fallback) coverage.
- `api/tests/unit/test_node_capacity_helper.py` - NEW. `_fits` boundary semantics + `worker_nodes` default-derivation/override coverage.
- `api/tests/integration/test_nodes_multinode.py` - NEW. Multi-node `/nodes` enumeration over `integration_client` (per-node `overThreshold` + degrade-not-500 on one failing node).

## Test Results
- **New trio** (`test_fake_node_fractions.py` + `test_node_capacity_helper.py` + `test_nodes_multinode.py`): **12 passed**.
- **Task-2 verify gate** (helper + multinode + original `test_nodes.py` + `test_seam_leakage.py`): **16 passed** (seam guard green).
- **Full api suite** (`uv run pytest -q`): **185 passed** (baseline 173 + 12 new tests; zero regressions).
- **Lint/typecheck:** `ruff check` clean, `mypy` clean on all touched source files.

## Decisions Made
None beyond the LOCKED contract — plan executed as specified. The `node_fractions`-with-float-fallback, derived `worker_nodes` default, and pure-arithmetic `_fits` were all dictated by 09-CONTEXT/09-RESEARCH and implemented exactly.

## Deviations from Plan

None - plan executed exactly as written.

The plan's verify commands say `python -m pytest`; per the invocation's environment note these were run as `uv run pytest` (the uv-managed env; bare python lacks `aiosqlite`). This is an environment invocation detail, not a code deviation.

## Issues Encountered
- The unit test initially imported `pytest` without using it (ruff F401). Removed the unused import; tests still green. Trivial, resolved during the lint step of Task 2.

## Known Stubs
None. All wiring is live: `worker_nodes` feeds `/nodes`, `_fits` is imported and used, the Fake reports real per-node values.

## User Setup Required
None - no external service configuration required. `worker_nodes` is an optional operator env override; the derived default keeps single-node configs working unchanged.

## Next Phase Readiness
- **Plan 02 (auto-select saga)** is unblocked: the Fake can now express a multi-node capacity matrix (`node_fractions`), `settings.worker_nodes` is the candidate list to iterate, and `_fits` is the shared comparator `selectNode` will reuse inside `_create_lock`.
- **Plan 03 (modal)** can rely on `/nodes` enumerating all candidate nodes so the UI shows every option.
- `wave_0_complete` (09-VALIDATION frontmatter) can flip true: the Fake `node_fractions` extension landed.

## Self-Check: PASSED

All created files verified present on disk (`api/lib/capacity.py`, the three new test files, this SUMMARY) and both task commits (`a6859f9`, `e984b66`) verified in git log.

---
*Phase: 09-auto-node-selection*
*Completed: 2026-06-16*
