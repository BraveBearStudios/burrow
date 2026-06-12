<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

---
phase: 01-control-plane-api
plan: 01
subsystem: database
tags: [sqlite, aiosqlite, migrations, partial-unique-index, pydantic-settings, vmid-reservation]

# Dependency graph
requires:
  - phase: 00-contracts-seams-golden-template
    provides: "DbProvider ABC, SqliteProvider over 001_init.sql, CamelModel DTOs (Workspace/WorkspaceEvent), pydantic-settings Settings, seam-leakage guard, migrated-tmp sqlite_db fixture"
provides:
  - "002_vmid_unique.sql partial unique index on workspaces(vmid) WHERE deletedAt IS NULL AND vmid IS NOT NULL — the race-safe VMID reservation arbiter (SC-3/SC-4)"
  - "Ordered, idempotent migrate() backed by a schema_migrations ledger that applies ALL migrations in filename order (fixes the Phase-0 landmine where migrate() ran only 001)"
  - "VmidTakenError on the DbProvider ABC module + mapped from a vmid-uniqueness IntegrityError in SqliteProvider.createWorkspace (the 'lost the VMID race, retry' signal)"
  - "getEvents (WS-11, oldest-first with stable rowid tiebreaker) and getByVmid (active owner of a vmid) on the ABC + SqliteProvider"
  - "Every Phase-1 Settings key with safe non-secret defaults in one config edit (capacity threshold, ttyd/clone/task timeouts, net0 net params, allowed_origin, git credential token, source-IP gate)"
  - "Integration test package (tests/integration/) + WS-10 CI proof over real SQLite"
affects: [01-02-proxmox-provider, 01-03-workspace-saga, 01-04-routers, 01-05-bootconfig]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "schema_migrations ledger: ordered glob of migrations/*.sql applied once each by stem, idempotent and re-runnable"
    - "Partial-unique INSERT as the cross-process reservation arbiter; IntegrityError on workspaces.vmid -> typed VmidTakenError so the service retries without an aiosqlite dep"
    - "Single-owner config file: all Phase-1 Settings keys land here so no later plan edits config.py (avoids cross-plan write conflicts)"

key-files:
  created:
    - api/db/migrations/002_vmid_unique.sql
    - api/tests/integration/__init__.py
    - api/tests/integration/test_vmid_reservation.py
  modified:
    - api/db/sqliteProvider.py
    - api/db/provider.py
    - api/db/postgresProvider.py
    - api/config.py
    - .env.example

key-decisions:
  - "VmidTakenError is discriminated on the SQLite message phrase 'workspaces.vmid' (the violated column), NOT the index name — SQLite reports the column for a partial-unique violation, and the 002 index is the only uniqueness on workspaces.vmid"
  - "getEvents orders by (createdAt, rowid) so same-millisecond events keep insertion order — the WS-11 oldest-first guarantee holds under timestamp collisions"
  - "PostgresProvider stub gains NotImplemented getEvents/getByVmid so extending the ABC does not make the hosted-path stub abstract"
  - "All Phase-1 Settings ship as clearly-marked LAN placeholders / empty secret defaults; real values live only in the gitignored .env (T-01-22 mitigation)"

patterns-established:
  - "Ordered ledger migrations replace the 'skip if table exists' check"
  - "Driver IntegrityError mapped to a seam-level typed error at the SqliteProvider boundary"

requirements-completed: [WS-10, WS-11]

# Metrics
duration: 22min
completed: 2026-06-10
---

# Phase 1 Plan 01: DB Foundation Summary

**Race-safe VMID reservation over SQLite — a partial-unique-index `002` migration, an ordered schema_migrations-ledger `migrate()` that actually applies it, a typed `VmidTakenError` reservation path, `getEvents`/`getByVmid`, and every Phase-1 `Settings` key in one place.**

## Performance

- **Duration:** 22 min
- **Started:** 2026-06-10T14:57:50Z
- **Completed:** 2026-06-10T15:19:24Z
- **Tasks:** 4
- **Files modified:** 8 (3 created, 5 modified)

## Accomplishments

- `002_vmid_unique.sql` partial unique index (`WHERE deletedAt IS NULL AND vmid IS NOT NULL`) is now the cross-process reservation arbiter: a duplicate-active-vmid INSERT collides, while soft-deleted tombstones and NULL vmids stay out of the index so a destroyed vmid is reusable.
- Replaced the Phase-0 landmine `migrate()` (it applied only `001`) with an ordered, idempotent `schema_migrations`-ledger runner that applies every `migrations/*.sql` in filename order, exactly once.
- `VmidTakenError` declared on the `DbProvider` ABC module and raised from `SqliteProvider.createWorkspace` on a vmid-uniqueness `IntegrityError`; other IntegrityErrors propagate unchanged.
- `getEvents` (WS-11, oldest-first) and `getByVmid` (active vmid owner) added to the ABC + SqliteProvider, with the Postgres stub kept concrete.
- Every Phase-1 `Settings` key landed in one config edit with safe non-secret defaults, mirrored into `.env.example` as placeholders.
- WS-10 is CI-proven over real SQLite: 6 integration cases (index presence, duplicate→`VmidTakenError`, destroy→recreate reuse, distinct coexistence, `getByVmid` active/soft-deleted, `getEvents` oldest-first).

## Task Commits

Each task was committed atomically (Conventional Commits + `Signed-off-by`):

1. **Task 1: 002 partial-unique index + ordered migrate() ledger** - `2b00aa7` (feat)
2. **Task 2: VmidTakenError reservation + getEvents + getByVmid** - `a972357` (feat)
3. **Task 3: Consolidate all Phase-1 Settings keys** - `324feb4` (feat)
4. **Task 4: WS-10 vmid-reservation integration proof (TDD)** - `81fe7c1` (test)

## Files Created/Modified

- `api/db/migrations/002_vmid_unique.sql` - Partial unique index on `workspaces(vmid)` (the reservation arbiter).
- `api/db/sqliteProvider.py` - Ordered ledger `migrate()`; `IntegrityError`→`VmidTakenError`; `getEvents` (createdAt, rowid); `getByVmid`.
- `api/db/provider.py` - `VmidTakenError`; abstract `getEvents`/`getByVmid`; imports `WorkspaceEvent`.
- `api/db/postgresProvider.py` - Hosted-path NotImplemented stubs for the two new methods (keeps the ABC satisfied).
- `api/config.py` - All Phase-1 `Settings` keys with safe defaults.
- `.env.example` - Mirrored settable env names (placeholders only).
- `api/tests/integration/__init__.py` - Integration test package (SPDX-headed).
- `api/tests/integration/test_vmid_reservation.py` - WS-10 CI proof.

## Decisions Made

- **VmidTakenError discriminator = `"workspaces.vmid"` phrase, not the index name.** SQLite reports a partial-unique violation as `UNIQUE constraint failed: workspaces.vmid` (the column), so matching the index name `idx_workspaces_vmid_active` never fires. The `002` index is the only uniqueness on `workspaces.vmid` (001 declares none), so the column phrase is the reliable signal.
- **`getEvents` orders by `(createdAt, rowid)`.** A `rowid` insertion-order tiebreaker makes the WS-11 oldest-first guarantee deterministic even when two events share a millisecond.
- **Postgres stub extended.** The hosted-path stub gains `getEvents`/`getByVmid` NotImplemented bodies so extending the ABC does not make it abstract.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] VmidTakenError discriminator matched the wrong substring**
- **Found during:** Task 2 (createWorkspace IntegrityError mapping)
- **Issue:** The first cut matched `"idx_workspaces_vmid_active"` in the IntegrityError text. SQLite reports a partial-unique violation as `UNIQUE constraint failed: workspaces.vmid` (the column, not the index name), so the typed `VmidTakenError` would never be raised — a duplicate active vmid would surface as a bare `aiosqlite.IntegrityError` and the saga retry path would never trigger. Caught by a pre-commit smoke test before the code shipped.
- **Fix:** Discriminate on the `"workspaces.vmid"` column phrase (the only uniqueness on that column is the 002 index).
- **Files modified:** api/db/sqliteProvider.py
- **Verification:** Smoke test + integration `test_duplicate_active_vmid_raises_vmid_taken` assert `VmidTakenError` (not a bare IntegrityError).
- **Committed in:** a972357 (Task 2 commit — never shipped the broken matcher)

**2. [Rule 1 - Bug] getEvents oldest-first ordering not deterministic on timestamp collision**
- **Found during:** Task 4 (events oldest-first assertion)
- **Issue:** `getEvents` ordered only by `createdAt` (millisecond precision). Two events logged in the same millisecond would return in arbitrary order, violating the WS-11 oldest-first contract.
- **Fix:** Added `rowid` (insertion order) as a stable tiebreaker: `ORDER BY createdAt, rowid`.
- **Files modified:** api/db/sqliteProvider.py
- **Verification:** `test_get_events_returns_log_oldest_first` green; full suite green.
- **Committed in:** 81fe7c1 (Task 4 commit)

**3. [Rule 3 - Blocking] 01-CONTEXT.md missing the SPDX header failed the repo-wide REUSE gate**
- **Found during:** Task 1 (running `reuse lint` as part of the gate)
- **Issue:** `.planning/phases/01-control-plane-api/01-CONTEXT.md` shipped without the two-line SPDX header (121/122 files compliant), failing the repo-wide REUSE/SPDX gate that this plan's success criteria require green.
- **Fix:** Added the standard HTML-comment SPDX header (matching the other planning markdown docs).
- **Files modified:** .planning/phases/01-control-plane-api/01-CONTEXT.md
- **Verification:** `reuse lint` → 122/122 compliant.
- **Committed in:** plan-metadata commit (planning doc, outside the per-task code file set)

---

**Total deviations:** 3 auto-fixed (2 bugs, 1 blocking)
**Impact on plan:** All three were necessary for correctness (VMID race signal, WS-11 ordering) or to keep the required gate green (REUSE). No scope creep — no new packages, no architecture change.

## Issues Encountered

- A stale `git status` snapshot in the initial environment suggested an empty repo; `git log` confirmed real commit history (HEAD on `0332611`). Committed normally on `main` (sequential, non-worktree).
- `reuse lint` flags generated `__pycache__/*.pyc` in the local working tree, but those are gitignored and absent in CI; clearing them confirms 122/122 source compliance.

## User Setup Required

None — no external service configuration required. New `Settings` keys ship with safe placeholder defaults; operators set real values in the gitignored `.env` when they reach the relevant phase.

## Next Phase Readiness

- The DB foundation is frozen for the rest of Phase 1: 01-02 (Proxmox provider), 01-03 (saga) reserves VMIDs through this index + `VmidTakenError`, 01-04 (routers) reads events via `getEvents`, 01-05 (bootconfig) looks up workspaces via `getByVmid` and reads `git_credential_token`/`allowed_origin`/net0 params from `Settings`.
- No blockers. Full gate green: 38 pytest passed, ruff + ruff format + mypy --strict (28 files) + `uv lock --check` + REUSE (122/122).

---
*Phase: 01-control-plane-api*
*Completed: 2026-06-10*

## Self-Check: PASSED

- Created files verified present: `002_vmid_unique.sql`, `tests/integration/__init__.py`, `tests/integration/test_vmid_reservation.py`, `01-01-SUMMARY.md`.
- Task commits verified in git history: `2b00aa7`, `a972357`, `324feb4`, `81fe7c1`.
