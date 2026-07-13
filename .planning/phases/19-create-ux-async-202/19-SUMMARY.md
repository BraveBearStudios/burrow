<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
# Phase 19: Create-UX Async-202 - Summary

**Completed:** 2026-07-13
**Requirement:** UX-01 · **ADR:** ADR-0017

## What shipped

`POST /api/v1/workspaces` now returns **202 + a `creating` row immediately** and runs
the boot saga in a tracked background task, so a slow real boot never `504`s.

- **Saga split** (`workspaceService.py`): `reserveWorkspace` (steps 0+1 — capacity
  guard + VMID reservation under `_create_lock`, returns the `creating` row fast) and
  `_runBootSaga` (steps 2-7 + compensation, node/vmid from the reserved row).
  `createWorkspace` is now `reserve` + `await _runBootSaga` — synchronous behavior
  UNCHANGED (the service-level saga/compensation/capacity tests stayed green,
  untouched). `scheduleCreate` reserves then schedules `_run_boot_saga_safe`
  (awaits the saga, logs + swallows on failure since the row already lands `error`).
- **App-scoped task registry** (`main.py`): `_create_tasks` set + `schedule_create_task`
  (create + strong-ref + self-discard), injected into `scheduleCreate` as the
  `schedule` seam so the service stays registry-agnostic. Lifespan shutdown cancels
  the reconciler then cancels + drains in-flight create tasks (no leak).
- **202 endpoint** (`workspaces.py`): `status_code=202`, `scheduleCreate(...)`.
  Reservation-time failures (capacity, no free VMID) still reject synchronously
  through the existing handlers BEFORE the 202.
- **ADR-0017** records the async-202 create + background-task lifecycle decision
  (`creating` state reused, list-poll-driven UI, row-always-lands-error guarantee;
  Starlette BackgroundTasks + client long-poll rejected).
- **UI wait-state**: `NewWorkspaceModal` closes on the 202 `creating` response; the
  SetupWizard create step already advanced on mutation resolve. No new poll — the
  existing 3s workspace-list `refetchInterval` renders `creating`→`running`/`error`.

## Verification evidence

- Backend: `ruff` + `ruff format --check` + `mypy . --strict` clean (90 files);
  `uv run pytest -q` → **302 passed** (299 prior + 3 new async-202). New tests: 202 +
  `creating` without waiting (boot gated on an `asyncio.Event`), failing boot →
  `error` on the background path, shutdown cancels + drains an in-flight create.
- Frontend: `tsc --noEmit` clean; `biome ci .` clean (59 files); `vitest run` →
  **136 passed** (17 files).
- `reuse lint` → 492/492 (ADR-0017 header included).

## Note

The HTTP create contract legitimately changed (200+`running` → 202+`creating`), so
three existing integration files (`test_workspaces_api`, `test_bootconfig`,
`test_create_auto_node`) + a shared `await_workspace_status` conftest helper were
updated to poll to `running`. The capacity no-fit test still asserts a synchronous
`409` (reservation-time rejection). `createWorkspace`'s synchronous tests untouched.

## Commits

`feat(19)` saga split + 202 · `docs(19)` ADR-0017 · `test(19)` async-202 tests +
contract updates · `feat(19)` UI create wait-state.
