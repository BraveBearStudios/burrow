<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 04-hardening-release
plan: 01
subsystem: api
tags: [reconciler, reaper, idle-auto-stop, asyncio, lifespan, fastapi, ci]

# Dependency graph
requires:
  - phase: 04-hardening-release
    plan: 02
    provides: stopWorkspace(reason=) threading reason into workspace.stopped; reconciler_period_s/creating_timeout_s/idle_window_s Settings keys; ADR-0010
  - phase: 01-foundation
    provides: createWorkspace saga, compute.usedVmids/destroyCt (idempotent), db.listWorkspaces/getEvents/updateWorkspace/logEvent, _safe redaction, _db_used_vmids
provides:
  - "Reconciler.reconcile_once() — pure single pass over the two seams: reaper (pool-bounded orphan destroy + leaked-VMID free + timed-out creating sweep) + idle auto-stop, with an injectable now"
  - "FastAPI lifespan owning the periodic reconcile task on the request-path get_compute()/get_db() singletons, cancelled cleanly on shutdown"
  - "build_reconciler() factory composing the reconciler from the same singletons the routers use"
  - "CI static-gates wiring for the Phase-4 hermetic tiers (reconciler + capacity-race + lifespan)"
affects: [04-hardening-release, the fleet runtime (unattended reaping + auto-stop)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure single-pass reconcile: every decision a function of (DB state, compute state, injected now) — no asyncio.sleep, no wall-clock, no freezegun"
    - "In-reconciler pool-range safety bound (if vmid in pool) because the Fake's usedVmids() is unfiltered — the bound cannot live in the provider"
    - "Row-less orphan reaps audit via a structured log line (the events FK needs a live workspaceId); rows-with-events reaps use db.logEvent"
    - "FastAPI lifespan owns a thin while-True loop calling reconcile_once(); the loop wraps each pass in a broad except, CancelledError propagates for clean cancel"
    - "Lifespan tested by driving the lifespan(app) async context manager directly (no live server, no asgi_lifespan dependency)"

key-files:
  created:
    - api/services/reconciler.py
    - api/tests/unit/test_reconciler.py
    - api/tests/integration/test_lifespan.py
  modified:
    - api/main.py
    - .github/workflows/ci.yml

key-decisions:
  - "reaper.timed_out reason is the fixed literal 'creating timeout' — NOT routed through _safe(exc) (which takes a BaseException, not a str; reserved for real exception text)"
  - "Row-less orphan reaps log structurally (logger.info('reaper.destroyed', extra={'vmid': vmid})), never db.logEvent — a leaked VMID has no live row to satisfy the events FK"
  - "_reconcile_loop re-raises CancelledError explicitly (broad except catches Exception only) so the lifespan's await task unwinds cleanly on shutdown"
  - "Lifespan tested by entering/exiting lifespan(app) directly rather than via a server or asgi_lifespan — zero new dependency (FROZEN guardrail 7)"

patterns-established:
  - "Injectable-now reconcile (constructor `now=None` -> `now or (lambda: datetime.now(timezone.utc))`) as the testability seam, replacing a time-mock library"
  - "The reaper reuses the existing seams verbatim (idempotent destroyCt, _db_used_vmids shape, getEvents oldest-first, guarded stopWorkspace) — the only new backend code is the single reconcile pass + the lifespan"

requirements-completed: [CAP-02, CAP-03]

# Metrics
duration: 12min
completed: 2026-06-12
---

# Phase 4 Plan 01: Reconciler (reaper + idle auto-stop) + FastAPI lifespan Summary

**`Reconciler.reconcile_once()` is a pure single pass that reaps pool orphans / leaked VMIDs / timed-out `creating` rows under a load-bearing pool-range safety bound and auto-stops idle running workspaces with `reason: idle`, all driven by an injectable `now`; a FastAPI lifespan (none existed before) owns the periodic loop on the request-path singletons and cancels it cleanly on shutdown.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-06-11T23:53:53Z
- **Completed:** 2026-06-12T00:05:16Z
- **Tasks:** 3
- **Files modified:** 5 (3 created, 2 modified)

## Accomplishments

- **Reaper (CAP-03):** `_reap()` destroys in-pool CTs with no live DB row (orphans / leaked VMIDs) under the load-bearing `if vmid in pool` safety bound — the Fake's `usedVmids()` is unfiltered, so the bound MUST live in the reconciler (T-04-01A). Row-less reaps audit via a structured `reaper.destroyed` log line (the events FK needs a live `workspaceId`). Timed-out `creating` rows get their CT destroyed (idempotent), status set to `error`, and a per-row `reaper.timed_out` event with the fixed `{"reason": "creating timeout"}` literal.
- **Idle auto-stop (CAP-02):** `_auto_stop()` derives idle purely from the terminal connect/disconnect event log — idle iff the LAST terminal event is a `terminal.disconnected` older than `idle_window_s`. A reconnect flips the last event back to `connected` (not idle, Pitfall 2); a never-connected workspace is spared. Stops go through the guarded `stopWorkspace(reason="idle")` so `reason: idle` reaches the `workspace.stopped` event data for the UI badge.
- **Injectable now (FROZEN guardrail 5):** the whole reconcile is a pure function of (DB state, compute state, `now`) — zero `asyncio.sleep`, zero wall-clock, zero `freezegun`. The tests drive one `reconcile_once()` per case with an explicit `now`.
- **FastAPI lifespan (Task 2):** added the first lifespan in `main.py` — `build_reconciler()` composes the reconciler from the SAME `get_compute()`/`get_db()` singletons the routers use (a fresh Fake would see an empty fleet), `_reconcile_loop` survives a failing pass via a broad except, and the lifespan cancels + suppresses `CancelledError` on shutdown (Pitfall 4).
- **CI wiring (Task 3):** the `static-gates` job now runs the three Phase-4 hermetic tiers (`test_reconciler`, `test_capacity_race`, `test_lifespan`) over the Fake, so a reaper/auto-stop/capacity/lifespan regression fails CI, not only the dev-homelab smoke. No new third-party action; permissions + SHA pins unchanged.

## Task Commits

Task 1 followed the TDD RED -> GREEN cycle; no refactor commit was needed (the GREEN diff was already minimal):

1. **Task 1 (RED): failing single-pass reconciler tests** - `e1b7547` (test)
2. **Task 1 (GREEN): Reconciler.reconcile_once() reaper + idle auto-stop** - `8ebaf62` (feat)
3. **Task 2: FastAPI lifespan owns the periodic reconcile task** - `26aa740` (feat)
4. **Task 3: CI static-gates runs the Phase-4 hermetic tiers** - `84ea556` (ci)

## Files Created/Modified

- `api/services/reconciler.py` (new) - `Reconciler(compute, db, settings, service, now=None)` with `reconcile_once()` -> `_reap()` then `_auto_stop()`; the pool-range bound, the structured-log-vs-event split, the idle `term[-1]` keying, and a tz-aware `_parse` helper. Imports ONLY `ComputeProvider`, `DbProvider`, `Settings`, `WorkspaceService`, `_safe` (seam discipline).
- `api/tests/unit/test_reconciler.py` (new) - 8 hermetic single-pass tests: in-pool orphan destroyed + out-of-pool spared + live-owned spared; timed-out `creating` -> error + event; fresh `creating` not swept; idle -> `stopWorkspace(reason=idle)`; reconnect + never-connected not stopped; `reaper.*` event carries no secret.
- `api/main.py` - added `build_reconciler()`, `_reconcile_loop()`, `lifespan()`, and `lifespan=lifespan` on the `FastAPI(...)` construction; new imports `asyncio`, `contextlib`, `logging`, `AsyncIterator`, `Reconciler`.
- `api/tests/integration/test_lifespan.py` (new) - 3 tests driving `lifespan(app)` directly: start runs a pass + task live, exit -> task cancelled (no leak); built on the same compute singleton; loop survives a failing pass.
- `.github/workflows/ci.yml` - new `api · pytest (reconciler + capacity + lifespan tiers)` step in `static-gates`.

## Decisions Made

- **`reaper.timed_out` reason is a literal, not `_safe()`-wrapped.** `_safe(exc: BaseException)` takes an exception, not a str; the `"creating timeout"` reason is a fixed non-secret literal, so wrapping it would be a type error and a misuse. `_safe` is reserved for real exception text (and re-exported from `reconciler.py` for any future reaper path that logs an exception reason).
- **Row-less orphan reaps log structurally, never `db.logEvent`.** A leaked VMID with no live row cannot satisfy the events FK (FROZEN guardrail 2 / Pitfall 3), so `logger.info("reaper.destroyed", extra={"vmid": vmid})` is the audit sink — the integer vmid carries no secret/topology. The UI drawer correctly never shows these (no workspace to open).
- **`_reconcile_loop` re-raises `CancelledError`.** The broad guard catches `Exception` (not `BaseException`), and the loop explicitly re-raises `CancelledError`, so the lifespan's `await task` unwinds cleanly on shutdown instead of the cancel being swallowed mid-pass.
- **Lifespan tested by driving `lifespan(app)` directly.** `asgi_lifespan` is not in the stack and no new dependency is allowed (FROZEN guardrail 7), and `httpx.ASGITransport` does not trigger lifespan events. Entering/exiting the async context manager directly tests the real `lifespan` function hermetically and asserts the task lifecycle (start -> running -> cancelled, no leak).

## Deviations from Plan

None - plan executed exactly as written.

The plan's note that `reaper.timed_out`'s reason is the PLAIN literal `"creating timeout"` (NOT `_safe()`-wrapped) was honored exactly; the redaction test (Test 6) proves no secret reaches a `reaper.*` event even when the owning row's name/repo embed a token, because the event data is the fixed literal only.

Within-plan engineering choices the plan delegated to Claude's discretion:
- The lifespan test harness (direct `lifespan(app)` context-manager drive) realizes the plan's "ASGI lifespan harness ... assert the task is created on startup and cancelled after shutdown" with zero new dependency.
- An extra negative test (`never-connected running workspace not auto-stopped`) and an extra reaper test (`in-pool CT with a live row spared`) were added beyond the six named behaviors to fully pin the safety bound and the idle predicate — additive coverage, not scope creep.

## Issues Encountered

- **One unused import in the RED test** (`WorkspaceCreate`) — the tests build rows via the dict-based `db.createWorkspace`, not the model. Removed before the GREEN commit; ruff clean thereafter.

## Verification

- `cd api && uv run pytest tests/unit/test_reconciler.py -x -q` — 8 passed (reaper + idle single-pass).
- `cd api && uv run pytest tests/integration/test_lifespan.py -x -q` — 3 passed (start/cancel + same-singleton + survives-failing-pass).
- `cd api && uv run pytest tests/unit/test_seam_leakage.py -q` — 4 passed (reconciler leaks no `proxmoxer`/`aiosqlite`).
- `cd api && uv run pytest tests/unit/test_reconciler.py tests/integration/test_capacity_race.py tests/integration/test_lifespan.py -q` — 12 passed (the exact CI step command).
- `cd api && uv run pytest -q` — **166 passed** (full api suite; +11 over the 155 in 04-02, no regression).
- `cd api && uv run mypy . --strict` — clean (64 source files).
- `cd api && uv run ruff check . && uv run ruff format --check .` — clean (64 files).
- `uvx --with charset-normalizer reuse lint` — 100% compliant (270/270 files; reconciler.py + both new test files carry SPDX headers).
- Real-Proxmox reaper/auto-stop acceptance remains the dev-homelab smoke (Manual-Only, 04-VALIDATION) — NOT a CI command.

## Next Phase Readiness

- **CAP-02 / CAP-03 are live in CI:** the fleet reaper + idle auto-stop run unattended via the lifespan, and a regression in either fails `static-gates`.
- The UI-06 event drawer (a separate Phase-4 plan) can surface the new `reaper.timed_out` and `workspace.stopped{reason: idle}` events; the `EVENT_BADGE` map already anticipates the `reaper.*` prefix and the `data.reason === "idle"` special-case.
- **Deferred (per CONTEXT, dev-homelab smoke not CI):** real-Proxmox acceptance of the reaper destroying real LXCs and auto-stop against a real ttyd session.

## Self-Check: PASSED

- FOUND: api/services/reconciler.py
- FOUND: api/tests/unit/test_reconciler.py
- FOUND: api/tests/integration/test_lifespan.py
- FOUND commit: e1b7547 (test RED), 8ebaf62 (feat GREEN), 26aa740 (feat lifespan), 84ea556 (ci)

---
*Phase: 04-hardening-release*
*Completed: 2026-06-12*
