<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

---
phase: 13-setup-wizard-ui-first-run-gate
plan: 01
subsystem: api
tags: [fastapi, sqlite, aiosqlite, setup-gate, envelope, dbprovider]

# Dependency graph
requires:
  - phase: 10-persistence-data-model
    provides: "003 migration — singleton settings table (id=1, setupCompletedAt TEXT seeded NULL)"
  - phase: 12-setup-wizard-backend
    provides: "DbProvider.getSetupState() read-only + routers/setup.py + ADR-0011"
provides:
  - "DbProvider.setSetupCompleted() seam (ABC + SQLite UPDATE + Postgres stub)"
  - "GET /api/v1/setup/state (first-run gate read)"
  - "POST /api/v1/setup/complete (idempotent setter, no body/token)"
affects: [13-setup-wizard-ui, useSetupState, useCompleteSetup, App.tsx-gate]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Idempotent singleton stamp: UPDATE settings SET setupCompletedAt = strftime ISO WHERE id=1 (no INSERT, no uniqueness)"
    - "Setter reads itself back via getSetupState() so the returned value is exactly what was written"

key-files:
  created: []
  modified:
    - api/db/provider.py
    - api/db/sqliteProvider.py
    - api/db/postgresProvider.py
    - api/routers/setup.py
    - api/tests/integration/test_setup_api.py

key-decisions:
  - "Setter reuses the SAME strftime('%Y-%m-%dT%H:%M:%fZ','now') format softDeleteWorkspace/migrate write (no new timestamp shape)"
  - "Idempotency via a plain WHERE id=1 UPDATE — re-stamping cannot fail; the endpoint adds no new error code"
  - "Postgres stub gained BOTH getSetupState + setSetupCompleted overrides for ABC parity (getSetupState override was missing since Phase 12)"

patterns-established:
  - "Gate endpoints are get_db-backed + respond() envelope, mirroring routers/templates.py"

requirements-completed: [SETUP-04, SETUP-05]

# Metrics
duration: 18min
completed: 2026-06-26
---

# Phase 13 Plan 01: Setup Gate Backend Setter + Endpoints Summary

**The deferred Phase-12 setter lands: `DbProvider.setSetupCompleted()` (idempotent singleton stamp) plus `GET /api/v1/setup/state` and `POST /api/v1/setup/complete` over the standard envelope, proven by 4 integration tests.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-06-26T02:15:00Z
- **Completed:** 2026-06-26T02:33:13Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- Added `setSetupCompleted()` to the `DbProvider` ABC + SQLite impl (real `UPDATE settings SET setupCompletedAt = <ISO> WHERE id = 1` + commit), reusing the existing strftime timestamp format and reading the value back so the return matches the row.
- Added the two gate endpoints to `routers/setup.py`, both wired through `Depends(get_db)` + `respond(...)`: `GET /setup/state` (read) and `POST /setup/complete` (idempotent setter, no body, no token, no new error code).
- Closed the Postgres hosted-path ABC-parity gap: added `getSetupState` (missing since Phase 12 added it to the ABC) + `setSetupCompleted` `NotImplementedError` overrides so the stub stays a concrete subclass.
- Locked state-null → complete-sets → state-returns → idempotent behavior with 4 integration tests over the real-temp-SQLite + Fake app.

## Task Commits

Each task was committed atomically:

1. **Task 1: setSetupCompleted on the DbProvider seam (ABC + SQLite + Postgres stub)** - `daad470` (feat)
2. **Task 2: GET /setup/state + POST /setup/complete gate endpoints** - `8b1b366` (feat)
3. **Task 3: integration tests for state read + idempotent complete** - `659219c` (test)

**Plan metadata:** see final docs commit below.

## Files Created/Modified
- `api/db/provider.py` - Declared `setSetupCompleted` `@abstractmethod`; tightened the `getSetupState` docstring (setter no longer "deferred").
- `api/db/sqliteProvider.py` - SQLite `setSetupCompleted`: strftime-ISO `UPDATE ... WHERE id = 1` + commit, returns the value via `getSetupState`.
- `api/db/postgresProvider.py` - Added `getSetupState` + `setSetupCompleted` hosted-path `NotImplementedError` overrides (ABC parity).
- `api/routers/setup.py` - Added `GET /setup/state` + `POST /setup/complete` (get_db + respond); extended the module docstring's endpoint list to SETUP-01..05.
- `api/tests/integration/test_setup_api.py` - 4 new tests (state-null, complete-then-state, idempotent-complete, routes-registered) + docstring covered-list update.

## Decisions Made
- **Timestamp format:** matched the existing `strftime('%Y-%m-%dT%H:%M:%fZ', 'now')` SQLite idiom (`deletedAt`, migrations) rather than inventing a Python-side ISO — keeps a single timestamp shape across the schema.
- **Return-by-readback:** the setter returns `await self.getSetupState()` after the UPDATE so the envelope's `setupCompletedAt` is exactly the row value (no clock-skew between the write and the returned string).
- **No new error code:** per the module docstring and `main._SAFE_ERROR_MESSAGES`, a singleton timestamp UPDATE cannot fail — confirmed; nothing added.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added the Postgres `getSetupState` stub override**
- **Found during:** Task 1 (DbProvider seam)
- **Issue:** Phase 12 added `getSetupState` as an `@abstractmethod` to the ABC but never added the matching override to `PostgresProvider`, leaving the hosted-path stub silently abstract-incomplete. The plan's `<interfaces>` note flagged exactly this and instructed adding the parity override.
- **Fix:** Added `getSetupState` (alongside the new `setSetupCompleted`) `NotImplementedError` override so `PostgresProvider` is a concrete subclass of the ABC again.
- **Files modified:** api/db/postgresProvider.py
- **Verification:** `uv run mypy db/provider.py db/sqliteProvider.py db/postgresProvider.py` exits 0.
- **Committed in:** `daad470` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 missing-critical / ABC parity)
**Impact on plan:** The fix restores the hosted-path stub's ABC conformance the plan explicitly called for. No scope creep.

## Issues Encountered
None - all three tasks executed as written; lint/type/test green at each step.

## Known Stubs
None - the SQLite path is fully wired (real UPDATE + commit, read-back). The `PostgresProvider` `NotImplementedError` overrides are intentional hosted-path stubs (ADR-0001), not v1 stubs.

## Verification
- `cd api && uv run pytest tests/integration -k setup -q` → **20 passed** (16 prior + 4 new).
- `cd api && uv run pytest -q` → **250 passed** (full api suite; pre-existing websockets legacy DeprecationWarnings in the terminal-proxy tests are out of scope).
- `cd api && uv run mypy db/provider.py db/sqliteProvider.py db/postgresProvider.py routers/setup.py tests/integration/test_setup_api.py` → clean.
- `cd api && uv run ruff check db/ routers/setup.py tests/integration/test_setup_api.py` → clean.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The UI half of Phase 13 (`useSetupState` / `useCompleteSetup` hooks, `SetupWizard.tsx`, the `App.tsx` first-run gate, and the `NewWorkspaceModal` persistent checkbox) can now consume `GET /api/v1/setup/state` + `POST /api/v1/setup/complete` over the envelope.
- Gate ordering contract holds: the wizard's final step calls `/setup/complete` only AFTER the first-workspace create succeeds; the idempotent setter tolerates re-entry.

---
*Phase: 13-setup-wizard-ui-first-run-gate*
*Completed: 2026-06-26*

## Self-Check: PASSED

All 6 claimed files exist on disk; all 3 task commits (`daad470`, `8b1b366`, `659219c`) found in git history.
