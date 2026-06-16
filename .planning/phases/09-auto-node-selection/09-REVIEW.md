---
phase: 09-auto-node-selection
reviewed: 2026-06-16T07:59:50Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - api/services/workspaceService.py
  - api/lib/capacity.py
  - api/lib/errors.py
  - api/config.py
  - api/compute/fakeProvider.py
  - api/models/workspace.py
  - api/routers/nodes.py
  - ui/src/components/NewWorkspaceModal.tsx
  - ui/src/types/workspace.ts
  - ui/tests/msw/handlers.ts
  - api/tests/unit/test_node_selection.py
  - api/tests/integration/test_create_auto_node.py
findings:
  critical: 0
  warning: 2
  info: 4
  total: 6
status: issues_found
---

# Phase 9: Code Review Report

**Reviewed:** 2026-06-16T07:59:50Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Phase 9 (WSX-01, auto node selection) was reviewed at standard depth against the
six locked-design focus areas. The core concurrency and seam-discipline claims
hold up under tracing:

- **Concurrency/overcommit:** `selectNode()` runs inside `_create_lock`, and the
  resolved `node` flows through the SAME post-lock capacity guard and VMID reserve
  (`workspaceService.py:144-161`). There is no path where `payload.node is None`
  escapes the lock or where the chosen node skips re-validation. The integration
  test `test_persisted_node_matches_selection_inside_lock` proves the persisted row
  carries the selected node. No overcommit window found.
- **Seam discipline:** `selectNode`, `capacity.py`, and `nodes.py` reference only
  `getNodeMemory`, `settings`, `_fits`, and `CapacityError` — no `proxmoxer`/
  `aiosqlite`/raw SQL. The `test_seam_leakage.py` token guard confirms this in CI.
- **`_fits` boundary:** `fraction <= threshold` is correct for the "boundary `==`
  eligible, strict `>` refuses" contract, and is the single comparator shared by
  `/nodes` and auto-select. Tie-break (name ascending) and raising-node-skip are
  correct and tested.
- **Optional `node` contract:** api model (`str | None = None`) ↔ ui type
  (`node?: string | null`) ↔ modal (`node || null`) ↔ MSW (`body.node ??`) are
  consistent. No `""` vs `null` mismatch reaches the wire.
- **`CapacityError` additive `message=`:** keyword-only, single-arg callers
  unchanged, `.code` invariant. Correct at the type level.

Two warnings were found. The most consequential is that the auto no-fit
"manual-pick hint" message is silently discarded by the central error handler, so
the operator never sees it and instead gets a message that is misleading on the
auto path. The remainder are info-level robustness/consistency nits.

## Warnings

### WR-01: Auto no-fit "manual-pick hint" message is discarded at the wire boundary

**File:** `api/services/workspaceService.py:238-241`, `api/main.py:206-207`, `api/lib/errors.py:53-58`

**Issue:** `selectNode()` raises
`CapacityError(message="All nodes at capacity. Pick a node manually to override.")`
and the class docstring and `selectNode` docstring both assert the refusal is
"raised with a manual-pick hint." But the central `_service_error_handler` does:

```python
message = _SAFE_ERROR_MESSAGES.get(exc.code, _SAFE_ERROR_MESSAGES["service_error"])
```

It keys on `exc.code` only and never reads `str(exc)` / `exc.args`, so for
`capacity_exceeded` it ALWAYS emits the static
`"The selected node is over capacity."` The custom `message=` is constructed,
stored on the exception, and then thrown away before it reaches the envelope. Two
concrete consequences:

1. The `message=` keyword parameter on `CapacityError` is effectively dead code at
   the API boundary — the entire reason it was added (a distinct auto-path hint) is
   never observable by any client.
2. On the AUTO path the operator gets "The **selected** node is over capacity."
   even though they selected NO node (they chose Auto). The modal surfaces
   `err.message` verbatim (`NewWorkspaceModal.tsx:264-266`), so this misleading
   string is what the user reads. It does not tell them to pick a node manually,
   which is the one recovery action available.

The unit test `test_no_fit_raises_capacity_error_with_manual_pick_hint` asserts
`"manual" in str(excinfo.value).lower()` — it checks the *exception object* in
isolation and passes, but it does NOT exercise the router, so it gives false
confidence that the hint reaches the wire. No test asserts the end-to-end response
body message; `test_auto_no_fit_refuses_with_capacity_envelope_and_no_orphan` only
checks `error.code`.

**Fix:** Differentiate the two refusal shapes at the wire. Either (a) give the
auto no-fit its own error code (e.g. `no_fitting_node`) with its own
`_SAFE_ERROR_MESSAGES` entry that carries the manual-pick hint, or (b) let
`_service_error_handler` prefer a vetted per-instance message for `CapacityError`
when one was explicitly supplied. Option (a) keeps the "never echo raw exception
text" rule intact:

```python
# lib/errors.py — distinct code for the auto no-fit case
class NoFittingNodeError(CapacityError):
    code = "no_fitting_node"

# selectNode()
if not fitting:
    raise NoFittingNodeError(
        message="All nodes at capacity. Pick a node manually to override."
    )

# main.py
_SERVICE_ERROR_STATUS[NoFittingNodeError] = 409
_SAFE_ERROR_MESSAGES["no_fitting_node"] = (
    "All nodes are at capacity. Pick a node manually to override."
)
```

Then add an integration assertion on the response body `error.message` (not just
`error.code`) so the hint is regression-protected end to end.

### WR-02: `worker_nodes` default derivation silently breaks if `default_node` is overridden after construction, and dedup/empty-string entries are unvalidated

**File:** `api/config.py:54`, `api/config.py:107-118`

**Issue:** `_derive_worker_nodes_default` only fires when `worker_nodes` is falsy
at model-construction time. Two robustness gaps that feed directly into the
selection loop (`workspaceService.py:231`):

1. An operator who sets `BURROW_WORKER_NODES` to a value containing an empty
   string or duplicates (e.g. `pve1,,pve1` via a comma-split env source) gets those
   passed straight into `selectNode`'s iteration. A duplicate node is probed twice
   (two `getNodeMemory` calls, double-counted in the tie-break candidate list); an
   empty-string node name is handed to `getNodeMemory("")` and, if it does not
   raise, becomes a selectable target that then gets persisted as the row's NOT
   NULL `node` and passed to `cloneCt`/`startCt`. There is no validation that
   `worker_nodes` entries are non-empty/unique.

2. The derivation reads `self.default_node` at validator time, which is correct for
   env/`__init__` overrides, but a test or runtime mutation that sets
   `settings.default_node` *after* construction (as the test fixtures freely
   monkeypatch `worker_nodes` directly) will not re-derive. This is acceptable for
   v1 (`--workers 1`) but the coupling is implicit and undocumented at the field.

**Fix:** Add a validator that strips/dedups while preserving order, and rejects
empty entries, so a malformed topology fails loudly instead of silently selecting a
bogus node:

```python
@model_validator(mode="after")
def _normalize_worker_nodes(self) -> "Settings":
    if not self.worker_nodes:
        self.worker_nodes = [self.default_node]
        return self
    seen: list[str] = []
    for n in self.worker_nodes:
        name = n.strip()
        if not name:
            raise ValueError("worker_nodes entries must be non-empty")
        if name not in seen:
            seen.append(name)
    self.worker_nodes = seen
    return self
```

## Info

### IN-01: Successful create returns HTTP 200 while the create handler is documented and mocked as 201

**File:** `api/routers/workspaces.py:26-33`, `ui/tests/msw/handlers.ts:174`

**Issue:** `create_workspace` returns `respond(...)` with no `status_code`, so
FastAPI emits **200** for a POST create. The integration test asserts `== 200`
(`test_create_auto_node.py:77`), but the MSW fake and the UI test return **201**
(`handlers.ts:174`, `NewWorkspaceModal.test.tsx:207`). The client
(`api/client.ts`) branches on `body.error` only and ignores status on success, so
nothing breaks today, but the backend and the UI test doubles disagree on the
create status code. A future consumer that keys on 201 (or a contract test) would
trip on this drift.

**Fix:** Pick one. For a synchronous create that returns the final row, 200 is
defensible; align the MSW handler and UI test to 200. If 201 is intended, set
`status_code=201` on the route and update the integration test. Either way, make
backend and doubles agree.

### IN-02: Auto-path comment claims selectNode "already guaranteed `_fits`" but the redundant guard re-reads memory and can diverge

**File:** `api/services/workspaceService.py:154-158`

**Issue:** The comment at line 154-156 says the post-select guard is "the single
authoritative threshold check both paths pass through," and for the auto path
`selectNode` already validated `_fits` on the same node. But the guard calls
`getNodeMemory(node)` AGAIN — a second read of a value that can change between the
two calls even inside the lock is not possible here (same event loop, no await
interleaving mutates node memory), so this is currently safe. The subtle issue is
the two checks use DIFFERENT comparators: `selectNode` uses `_fits` (`<=`,
boundary eligible) while the guard uses raw `> threshold` (`workspaceService.py:157`).
They agree at the boundary today (`<= t` is the negation of `> t`), so this is
consistent, but it is a second hand-rolled comparison that bypasses the shared
`_fits` helper the phase explicitly introduced to prevent drift (`capacity.py`
docstring: "single source of truth"). If `_fits` semantics ever change (e.g. to
`<`), this guard would silently diverge.

**Fix:** Route the guard through the shared comparator so there is genuinely one
source of truth:

```python
if not _fits(await self.compute.getNodeMemory(node), self.settings.capacity_threshold):
    raise CapacityError(node)
```

### IN-03: Auto no-fit envelope discards which nodes were considered/why each was rejected

**File:** `api/services/workspaceService.py:230-244`

**Issue:** When no node fits, the candidate fractions and the skip reasons
(unreachable vs over-threshold) are computed and then dropped. For a single
operator triaging "why did Auto refuse," the only signal is a generic 409 with no
indication of whether nodes were over capacity or unreachable. This is a
diagnosability gap, not a correctness bug; the values are non-secret (node names +
fractions), so a structured `logger.info`/`warning` on the no-fit branch would aid
the homelab smoke (ACC-01) without changing the wire contract.

**Fix:** Log the considered set on the no-fit branch before raising:

```python
if not fitting:
    logger.warning(
        "auto-select found no fitting node",
        extra={"considered": self.settings.worker_nodes,
               "threshold": self.settings.capacity_threshold},
    )
    raise CapacityError(message="All nodes at capacity. Pick a node manually to override.")
```

### IN-04: UI test assertion for "node null" is too weak to catch a `""`/omitted regression

**File:** `ui/src/components/NewWorkspaceModal.test.tsx:254`

**Issue:** The Auto-path test asserts
`expect(captured.body?.node ?? null).toBeNull()`. The `?? null` coalesces
`undefined` to `null`, so this assertion passes whether the modal sends `null`,
`undefined`, or omits `node` entirely. The whole point of the locked contract is
that Auto sends `null` specifically (not `""`, not omitted). The modal currently
does the right thing (`node: node || null`, `NewWorkspaceModal.tsx:244`), but the
test would NOT catch a regression that started sending `""` only if `""` were
falsy-coalesced — and it actively would not catch an `undefined`/omitted
regression. The over-threshold manual nodes are also rendered in the dropdown with
no over-capacity indication, so an operator can manually pick a node the backend
will then reject; that is the intended manual-override path but worth a visual cue
(out of scope for this phase).

**Fix:** Tighten to assert the exact value sent:

```ts
expect(captured.body).toHaveProperty("node", null);
```

---

_Reviewed: 2026-06-16T07:59:50Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
