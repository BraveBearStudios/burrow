<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
# Phase 9: Auto Node Selection - Context

**Gathered:** 2026-06-16
**Status:** Ready for planning
**Mode:** Smart discuss (autonomous, ultracode) — 4 parallel codebase scouts grounded 2 grey areas, both accepted as recommended

<domain>
## Phase Boundary

WSX-01: when the operator creates a workspace WITHOUT picking a node, the control plane
auto-selects the least-loaded node that still passes the node-RAM capacity threshold,
proven over the FakeComputeProvider's multi-node capacity. Manual node pick stays available
and unchanged. The `ComputeProvider` seam stays free of Proxmox specifics (seam-leakage guard
green). Backend create-saga is the core; a small NewWorkspaceModal touch adds the "auto" path.

Real multi-node Proxmox validation is the deferred dev-homelab smoke (ACC-01) — NOT a v1.2
CI gate. Everything here is CI-provable over the Fake's multi-node capacity.

</domain>

<decisions>
## Implementation Decisions

### Node Enumeration + Selection (backend)
- **Candidate-node list comes from a Settings `worker_nodes` list** (operator topology config,
  same spirit as the existing `settings.default_node`). Auto-select iterates `worker_nodes`
  calling `getNodeMemory(node)`. **No `ComputeProvider` ABC change, no new seam method, no ADR**
  — the seam stays clean (auto-select calls only the existing `getNodeMemory`). KISS/YAGNI: do
  not grow the provider contract without a concrete need; the node list is topology config.
  (Rejected alternative: adding `listNodes()` to the ABC for dynamic discovery — would need
  ADR-0011 + a Proxmox impl only homelab-verifiable. Deferred; revisit if real dynamic cluster
  discovery becomes a concrete requirement.)
- **Selection rule:** pick the node with the lowest `getNodeMemory` fraction among nodes
  at/under threshold; **tie-break by node name ascending** (deterministic for tests).
- **No-fit behavior:** when no node is at/under threshold, reuse the existing `CapacityError`
  (`capacity_exceeded` code) with a message hinting manual selection (e.g. "All nodes at
  capacity. Pick a node manually to override."). No new error code, no overcommit (criterion 2).
- **Selection runs INSIDE `_create_lock`:** select → step-0 capacity guard → step-1 VMID
  reserve form one serialized critical section, preserving the ADR-0010 atomicity contract.
  `getNodeMemory` is a fast read, so holding the lock across selection is acceptable for v1
  (`--workers 1`, single operator). The existing per-node guard remains the single authoritative
  threshold check (strict `>`); the chosen node flows into it unchanged.

### API + UI Contract
- **Auto signal = `node: Optional[str] = None`** on `WorkspaceCreate`. `None`/omitted = auto;
  a node string = manual pick (unchanged path). The service fills the chosen node and SHOULD
  echo the selected node back in the create response for operator visibility. Cleanest Pydantic
  contract; no new field, no sentinel string, no bool flag.
- **NewWorkspaceModal defaults to "Auto (least-loaded)"** as the first/selected option; manual
  pick is the escape hatch (one-click create matches WSX-01 "operator does not pick a node").
  Remove the current "default to first node on mount" behavior; selecting Auto sends `node: null`
  (or omits it). Form validation must accept the Auto choice.
- **FakeComputeProvider gains optional `node_fractions: dict[str, float]`** in `__init__`
  (float fallback preserves every existing fixture: `FakeComputeProvider()` and
  `FakeComputeProvider(node_memory=0.25)` keep working). `getNodeMemory(node)` looks the node up
  in the dict, falling back to the single value. This is what makes the multi-node tests possible.
- **Shared capacity helper:** extract ONE `_fits(fraction, threshold)` / node-capacity helper
  used by BOTH the `GET /api/v1/nodes` route and auto-select, so the modal's displayed capacity
  and the saga's selection decision never drift (single source of truth, strict `>` semantics,
  boundary `==` allowed).

### Claude's Discretion (implementation details — defaults stated, Claude may refine)
- `selectNode()` as a small pure-ish service method (reads `worker_nodes` + `getNodeMemory`,
  returns the chosen node or raises `CapacityError`) vs inlined in `createWorkspace` — default:
  a separate method for unit-testability; called inside the lock when `payload.node is None`.
- Exact `worker_nodes` Settings shape + default (e.g. defaults to `[default_node]` so a
  single-node config still works and the existing single-node tests stay green).
- `getNodeMemory` raising for one node during the scan → skip that node (treat as unavailable,
  mirrors the `/nodes` degrade-not-500 posture); only raise `CapacityError` if NO node fits.
- Whether the create response gains a `selectedNode` field or reuses the existing workspace row's
  `node` — default: surface the chosen node via the returned workspace row's node field.

</decisions>

<code_context>
## Existing Code Insights (from 4 parallel scouts — file:line)

### Reusable Assets
- `api/services/workspaceService.py` — `createWorkspace` saga (line ~129); `_create_lock`
  asyncio.Lock (~126) serializes step-0 capacity guard (~145, `getNodeMemory(payload.node) >
  threshold` → `CapacityError`) + step-1 `_reserve_vmid_and_row` (~196); released before the
  multi-second `cloneCt` (~154). `_compensate` (~232) is idempotent reverse. ADR-0010 documents
  the lock.
- `api/compute/provider.py` — `ComputeProvider` ABC (~47); `getNodeMemory(self, node: str) ->
  float` (~153) is the ONLY capacity method (returns mem_used/mem_total fraction in [0,1]). NO
  enumeration method exists — confirms the Settings-list decision.
- `api/compute/fakeProvider.py` — `FakeComputeProvider.__init__` (~67, single `node_memory`
  float default 0.25) + `getNodeMemory` (~200, returns the single value, ignores node name).
  This is the file to extend with `node_fractions`.
- `api/config.py` — `capacity_threshold` (~59, default 0.80) + `default_node`; add `worker_nodes`
  here (default `[default_node]`).
- `api/routers/nodes.py` — `GET /api/v1/nodes` (~51) + `_node_capacity` (~30-48) computing
  `{node, memoryUsedFraction, capacityThreshold, overThreshold}` with strict `>` (line ~42),
  degrade-not-500 (null fraction + overThreshold=false on raise). Currently iterates only
  `[settings.default_node]` → extend to iterate `worker_nodes`; this is where the shared `_fits`
  helper lives or is factored from.
- `api/models/workspace.py` — `WorkspaceCreate` (~34-42), `node` field (~41) currently REQUIRED
  → make `Optional[str] = None`.
- `api/routers/workspaces.py` — `POST /api/v1/workspaces` (~26-33) → `service.createWorkspace`.
- `ui/src/components/NewWorkspaceModal.tsx` — node `<select>` (~417-429) populated by `useNodes`;
  `node` state (~183) defaulted to first node on mount (~211-215, REMOVE for Auto default);
  form validity requires non-empty node (~230); submit passes `{name, projectRepo,
  projectBranch, node}` (~241-246).
- `ui/src/hooks/useNodes.ts`, `ui/src/hooks/useWorkspaces.ts` (`useCreateWorkspace` ~39-50),
  `ui/src/types/workspace.ts` (`WorkspaceCreate` ~34-40, `node: string` ~39 → optional),
  `ui/src/api/client.ts` (envelope unwrap).

### Established Patterns
- snake_case DB/Python → camelCase JSON via the single `CamelModel` base (`by_alias=True` at the
  router boundary). A new Settings key is snake_case; a new model field serializes to camelCase.
- Capacity threshold is strict `>` refuse, boundary `==` allowed (test_capacity_guard.py boundary
  test) — auto-select MUST use the same comparison.
- `api/tests/unit/test_seam_leakage.py` (~71) tokenizes api/ .py (excludes comments/strings),
  asserts proxmoxer/ProxmoxAPI only in `proxmoxProvider.py` — auto-select must stay green.
- FakeFailures injectable hook for compensation tests; deterministic Fake (no random/sleep).

### Integration Points
- Router detects `payload.node is None` → service auto-selects inside the lock → existing guard +
  reserve proceed with the chosen node → unchanged clone/start/health/running tail.
- `/nodes` route + auto-select share the `_fits`/`_node_capacity` helper → UI capacity display and
  saga decision agree.
- Modal "Auto" option → `node: null`/omit → backend auto-path; manual pick → existing path.

</code_context>

<specifics>
## Specific Ideas

- The two scouts disagreed on lock placement (inside vs outside `_create_lock`); resolved to
  INSIDE for atomicity-by-construction and simplest reasoning. In v1 (`--workers 1`,
  non-reservation-aware threshold) inside-vs-outside is not a correctness divider, so inside wins
  on clarity. Note this in the plan so the executor does not "optimize" it back outside.
- Multi-node test matrix (criterion 5, all over the Fake's `node_fractions`): least-loaded-fitting
  node chosen; over-threshold node skipped; boundary node at exactly threshold is eligible;
  no-fit (all over threshold) refuses with `CapacityError`; tie → name ascending; manual pick
  still works end-to-end; seam-leakage guard stays green.

</specifics>

<deferred>
## Deferred Ideas

- Dynamic cluster node discovery via a new `ComputeProvider.listNodes()` ABC method (+ ADR-0011 +
  Proxmox impl) — rejected for v1.2 in favor of the Settings `worker_nodes` list. Revisit only if
  dynamic discovery becomes a concrete requirement.
- Reservation-aware capacity accounting (counting pending-but-not-booted workspaces against a
  node's budget) — out of scope; v1 threshold is best-effort over actual node RAM, same as today.
- Real multi-node Proxmox validation → deferred dev-homelab smoke (ACC-01).

</deferred>
