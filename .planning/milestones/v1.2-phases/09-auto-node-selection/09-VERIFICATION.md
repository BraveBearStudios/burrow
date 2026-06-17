<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 09-auto-node-selection
verified: 2026-06-16T08:35:00Z
status: passed
score: 5/5 roadmap success criteria verified (16/16 plan must-have truths)
overrides_applied: 0
re_verification:
  previous_status: none
  note: initial verification (no prior VERIFICATION.md)
deferred:
  - truth: "Auto-select across REAL multiple Proxmox nodes with real RAM load on a live cluster"
    addressed_in: "ACC-01 (dev-homelab smoke)"
    evidence: "ROADMAP Phase 9 success criterion 5 explicitly fences real multi-node validation as the deferred ACC-01 dev-homelab smoke; REQUIREMENTS.md ACC-01 lists 'the WSX-01 multi-node selection on real nodes'. CI-provable behavior over the Fake's multi-node capacity is fully covered."
---

# Phase 9: Auto Node Selection Verification Report

**Phase Goal:** When the operator creates a workspace without picking a node, the control plane chooses the least-loaded node that still passes the node-RAM capacity threshold — proven over the FakeComputeProvider's multi-node capacity — while manual node pick remains available and the `ComputeProvider` seam stays free of Proxmox specifics.
**Verified:** 2026-06-16T08:35:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria — the contract)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Operator supplies no node → control plane auto-selects a capacity-fitting node, preferring the least-loaded | VERIFIED | `workspaceService.py:153` resolves `node = payload.node if payload.node is not None else await self.selectNode()`; `selectNode` (`:235-266`) collects `(fraction, node)` where `_fits`, sorts by `(fraction, name)`, returns least-loaded. Tests: `test_selects_least_loaded_fitting_node`, `test_auto_picks_least_loaded_fitting_node` (integration) — PASS |
| 2 | No node passes threshold → create refused with the existing capacity envelope error (no overcommit) | VERIFIED | `selectNode:258-263` raises `CapacityError(message=...)` when `fitting` is empty; the guard (`:160`) never lets an over-threshold node through. Tests: `test_no_fit_raises_capacity_error_with_manual_pick_hint`, `test_auto_no_fit_refuses_with_capacity_envelope_and_no_orphan` (asserts `error.code == capacity_exceeded`, HTTP 409, zero rows) — PASS |
| 3 | Manual node selection still works end-to-end, unchanged | VERIFIED | Manual path gated on `payload.node is None` so a string skips `selectNode` entirely; `test_manual_node_pick_is_unchanged_end_to_end` fails `selectNode` loudly if wrongly called and PASSES, proving it is not consulted on the manual path |
| 4 | Selection depends only on the ComputeProvider capacity surface — no Proxmox detail leaks past the seam; seam-leakage guard green | VERIFIED | `selectNode` references only `getNodeMemory`, `settings.worker_nodes`, `_fits`, `CapacityError`. `lib/capacity.py` is pure arithmetic (no imports of any provider concrete). `ComputeProvider` ABC unchanged — no `listNodes` added (`rg listNodes api/` → none). `test_seam_leakage.py` (4 tests) — PASS |
| 5 | Proven over the FakeComputeProvider's multi-node capacity (least-loaded chosen, over-threshold skipped, no-fit refuses); real multi-node is the deferred ACC-01 smoke | VERIFIED (CI scope) / DEFERRED (real cluster) | The criterion-5 matrix is fully covered by 33 phase-9 tests over the Fake's `node_fractions`. Real-cluster validation correctly deferred to ACC-01 per the criterion's own fence (see Deferred Items) |

**Score:** 5/5 ROADMAP success criteria verified (real-cluster behavior correctly deferred, not a gap).

### Plan Must-Have Truths (16, all VERIFIED)

Plan 09-01 (5): per-node `node_fractions` + backward-compat float; `_fits` single comparator; `worker_nodes` derived default; `/nodes` enumerates `worker_nodes` via `_fits`. All confirmed in source + tests (`test_fake_node_fractions.py` 4, `test_node_capacity_helper.py` 8, `test_nodes_multinode.py` 2 — PASS).

Plan 09-02 (7): least-loaded auto-select; over-threshold skip; raising-node skip; boundary `==` eligible; tie→name asc; no-fit→`capacity_exceeded` (no overcommit); manual unchanged; selection inside `_create_lock` + seam green. Confirmed (`test_node_selection.py` 11, `test_create_auto_node.py` 4 — PASS).

Plan 09-03 (4): modal defaults to Auto (no first-node-on-mount); Auto submits `node: null`; manual still works; form valid with Auto. Confirmed (`NewWorkspaceModal.test.tsx` WSX-01 block 3 + 6 existing — 9 PASS).

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | Auto-select across REAL multiple Proxmox nodes on a live cluster | ACC-01 (dev-homelab smoke) | ROADMAP Phase 9 SC-5 explicitly fences it; REQUIREMENTS.md ACC-01 = "the WSX-01 multi-node selection on real nodes". Not a gap. |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `api/services/workspaceService.py` | `selectNode()` inside `_create_lock`; resolve-once-to-str; threads chosen node | VERIFIED | `:144` lock, `:153` resolve, `:160` guard via `_fits`, `:214-266` `selectNode`; in-lock placement commented do-not-move |
| `api/lib/capacity.py` | shared `_fits` (`<=`), pure arithmetic | VERIFIED | `:21-23` `fraction <= threshold`, `__all__`, no driver import |
| `api/lib/errors.py` | `CapacityError` additive keyword `message=`, `.code` invariant | VERIFIED | `:66` `__init__(self, node=None, *, message=None)`; promotes to `safe_message`; `code="capacity_exceeded"` |
| `api/config.py` | `worker_nodes` derived default + normalization | VERIFIED | `:54` `Field(default_factory=list)`, `:107-126` validator strips/dedups/drops-empty, defaults `[default_node]` |
| `api/routers/nodes.py` | `/nodes` iterates `worker_nodes` via `_fits` | VERIFIED | `:26` imports `_fits`, `:48` `not _fits(...)`, `:62` iterates `settings.worker_nodes` |
| `api/models/workspace.py` | `WorkspaceCreate.node: str \| None = None` | VERIFIED | `:46` Optional with None default |
| `api/compute/fakeProvider.py` | optional `node_fractions` kwarg + per-node lookup | VERIFIED | `:71` kwarg, `:209` `.get(node, self._node_memory)`; existing callers unchanged |
| `api/compute/provider.py` | ABC unchanged (no `listNodes`) | VERIFIED | only `getNodeMemory` (`:153`); no enumeration method; no ADR-0011 |
| `ui/src/types/workspace.ts` | `node?: string \| null` | VERIFIED | `:41` optional, mirrors backend |
| `ui/src/components/NewWorkspaceModal.tsx` | Auto default option; drop first-node-on-mount; Auto→null | VERIFIED | `:186` `""` default (no setNode effect), `:227` `isValid` drops node, `:244` `node: node \|\| null`, `:425` Auto option first |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `workspaceService.selectNode` | `settings.worker_nodes` + `getNodeMemory` | iterate + read | WIRED | `:240-242` |
| `workspaceService` | `lib.capacity._fits` | shared comparator (select + guard) | WIRED | `:33` import, `:160` guard, `:247` selection |
| `workspaceService` | `lib.errors.CapacityError` | no-fit raise with hint | WIRED | `:258` `raise CapacityError(message=...)` |
| `routers/nodes` | `lib.capacity._fits` | import + use | WIRED | `:26`/`:48` |
| `main._service_error_handler` | `CapacityError.safe_message` | surface hint at wire | WIRED | `main.py:209` prefers `safe_message` (WR-01 fix) |
| `NewWorkspaceModal` | `useCreateWorkspace` | submit `node: node \|\| null` | WIRED | `:238-245` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `/nodes` route | per-node capacity rows | `compute.getNodeMemory(n)` over `worker_nodes` | Real fraction (Fake `node_fractions` / Proxmox live) | FLOWING |
| `selectNode` chosen node | `fitting[0][1]` | `getNodeMemory` fractions filtered by `_fits` | Real least-loaded node persisted on the row | FLOWING |
| `NewWorkspaceModal` node select | `nodes` from `useNodes()` | `GET /api/v1/nodes` | Real candidate list (Auto + per-node options) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full API suite green | `uv run pytest -q` | 202 passed, 11 warnings (pre-existing websockets deprecation) | PASS |
| Phase-9 selection + seam matrix | `uv run pytest <9 files> -v` | 33 passed | PASS |
| API typecheck | `uv run mypy <7 phase-9 files>` | Success: no issues in 7 files | PASS |
| API lint | `uv run ruff check .` | All checks passed | PASS |
| Full UI suite green | `npx vitest run` | 117 passed (15 files) | PASS |
| Modal Auto/manual suite | `npx vitest run NewWorkspaceModal.test.tsx` | 9 passed | PASS |
| UI typecheck | `npx tsc --noEmit` | exit 0, no errors | PASS |
| UI lint | `npx biome ci .` | clean (50 files) | PASS |

### Probe Execution

No conventional `scripts/*/tests/probe-*.sh` and no probe markers declared in the phase plans/summaries. N/A for this phase (covered by the pytest/vitest suites above).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| WSX-01 | 09-01, 09-02, 09-03 | Workspace creation can auto-select the worker node (least-loaded passing the RAM threshold) proven over the Fake's multi-node capacity; manual pick retained; real multi-node = dev-homelab smoke | SATISFIED | All 5 ROADMAP SCs verified; REQUIREMENTS.md maps WSX-01 → Phase 9; the real-cluster clause is correctly the deferred ACC-01 |

No orphaned requirements: REQUIREMENTS.md maps only WSX-01 to Phase 9, and all three plans declare `requirements: [WSX-01]`.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | — | No TBD/FIXME/XXX in any phase-9 source file | — | BLOCKER gate clean |
| (none) | — | No TODO/HACK/PLACEHOLDER stubs; `placeholder` matches are React input attrs only | — | No stubs |

No empty-return stubs, no hardcoded-empty render data, no unwired components. The auto path is live end-to-end (omitted node → `selectNode` → guard → reserve → clone/start over the Fake; UI Auto sentinel → `node: null` → server auto-fills).

### Code Review Disposition (09-REVIEW.md: 0 critical, 2 warning, 4 info)

| Finding | Disposition | Verified |
|---------|-------------|----------|
| WR-01 (auto no-fit message discarded at wire / misleading "selected node") | FIXED | `main.py:209` prefers `safe_message`; `selectNode` message contains "manually"; `test_create_auto_node.py:131-135` asserts `"manually" in body` AND `"selected node" not in body` end-to-end |
| WR-02 (`worker_nodes` empty/dup not normalized) | FIXED | `config.py:107-126` strip/drop-empty/dedup validator; `test_worker_nodes_normalizes_whitespace_empties_and_dupes` PASS |
| IN-02 (guard bypassed shared `_fits`) | FIXED | guard now `not _fits(...)` (`:160`) — genuinely one comparator |
| IN-03 (no-fit diagnosability) | FIXED | `selectNode:251-257` logs considered nodes + fractions |
| IN-04 (weak UI null assertion) | FIXED | `NewWorkspaceModal.test.tsx:258` `toHaveProperty("node", null)` |
| IN-01 (create returns 200 while MSW/UI doubles use 201) | DEFERRED to backlog (info) | Does not affect WSX-01: production client branches on `body.error` not status; real integration test asserts 200 against the live route; both suites green. Test-double consistency nit only |

### Human Verification Required

None for the CI-provable scope. The single manual-only behavior (auto-select across real multiple Proxmox nodes with live RAM load) is the explicitly deferred **ACC-01 dev-homelab smoke** fenced by ROADMAP SC-5 — recorded as a deferred item, not a human-verification gate for this phase.

### Gaps Summary

No gaps. Every ROADMAP success criterion and every plan must-have truth is observably true in the codebase and proven by tests run in this verifier's own process (API 202 passed, UI 117 passed, mypy/ruff/tsc/biome all clean). The seam stays Proxmox-free (no `listNodes`, no ADR-0011, seam-leakage guard green). The one info-level review nit (IN-01, 200 vs 201 in test doubles) does not affect goal achievement and is deferred to the backlog. Real multi-node Proxmox validation is correctly deferred to ACC-01 per the criterion's own scope fence.

---

_Verified: 2026-06-16T08:35:00Z_
_Verifier: Claude (gsd-verifier)_
