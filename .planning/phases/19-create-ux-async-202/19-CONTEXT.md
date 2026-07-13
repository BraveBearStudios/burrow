<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
# Phase 19: Create-UX Async-202 - Context

**Gathered:** 2026-07-13
**Status:** Ready for planning
**Mode:** Auto (autonomous run). Backend lifecycle change + small UI wait-state; ADR-0017.

<domain>
## Phase Boundary

`POST /api/v1/workspaces` returns immediately (`202` + a `creating` row) with the
boot saga running in a tracked background task, so a slow real boot never `504`s.
The UI's existing 3s workspace-list poll drives `creating`→`running`/`error`, and
the setup-wizard create step no longer blocks. Cures the ~60s create 504 (UX-01).
</domain>

<decisions>
## Implementation Decisions

### Saga split (backend)
- Refactor `WorkspaceService.createWorkspace` into: `reserveWorkspace(payload)` —
  steps 0+1 (capacity guard + VMID reservation + persist `creating` row, under the
  existing `_create_lock`), returns the creating `Workspace` fast; and
  `_runBootSaga(ws, payload)` — steps 2-7 (clone → boot intent → start → IP → ttyd
  wait → mark `running`) plus the existing compensation-to-`error` except block
  (node read from `ws.node`).
- Keep `createWorkspace(payload)` as `reserve` + `await _runBootSaga` (synchronous,
  returns `running`) — UNCHANGED external behavior so the existing 299-test suite
  and any internal callers keep passing.
- Add `scheduleCreate(payload) -> Workspace`: `reserveWorkspace` (fast) + spawn
  `_runBootSaga` on a tracked background task via an app-scoped registry, return the
  `creating` row.

### 202 endpoint
- `POST /workspaces` calls `scheduleCreate`, returns the standard envelope with
  HTTP `202`. On a reservation-time failure (capacity, no free VMID) it still errors
  synchronously (the fast path can legitimately reject) via the existing handlers.

### Background-task lifecycle (ADR-0017)
- `get_service` builds a per-call service over the process-wide `get_compute`/`get_db`
  singletons, so the task registry lives at APP scope in `main.py` (module-level
  `set[asyncio.Task]`), NOT on the per-request service instance. A `done_callback`
  discards finished tasks. The lifespan cancels + awaits any in-flight create tasks
  on shutdown (mirroring the reconciler cancel), suppressing `CancelledError`.
- The background wrapper SWALLOWS the saga exception (the row already lands `error`
  via `_runBootSaga`'s compensation), so a failed boot never surfaces an
  un-retrieved-task warning. It is logged, not raised.

### UI wait-state
- The create call (NewWorkspaceModal + the SetupWizard create step) treats a `202`
  as success: close the modal / advance immediately; the existing 3s list poll shows
  the new `creating` row transitioning to `running` (or `error`). No new polling
  loop — reuse the workspace-list query's `refetchInterval`.

### Tests (CI-provable over the Fake)
- Inject a slow/blocking boot (an `asyncio.Event`-gated `_wait_ttyd`, or a Fake
  slow-boot hook) and assert `POST /workspaces` returns `202` + `creating` WITHOUT
  waiting; then release and assert the background task drives `running`; a failing
  boot drives `error`. A shutdown-cancels-in-flight-create test. UI: the modal/wizard
  closes/advances on 202 and the list poll reflects `creating`.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `api/services/workspaceService.py` — the 8-step saga (steps 0-1 vs 2-7 are the
  clean split point at the `async with self._create_lock` boundary + the `try` block).
- `api/main.py` — the reconciler task pattern (`asyncio.create_task` in `lifespan`,
  cancel+await+suppress on shutdown) to mirror for the create-task registry.
- `api/routers/workspaces.py` — the `POST /workspaces` endpoint (currently returns
  200 after the full saga).
- `ui/src/hooks/useWorkspaces.ts` / `useNodes.ts` — the existing 3s `refetchInterval`
  list poll that already renders status transitions.
- `ui/src/components/NewWorkspaceModal.tsx` + `SetupWizard.tsx` create step.

### Established Patterns
- Envelope `respond(...)`; FastAPI `status_code` on the route or Response.
- Compensation-to-`error` (SC-11) already guarantees never-stuck-`creating`.
- The state machine keeps `creating` as the initial state (no new state added).

### Integration Points
- `workspaceService.py` (split + scheduleCreate), `main.py` (task registry +
  lifespan shutdown), `routers/workspaces.py` (202). `docs/adr/ADR-0017-*.md` (new).
- `ui/`: NewWorkspaceModal + SetupWizard create step wait-state.
</code_context>

<specifics>
## Specific Ideas

`creating` stays the initial state (ADR reuse, no new state). The 202 body is the
same `Workspace` envelope, just the `creating` row. Reuse the list poll — do not add
a per-workspace poll.
</specifics>

<deferred>
## Deferred Ideas

The real >60s boot no-504 confirmation on live infra is the Phase 22 ACC-04 smoke.
</deferred>
