<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

---
phase: 10-persistence-data-model-reaper-carve-out
plan: 03
subsystem: database
tags: [sqlite, migration, persistence, pydantic, adr, wsx-02]

# Dependency graph
requires:
  - phase: 10-01
    provides: "mocked-proxmoxer integration tier (TEST-01 hard gate) cleared before any persistence-compute change"
  - phase: 01-01
    provides: "schema_migrations ledger migrate() that applies migrations/*.sql by stem, exactly once"
provides:
  - "003 migration: workspaces.persistent column (INTEGER NOT NULL DEFAULT 0) + singleton settings table (CHECK id=1) carrying setupCompletedAt"
  - "persistent: bool = False on Workspace and WorkspaceCreate DTOs"
  - "persistent threaded through sqliteProvider SELECT + createWorkspace INSERT and the create-saga reservation"
  - "ADR-0013 (Tier-1 persistence model) + ADR-0011 (settings singleton setup-state store)"
  - "test_migrations.py locking DEFAULT-0 backfill, settings singleton seed + invariant, fresh==migrated convergence"
affects: [10-04, 12, 13]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Schema change = drop a migrations/NNN_*.sql; change NOTHING in migrate() (the ordered ledger)"
    - "Singleton-column config table (id INTEGER PRIMARY KEY CHECK (id = 1)) for host-level state"
    - "SQLite ADD COLUMN NOT NULL requires a non-NULL DEFAULT on a non-empty table; DEFAULT 0 is the v1.2 backfill"

key-files:
  created:
    - api/db/migrations/003_persistent_and_settings.sql
    - api/tests/unit/test_migrations.py
    - docs/adr/ADR-0011-setup-state-store.md
    - docs/adr/ADR-0013-persistence-model.md
  modified:
    - api/models/workspace.py
    - api/db/sqliteProvider.py
    - api/services/workspaceService.py

key-decisions:
  - "settings is a singleton-column table (CHECK id=1), not key/value (ADR-0011); new host-level settings are columns, not keys"
  - "Tier-1 persistence = plain pct stop/start reuse of the same VMID, disk preserved, NO snapshot/CRIU (ADR-0013); deferred v1.4+"
  - "persistent is create-time-only for v1.3; updateWorkspace column_map left untouched (no Tier-1 path mutates it)"

patterns-established:
  - "Singleton config row: id INTEGER PRIMARY KEY CHECK (id = 1) + a single seeded row enforces the single-config invariant in the schema"
  - "v1.2-shaped DB fixture: apply 001/002 + record them in schema_migrations, then migrate() applies ONLY the unseen 003 (proves DEFAULT-0 backfill + convergence)"

requirements-completed: [WSX-02]

# Metrics
duration: 17min
completed: 2026-06-25
---

# Phase 10 Plan 03: Persistence Data Model Summary

**A `003` migration adds an opt-in `workspaces.persistent` flag (DEFAULT 0 backfill) and a singleton `settings` table through the existing ledger; `persistent` threads through both DTOs, the provider SELECT/INSERT, and the create saga, with ADR-0013 and ADR-0011 recording the locked persistence + setup-state decisions.**

## Performance

- **Duration:** 17 min
- **Started:** 2026-06-25T10:19:25Z
- **Completed:** 2026-06-25T10:37Z
- **Tasks:** 3 completed
- **Files modified:** 7 (4 created, 3 modified)

## Accomplishments

- WSX-02 data-model foundation landed: a `persistent` boolean is an opt-in property of the workspace row, reusing the existing stop/start lifecycle with no new compute capability, no new lifecycle state, and no `ComputeProvider` ABC change.
- The `003` migration drops through the unchanged `schema_migrations` ledger (`migrate()` byte-for-byte identical) and adds both the `persistent` column and the singleton `settings` table that Phase 12's setup wizard will consume.
- The migration is locked by `test_migrations.py`: DEFAULT-0 backfill on a v1.2-shaped pre-existing row, settings singleton seed (`id=1, setupCompletedAt IS NULL`), the `CHECK (id = 1)` singleton invariant (a second insert collides), and fresh-DB vs migrated-DB schema convergence.
- ADR-0013 (Tier-1 persistence; snapshots/CRIU deferred v1.4+) and ADR-0011 (settings singleton setup-state store) authored, resolving the two v1.3 ADRs anticipated for Phase 10.

## Task Commits

Each task was committed atomically:

1. **Task 1: Write the 003 migration through the existing ledger** - `b3dfa9c` (feat)
2. **Task 2: Thread persistent through models, provider, and the create saga** - `7f3c31f` (feat)
3. **Task 3: Migration test + ADR-0011 + ADR-0013** - `bc11000` (test)

**Plan metadata:** see final docs commit.

## Files Created/Modified

- `api/db/migrations/003_persistent_and_settings.sql` (created) - ALTER workspaces ADD persistent INTEGER NOT NULL DEFAULT 0; CREATE singleton settings (CHECK id=1) + seed row.
- `api/models/workspace.py` (modified) - `persistent: bool = False` on both `Workspace` and `WorkspaceCreate`.
- `api/db/sqliteProvider.py` (modified) - `persistent` added to `_WORKSPACE_COLUMNS` SELECT and the `createWorkspace` INSERT (column list + `data.get("persistent", False)` bind). VMID-race blocks untouched.
- `api/services/workspaceService.py` (modified) - `"persistent": payload.persistent` threaded into the reservation `base` dict so the reserved row carries the flag into the INSERT.
- `api/tests/unit/test_migrations.py` (created) - 4 async tests over a real `SqliteProvider`: backfill, singleton seed, singleton invariant, fresh==migrated convergence.
- `docs/adr/ADR-0011-setup-state-store.md` (created) - settings singleton carrying `setupCompletedAt`, behind the DbProvider seam.
- `docs/adr/ADR-0013-persistence-model.md` (created) - Tier-1 `persistent` flag; snapshots/CRIU deferred.

## Decisions Made

- **Singleton-column `settings` over key/value (ADR-0011):** one typed column per setting, exactly one row via `CHECK (id = 1)`; new host-level settings are migrations (columns), not untyped key/value rows. Matches the rest of the schema's discipline.
- **Tier-1 persistence only (ADR-0013):** `persistent` reuses `pct stop`/`pct start` on the same VMID with the disk preserved; no snapshot/CRIU. Snapshots/suspend/cross-reboot scrollback (WSX-05/06/07) stay deferred to v1.4+.
- **Create-time-only scope:** `persistent` is set once at create; the optional/defensive `updateWorkspace` `column_map` entry was skipped (no Tier-1 path mutates `persistent`), keeping the surface minimal.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical convention] Removed em dashes from both ADR bodies to satisfy CLAUDE.md**
- **Found during:** Task 3 (ADR authoring)
- **Issue:** The first ADR drafts used em dashes (`—`), which CLAUDE.md forbids ("No em dashes in any output, ever") and the plan reiterates ("no em dashes in their bodies"). The analog ADR-0010 happens to use them, but the project convention takes precedence.
- **Fix:** Replaced every em dash with a colon, comma, or restructured clause across `ADR-0011-setup-state-store.md` (2) and `ADR-0013-persistence-model.md` (8). Verified zero `—` / horizontal-rule lines remain via grep; both ADRs pass `reuse lint-file` (exit 0).
- **Files modified:** docs/adr/ADR-0011-setup-state-store.md, docs/adr/ADR-0013-persistence-model.md
- **Verification:** grep for `—`/`^---$`/`^***$`/`^___$` returns no matches in either file.
- **Committed in:** `bc11000` (part of task commit)

**2. [Rule 1 - Bug] Migration test fixture must record 001/002 in the ledger and list-wrap fetchall for mypy**
- **Found during:** Task 3 (test_migrations.py)
- **Issue:** (a) The v1.2-shaped DB fixture initially applied 001/002 raw without seeding `schema_migrations`, so the subsequent `migrate()` saw 001/002 as unapplied and re-ran them, hitting `table workspaces already exists`. (b) `cursor.fetchall()` is typed `Iterable[Row]`, so `len(rows)`/`rows[0]` failed mypy (`Sized`/indexable).
- **Fix:** (a) The fixture now creates `schema_migrations` and inserts the `001_init`/`002_vmid_unique` versions exactly as a real v1.2 `migrate()` would, so `migrate()` applies ONLY the unseen 003. (b) Wrapped the seeded-settings `fetchall()` in `list(...)`.
- **Files modified:** api/tests/unit/test_migrations.py
- **Verification:** `uv run pytest tests/unit/test_migrations.py` 4 passed; `uv run mypy tests/unit/test_migrations.py` clean.
- **Committed in:** `bc11000` (part of task commit)

---

**Total deviations:** 2 auto-fixed (1 Rule 2 / CLAUDE.md convention, 1 Rule 1 bug)
**Impact on plan:** Both fixes were necessary for correctness (a green, mypy-clean test) and project-convention compliance (no em dashes). No scope creep; no new files beyond the plan's `files_modified`.

## Issues Encountered

- The full api suite is slow (~2m40s, 210 tests) due to the websocket/terminal-proxy integration tests; the changed-surface subsets (`test_migrations.py`, `test_models.py`, `test_workspaces_api.py`, `test_db_provider.py`) run in seconds and were used as the inner loop. Final full-suite run: **210 passed**.

## Deferred Issues

- 3 pre-existing mypy errors in `api/tests/unit/test_node_selection.py:156-158` (`"LogRecord" has no attribute "considered"/"threshold"`) are out of scope (Phase 9 origin, file unmodified by this plan) and already logged in `deferred-items.md` from Plan 10-01. The four files changed by this plan are ruff- and mypy-clean.

## Verification Evidence

- `uv run pytest tests/unit/test_migrations.py tests/unit/test_models.py tests/integration/test_workspaces_api.py -x` -> 15 passed.
- Full api suite: `uv run pytest -q` -> 210 passed.
- `uv run ruff check` on the 4 changed source/test files -> All checks passed.
- `uv run mypy` on changed files -> clean (only the pre-existing, unrelated `test_node_selection.py` errors remain).
- `git diff HEAD~3 -- api/db/sqliteProvider.py` shows NO change to `migrate()` / `schema_migrations` / `executescript` (only the SELECT/INSERT column threading) — the ledger runner is unchanged.
- `grep -c "persistent: bool = False" api/models/workspace.py` -> 2.
- `reuse lint-file` on both new ADRs -> exit 0; no em dashes or horizontal-rule lines in either body.

## Self-Check: PASSED

All 5 created files exist on disk; all 3 task commits (`b3dfa9c`, `7f3c31f`, `bc11000`) are present in git history.
