<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
# Phase 9: Auto Node Selection - Research

> Distilled from 4 parallel codebase scouts (create-saga, compute-seam, nodes-api, create-modal).
> All file:line references verified against the live tree during scouting.

## Summary

WSX-01 inserts a least-loaded-fitting node selection into the create path when the operator
supplies no node. The cleanest seam-clean approach (LOCKED in CONTEXT): a Settings `worker_nodes`
topology list iterated with the existing `ComputeProvider.getNodeMemory(node)` — NO new ABC
method, NO ADR, seam-leakage guard stays green. Selection runs inside the existing `_create_lock`
critical section so select -> capacity guard -> VMID reserve stays atomic (ADR-0010). Proven over
the FakeComputeProvider extended with per-node fractions. Real multi-node Proxmox is deferred
ACC-01 homelab smoke.

## Architectural Responsibility Map

| Layer | File | Role in Phase 9 |
|-------|------|-----------------|
| Settings | `api/config.py` (~59 threshold, + new `worker_nodes`) | Source of the candidate-node list (default `[default_node]`) + the 0.80 threshold |
| Seam (ABC) | `api/compute/provider.py` (`getNodeMemory` ~153) | UNCHANGED — the only capacity method auto-select calls |
| Fake | `api/compute/fakeProvider.py` (`__init__` ~67, `getNodeMemory` ~200) | Extend with optional `node_fractions: dict[str,float]` to prove multi-node selection |
| Service | `api/services/workspaceService.py` (`createWorkspace` ~129, `_create_lock` ~126, guard ~145, reserve ~196) | New `selectNode()` called inside the lock when `payload.node is None`; existing guard runs on the chosen node |
| Capacity helper | `api/routers/nodes.py` (`_node_capacity` ~30-48, strict `>` ~42) | Factor a shared `_fits(fraction, threshold)` used by `/nodes` AND auto-select |
| API model | `api/models/workspace.py` (`WorkspaceCreate.node` ~41) | `node` becomes `Optional[str] = None` (None = auto) |
| Router | `api/routers/workspaces.py` (POST ~26-33) | Passes payload through; `/nodes` route iterates `worker_nodes` not `[default_node]` |
| UI | `ui/src/components/NewWorkspaceModal.tsx` (select ~417, node state ~183, first-node default ~211-215, validity ~230, submit ~241) | Add "Auto (least-loaded)" as default option; drop first-node default; send `node: null` for Auto |
| UI types/hooks | `ui/src/types/workspace.ts` (`WorkspaceCreate.node` ~39), `ui/src/hooks/useNodes.ts`, `useWorkspaces.ts` (`useCreateWorkspace` ~39) | `node` becomes optional in the create payload type |

## The selection algorithm (LOCKED shape)

```
selectNode():                       # service method, called inside _create_lock when node is None
  candidates = settings.worker_nodes # topology config; default [default_node]
  fitting = []
  for n in candidates:
    try: f = await getNodeMemory(n)  # the ONLY seam call
    except: continue                 # skip unreachable (mirrors /nodes degrade-not-500)
    if _fits(f, threshold):          # shared helper: f <= threshold (strict > refuses; == allowed)
      fitting.append((f, n))
  if not fitting: raise CapacityError("All nodes at capacity. Pick a node manually to override.")
  fitting.sort(key=lambda fn: (fn[0], fn[1]))   # least fraction, tie -> node name ascending
  return fitting[0][1]
```

## Pitfalls (must respect)

1. **Lock placement.** Selection MUST run INSIDE `_create_lock` (not before acquire). The two
   scouts disagreed; resolved to inside for atomicity-by-construction. Do NOT "optimize" it
   outside the lock — keep select -> guard -> reserve in one serialized section (ADR-0010).
2. **Threshold comparison is strict `>` refuse, `==` allowed.** `_fits` must be `fraction <=
   threshold`. A node at exactly 0.80 is ELIGIBLE (boundary-tested in test_capacity_guard.py).
3. **Seam leakage.** `selectNode` lives in the service and calls ONLY `getNodeMemory` + reads
   `settings.worker_nodes`. No proxmoxer/ProxmoxAPI symbol may appear outside `proxmoxProvider.py`
   (test_seam_leakage.py ~71 tokenizes and asserts). Do not import provider concretes.
4. **Fake backward-compat.** `FakeComputeProvider()` and `FakeComputeProvider(node_memory=0.25)`
   MUST keep working — `node_fractions` is an OPTIONAL kwarg with float fallback. Every existing
   conftest fixture stays green.
5. **`/nodes` route must enumerate `worker_nodes`,** not just `[default_node]`, so the UI shows all
   nodes and the displayed capacity matches the auto-select decision (shared `_fits`).
6. **Modal validity + default.** Removing the first-node-default-on-mount (~211-215) must not
   break form validity (~230); "Auto" is a valid selection that sends `node: null`/omits it.
7. **camelCase boundary.** New Settings key is snake_case (`worker_nodes`); `WorkspaceCreate.node`
   Optional serializes camelCase via the existing `CamelModel`/`by_alias=True`. No hand-mapping.

## Don't Hand-Roll / Reuse

- Reuse the existing `CapacityError` (`capacity_exceeded` code) for no-fit — no new error type.
- Reuse the existing per-node capacity computation (`_node_capacity`) by factoring `_fits` out of
  it; do not duplicate the threshold comparison.
- Reuse the existing `_create_lock`, guard, reserve, and compensation tail unchanged.

## Validation Architecture

> `nyquist_validation` enabled. New backend test code (pytest, unit + integration tiers over the
> Fake) + UI vitest for the modal option. Real multi-node Proxmox = deferred ACC-01 homelab smoke.

### Test Framework
| Property | Value |
|----------|-------|
| Backend | pytest (existing `api/tests/unit` + `api/tests/integration`); Fake extended with `node_fractions` |
| Frontend | vitest + MSW (existing `ui` harness) for the modal Auto option |
| Quick run | `cd api && python -m pytest tests/unit/test_node_selection.py -q` |
| Full suite | `cd api && python -m pytest -q` then `cd ui && npx vitest run` |

### Phase Requirements -> Test Map (criterion 5 matrix, all over the Fake's multi-node capacity)
| Behavior | Test | Tier |
|----------|------|------|
| No node supplied -> least-loaded-fitting node chosen | `node_fractions={pve1:0.6, pve2:0.3, pve3:0.5}` -> selects `pve2` | unit |
| Over-threshold node skipped | `{pve1:0.9, pve2:0.3}` -> selects `pve2`, never `pve1` | unit |
| Boundary node at exactly threshold is eligible | `{pve1:0.80}` -> selects `pve1` (== allowed) | unit |
| Tie among equally-loaded -> name ascending | `{pve2:0.4, pve1:0.4}` -> selects `pve1` | unit |
| No fit (all over threshold) -> CapacityError, no overcommit | `{pve1:0.95, pve2:0.9}` -> raises `CapacityError` | unit |
| Manual pick still works end-to-end | explicit `node="pve3"` -> saga uses pve3 unchanged | integration |
| Auto path end-to-end | `node=None` -> create succeeds on the selected node | integration |
| Seam-leakage guard stays green | `test_seam_leakage` passes with the new selection code | unit |
| `/nodes` enumerates `worker_nodes` + shares `_fits` | multi-node `/nodes` response matches selection eligibility | integration |
| Modal: Auto is the default + sends null; manual still selectable | vitest render + submit assertions | unit (ui) |

## Assumptions Log
| # | Claim | Risk if wrong |
|---|-------|---------------|
| A1 | `worker_nodes` defaults to `[default_node]` so single-node configs + existing tests stay green | LOW — one-line Settings default |
| A2 | Reserving a VMID does not change `getNodeMemory` (Fake fractions are static) -> inside-vs-outside lock is not a v1 correctness divider; inside chosen for clarity | LOW — documented; real RAM accounting is deferred |
| A3 | The `/nodes` route can iterate `worker_nodes` without a seam change (it already calls `getNodeMemory` per node) | LOW — verified in nodes.py |

## Open Questions
- None blocking. Real multi-node Proxmox enumeration (if `worker_nodes` static config proves
  insufficient) is the deferred dynamic-discovery `listNodes()` path (ADR-0011), explicitly out of
  v1.2 scope per CONTEXT.

## Environment Availability
| Dependency | Available | Note |
|------------|-----------|------|
| pytest + Fake | ✓ | extend Fake with `node_fractions`; all CI-provable on dev box |
| vitest + MSW | ✓ | existing ui harness |
| Real multi-node Proxmox | ✗ | deferred ACC-01 homelab smoke (by design) |
