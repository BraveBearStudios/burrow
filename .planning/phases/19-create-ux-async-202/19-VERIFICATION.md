<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
status: passed
phase: 19
verified: 2026-07-13
---

# Phase 19: Create-UX Async-202 - Verification

**Goal:** `POST /workspaces` returns immediately (202 + `creating`) with the boot saga
in a tracked background task, so a slow boot never 504s; the UI list poll drives
`creating`→`running`/`error` and the wizard create step no longer blocks (UX-01).

## Must-Haves

1. **202 + `creating` row returned immediately** - PASSED. `POST /workspaces` is
   `status_code=202` and returns the reserved `creating` workspace via
   `scheduleCreate`; an integration test gates the boot on an `asyncio.Event` and
   asserts the response arrives `creating` WITHOUT waiting for the saga.

2. **Boot saga runs in a tracked background task** - PASSED. `scheduleCreate`
   schedules `_run_boot_saga_safe` via the app-scoped `_create_tasks` registry
   (`schedule_create_task`, strong-ref + self-discard); on release the row
   transitions to `running`, and a failing boot lands `error` on the background path.
   Lifespan shutdown cancels + drains in-flight create tasks (tested, no leak).

3. **Never stuck `creating`; compensation preserved** - PASSED. `_runBootSaga` keeps
   the SC-11 compensation (stop+destroy, row→`error`); the background wrapper swallows
   the re-raised exception after the row lands `error`, so a client-gone boot still
   lands the row correctly and never surfaces an un-retrieved-task warning.

4. **UI create no longer blocks** - PASSED. `NewWorkspaceModal` closes on the 202
   `creating` response; the SetupWizard create step advances on mutation resolve. No
   new poll added — the existing 3s workspace-list `refetchInterval` renders the
   `creating`→`running`/`error` transition.

5. **`createWorkspace` synchronous behavior unchanged** - PASSED. The service-level
   `createWorkspace` (reserve + await saga) is untouched externally; all service-tier
   saga/compensation/capacity/state-machine tests passed unmodified.

## Evidence

- `ruff` + `mypy --strict` clean (90 files); `uv run pytest -q` → **302 passed**
  (299 prior + 3 new async-202).
- UI: `tsc --noEmit` clean; `biome ci .` clean; `vitest run` → **136 passed**.
- `reuse lint` → 492/492 (ADR-0017 header included).

## Realized-at-downstream (by design, NOT a gap)

- The real >60s boot no-504 confirmation on live infra is the Phase 22 ACC-04 smoke.

**Verdict: PASSED** — the async-202 create + tracked background boot saga is delivered
and verified over the Fake (api 302 + ui 136); the ~60s create 504 is cured in CI.
