<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# ADR-0017: Async-202 workspace create with a background boot saga

## Status

Accepted

## Context

`POST /api/v1/workspaces` runs the full 8-step create saga synchronously and only
returns once the worker reaches `running`: clone the golden template, persist boot
intent, start the container, resolve the static IP, and poll ttyd health. On real
Proxmox infrastructure that end-to-end boot routinely exceeds 60 seconds (a full
clone plus first-boot plugin install), and the reverse proxy in front of the control
plane closes the request with a `504 Gateway Timeout` long before the saga finishes.
The workspace usually does come up, but the operator sees a failed request, the setup
wizard's create step appears to hang, and a retry can reserve a second VMID.

The synchronous saga already persists a `creating` row with a reserved VMID BEFORE it
clones (RESEARCH Pattern 2), and any post-reservation failure runs idempotent reverse
compensation that lands the row in `error` (SC-11). So the durable record of the boot
already exists independent of the HTTP request; the request is holding the connection
open only to report the final status, and that is exactly what times out.

The UI also already polls the workspace list every 3 seconds and renders
`creating` -> `running`/`error` transitions from that poll. The status feedback path
therefore does not depend on the create response body carrying the final state.

## Decision

Return `202 Accepted` with the `creating` row immediately, and run the boot saga
(steps 2 through 7) in a tracked background task. The `creating` state is reused as
the initial state; no new state is added.

- **Split the saga at the reservation boundary.** `reserveWorkspace` runs steps 0+1
  (node resolve, capacity guard, VMID reservation, persist the `creating` row) under
  the existing create-lock and returns fast. `_runBootSaga` runs steps 2 through 7
  plus the existing compensation-to-`error` block. The synchronous `createWorkspace`
  is kept as `reserveWorkspace` then `await _runBootSaga`, so internal callers and the
  unit tier that await a fully-booted workspace are unchanged.

- **Reservation errors still surface synchronously.** Capacity rejection and an
  exhausted VMID pool raise from `reserveWorkspace` BEFORE the `202` is returned, so a
  create the control plane can legitimately refuse still fails synchronously through
  the existing typed-error envelope handlers (`409 capacity_exceeded`,
  `409 no_free_vmid`). Only the slow boot moves to the background.

- **App-scoped tracked background task.** `scheduleCreate` reserves the row, then hands
  `_runBootSaga` to a caller-injected `schedule` callback and returns the `creating`
  row. `main.schedule_create_task` is that callback: it creates the task, holds a
  strong reference in a module-level `set` (a bare `create_task` handle is only weakly
  held by the loop and could be garbage-collected mid-flight), and removes it on
  completion via `add_done_callback`. The registry lives at app scope, not on the
  per-request service instance, because `get_service` builds a fresh service per call.
  The `schedule` seam keeps `WorkspaceService` free of any app-registry coupling.

- **Shutdown cancels in-flight creates.** The lifespan's shutdown, after cancelling the
  reconciler, cancels every tracked create task and awaits them with
  `gather(return_exceptions=True)` (suppressing the resulting `CancelledError`), so no
  in-flight boot leaks past shutdown.

- **The row always lands `error`, even if the client is gone.** The background wrapper
  `_run_boot_saga_safe` awaits `_runBootSaga` and swallows the exception (logged
  redacted), because the saga's own compensation has already landed the row in `error`
  (SC-11). The client that received the `202` and disconnected does not need the raise;
  swallowing it keeps the tracked task from carrying an un-retrieved exception.

- **List-poll-driven UI.** The create call (the New Workspace modal and the setup
  wizard's create step) treats the `202` as success and closes / advances immediately.
  The existing 3 second workspace-list poll renders the new `creating` row moving to
  `running` or `error`. No new per-workspace poll is added.

## Consequences

**Positive:**

- A real boot longer than the proxy timeout no longer `504`s: the create returns in the
  time it takes to reserve a VMID and persist a row, and the boot proceeds in the
  background.
- The UI is simpler and honest: the modal/wizard no longer pretends to block on a
  synchronous boot, and the already-existing list poll is the single status source.
- The durable guarantees are unchanged: a reserved VMID, a `creating` row before any
  clone, and idempotent compensation to `error` on any failure.

**Negative / trade-offs:**

- The control plane now owns background-task lifecycle: a registry with a strong
  reference and a done-callback, plus a shutdown cancel-and-drain. This is the same
  cancel/suppress pattern the reconciler already uses, so it is one more instance of a
  known shape rather than a new mechanism.
- A create failure is no longer observable in the HTTP response; the operator learns of
  it only from the row landing `error` in the list. This is acceptable because the row
  is the durable source of truth and the poll already surfaces it.
- v1 assumes a single worker process; the module-level task set is per-process. A
  multi-process control plane would move task tracking behind the same seam, consistent
  with the deferred cross-process upgrade path in ADR-0010.

**Neutral / follow-on:**

- The real longer-than-60-second boot no-504 confirmation on live infrastructure is the
  Phase 22 ACC-04 smoke.

## Alternatives considered

- **Starlette / FastAPI `BackgroundTasks`.** Rejected: a `BackgroundTasks` job is tied
  to the request-response cycle and is not owned by the app lifespan, so it cannot be
  cancelled and drained on shutdown and its lifetime is coupled to the request that
  scheduled it. The boot saga must outlive the request that returned the `202`, which is
  the whole point, so an app-scoped tracked task is the correct owner.

- **Keep create synchronous and stream progress over a client long-poll or WebSocket.**
  Rejected: it adds a new real-time status channel and a new UI subscription for a
  problem the existing 3 second list poll already solves, and it still holds a
  connection open across the slow boot (the original `504` risk, moved to a different
  endpoint). Reusing the list poll is less surface for the same feedback.

## Revisit trigger

A multi-process or multi-node control plane where create tasks must be tracked and
cancellable across processes (which moves the registry behind a shared store, aligned
with the ADR-0010 cross-process upgrade path), or a product requirement for real
per-step boot progress in the UI (which would reintroduce a status-streaming channel
that this decision deliberately declined).
