<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 00-contracts-seams-golden-template
plan: 02
subsystem: api
tags: [provider-seam, abc, compute, db, sqlite, aiosqlite, proxmox, fake-provider, migration]

# Dependency graph
requires:
  - "00-01: CamelModel base + Workspace/WorkspaceEvent/Template models + ComputeTask/ComputeStatus/BootConfig DTOs + Settings (BURROW_COMPUTE/BURROW_DB, database_path, proxmox_ca_cert_path)"
provides:
  - "ComputeProvider ABC (PLAT-07, SC-13): full Phase-1 saga method set + typed ComputeError hierarchy"
  - "FakeComputeProvider (PLAT-08): in-memory, deterministic (IP=10.99.0.<vmid%256>), no random/sleep, injectable FakeFailures hooks"
  - "ProxmoxComputeProvider skeleton: imports proxmoxer, reads proxmox_ca_cert_path, every method NotImplementedError"
  - "DbProvider ABC (PLAT-06): tech-spec §6.3 contract + healthcheck"
  - "SqliteProvider: aiosqlite impl + idempotent 001_init.sql migration runner; camelCase columns -> snake_case Workspace DTOs"
  - "PostgresProvider hosted-path stub (every method NotImplementedError, no driver imported)"
  - "api/db/migrations/001_init.sql: tech-spec §7.1 schema (no partial unique index)"
affects: [00-03-app-factory-test-substrate, phase-1-control-plane-api]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Provider seam as ABC returning Pydantic DTOs only; driver symbols confined to the impl file"
    - "Deterministic in-memory Fake (pure function of inputs, no random/sleep) for hermetic test tiers"
    - "DB column<->field bridge in the SQLite impl: SELECT camelCase columns AS snake_case field names; INSERT/UPDATE map snake_case -> camelCase"
    - "Idempotent migration runner: check sqlite_master then executescript 001_init.sql once"

key-files:
  created:
    - api/compute/__init__.py
    - api/compute/provider.py
    - api/compute/fakeProvider.py
    - api/compute/proxmoxProvider.py
    - api/db/__init__.py
    - api/db/provider.py
    - api/db/sqliteProvider.py
    - api/db/postgresProvider.py
    - api/db/migrations/001_init.sql
  modified:
    - api/pyproject.toml

key-decisions:
  - "ComputeProvider exposes the COMPLETE saga method set now (getNextVmid/usedVmids/cloneCt/injectBootConfig/start/stop/destroy/getStatus/getIp/getNodeMemory/waitTask/healthcheck) so Phase 1 lands against a frozen contract."
  - "FakeComputeProvider failure injection via a FakeFailures dataclass (raise_on_nth_call: dict[method,int]); shape frozen now so Phase-1 compensation tests do not refactor the constructor."
  - "Scoped mypy override [[tool.mypy.overrides]] module='proxmoxer.*' ignore_missing_imports=true — proxmoxer ships no py.typed; --strict stays in force on all first-party code."
  - "SQLite schema columns are camelCase (tech-spec §7.1 verbatim); the snake<->camel bridge lives only in sqliteProvider.py (SELECT ... AS snake; INSERT/UPDATE map back to camel)."
  - "001_init.sql carries an inline two-line `--` SPDX header (not a REUSE.toml glob); `#` is not a valid SQL comment so it is never used."

patterns-established:
  - "Typed ComputeError hierarchy (NoFreeVmidError/CloneError/TaskFailedError/LxcNotReadyError) routers will map to envelope error codes in Phase 1."
  - "Provider impls return DTOs only; no proxmoxer/aiosqlite type leaks past the interface (formally gated by the seam-leakage test in Plan 03)."

requirements-completed: [PLAT-06, PLAT-07, PLAT-08]

# Metrics
duration: 11min
completed: 2026-06-10
---

# Phase 0 Plan 02: Provider Seams Summary

**The two load-bearing provider seams: a first-class `api/compute/` package (`ComputeProvider` ABC exposing the full Phase-1 saga method set + typed error hierarchy, a deterministic in-memory `FakeComputeProvider` with injectable failure hooks, and a `ProxmoxComputeProvider` skeleton) and the `api/db/` seam (`DbProvider` ABC, `SqliteProvider` over `aiosqlite` with `001_init.sql`, and a `PostgresProvider` stub) — providers return Pydantic DTOs only, with no `proxmoxer`/`aiosqlite` driver type leaking past the interface.**

## Performance

- **Duration:** 11 min
- **Started:** 2026-06-10T04:49:16Z
- **Completed:** 2026-06-10T05:00:11Z
- **Tasks:** 3
- **Files modified:** 9 created, 1 modified

## Accomplishments

- **ComputeProvider ABC (PLAT-07, SC-13)** in the first-class `api/compute/` package: every method the Phase-1 create/stop/start/destroy saga will call — `getNextVmid`, `usedVmids`, `cloneCt(full=True)`, `injectBootConfig`, `startCt`, `stopCt`, `destroyCt`, `getStatus`, `getIp`, `getNodeMemory`, `waitTask`, `healthcheck` — declared as `@abstractmethod async def`, returning the `ComputeTask`/`ComputeStatus`/`BootConfig` DTOs from 00-01. Typed `ComputeError` hierarchy: `NoFreeVmidError`, `CloneError`, `TaskFailedError`, `LxcNotReadyError`.
- **FakeComputeProvider (PLAT-08):** in-memory `dict[int, _FakeContainer]`, fully deterministic — IP computed from VMID (`10.99.0.<vmid%256>`), no `random`, no `asyncio.sleep`. Lifecycle-accurate: `cloneCt` records a stopped container, `startCt` flips it running (and `getIp` returns the fake IP), `destroyCt` frees the VMID. `getNextVmid` skips `used` ids and raises `NoFreeVmidError` on exhaustion; `injectBootConfig` is a no-op; `waitTask` returns OK immediately. Injectable `FakeFailures` (raise on the Nth call of a named method) shaped now for Phase-1 compensation tests.
- **ProxmoxComputeProvider skeleton:** imports `proxmoxer` at module top (dep-resolution + seam confinement), `__init__` reads `settings.proxmox_ca_cert_path` for CA-pinned TLS (never `verify_ssl=False`), and every one of the 12 methods raises `NotImplementedError("<method> — Phase 1")`. No real Proxmox calls.
- **DbProvider ABC (PLAT-06):** tech-spec §6.3 contract (`createWorkspace`/`getWorkspace`/`listWorkspaces`/`updateWorkspace`/`softDeleteWorkspace`/`logEvent`) plus a `healthcheck` for `/health` forward-compat, all `@abstractmethod async def` returning `Workspace`/`None`.
- **SqliteProvider:** `aiosqlite` impl with an idempotent migration runner that applies `001_init.sql` once; full CRUD/log/healthcheck. Round-trips a workspace through `createWorkspace`/`getWorkspace`, filters `listWorkspaces` by status, soft-deletes (excluded from get/list), appends events, and passes `healthcheck`. The snake_case↔camelCase column bridge lives only here.
- **`001_init.sql`:** tech-spec §7.1 schema **verbatim** — `workspaces`/`events`/`templates`, the two indexes, and the `INSERT INTO templates ... ('default', 9000)` seed — with the two-line `--` SPDX header. **No** `UNIQUE(vmid) WHERE deletedAt IS NULL` partial index (deferred to the Phase-1 `002_*` migration, SC-4).
- **PostgresProvider:** hosted-path stub behind the seam; every method `NotImplementedError`, no driver imported.
- **Gates:** `ruff check`, `ruff format --check`, and `mypy . --strict` all green across the full 17-file `api/` tree; `uv lock --check` fresh.

## Task Commits

Each task was committed atomically (Conventional Commits + DCO `Signed-off-by`):

1. **Task 1: ComputeProvider ABC + typed errors + FakeComputeProvider (PLAT-07, PLAT-08)** — `cb864fb` (feat)
2. **Task 2: ProxmoxComputeProvider skeleton (NotImplementedError bodies)** — `dd520f6` (feat)
3. **Task 3: DbProvider ABC + 001_init.sql + SqliteProvider + Postgres stub (PLAT-06)** — `190dc4c` (feat)

## Files Created/Modified

- `api/compute/__init__.py` — package marker (SPDX header)
- `api/compute/provider.py` — `ComputeProvider(ABC)` + `ComputeError`/`NoFreeVmidError`/`CloneError`/`TaskFailedError`/`LxcNotReadyError`
- `api/compute/fakeProvider.py` — `FakeComputeProvider` + `FakeFailures` + `_FakeContainer`
- `api/compute/proxmoxProvider.py` — `ProxmoxComputeProvider` skeleton (imports `proxmoxer`, reads CA cert path, `NotImplementedError` bodies)
- `api/db/__init__.py` — package marker (SPDX header)
- `api/db/provider.py` — `DbProvider(ABC)` (§6.3 + `healthcheck`)
- `api/db/sqliteProvider.py` — `SqliteProvider` (aiosqlite + migration runner + snake↔camel column bridge)
- `api/db/postgresProvider.py` — `PostgresProvider` hosted-path stub
- `api/db/migrations/001_init.sql` — tech-spec §7.1 schema (no partial unique index)
- `api/pyproject.toml` — **modified:** added a scoped `[[tool.mypy.overrides]]` for `proxmoxer.*`

## Decisions Made

- **Lock the full ComputeProvider saga surface now.** The ABC declares every method the Phase-1 saga calls (including `getNextVmid`/`usedVmids` allocation helpers, `getNodeMemory` capacity guard, `waitTask` UPID wait) even though only the Fake implements them — that is the entire point of "seams first." A missing method discovered in Phase 1 would rewire every impl + every test.
- **`FakeFailures` dataclass for injectable failures** (`raise_on_nth_call: dict[method, int]`), counted per method across the provider's lifetime; `cloneCt` raises `CloneError`, other methods `LxcNotReadyError`. The shape is frozen now so Phase-1 compensation tests build against it without refactoring the constructor.
- **Scoped mypy override for `proxmoxer.*`** (`ignore_missing_imports = true`). `proxmoxer` ships no `py.typed`, so `mypy --strict` flagged its untyped import. A per-module override confines the allowance to that one third-party module and keeps strict mode in force on every first-party file (the `proxmoxer` symbol itself stays confined to `proxmoxProvider.py`).
- **SQLite columns are camelCase** (tech-spec §7.1 verbatim: `lxcIp`, `projectRepo`, `proxmoxTid`, `workspaceId`). Rather than rename the schema, the snake↔camel bridge lives only in `sqliteProvider.py`: reads `SELECT ... AS <snake_field>` so a row maps straight onto `Workspace.model_validate`; writes map snake_case keys back to the camelCase columns.
- **`001_init.sql` carries an inline two-line `--` SPDX header**, not a `REUSE.toml` glob — `#` is not a valid SQL comment and is never used.
- **`createWorkspace` accepts snake_case keys** (`name`, `project_repo`, `node`, …) matching the model field names and the plan's verify payload; it generates a hex UUID id when none is supplied.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added a scoped mypy override for the untyped `proxmoxer` import**
- **Found during:** Task 2 (ProxmoxComputeProvider skeleton)
- **Issue:** `mypy --strict` failed on `import proxmoxer` with `[import-untyped]` — proxmoxer installs no `py.typed` marker / stubs, which blocks the required strict gate.
- **Fix:** Added `[[tool.mypy.overrides]] module = "proxmoxer.*"` with `ignore_missing_imports = true` to `api/pyproject.toml`. Strict mode stays fully in force on all first-party code; the allowance is confined to the one third-party module, and `proxmoxer` itself stays confined to `proxmoxProvider.py`.
- **Files modified:** api/pyproject.toml
- **Verification:** `uv run mypy compute --strict` and `uv run mypy . --strict` both clean; `uv lock --check` still fresh (tooling-only change, no dep delta).
- **Committed in:** `dd520f6` (Task 2 commit)

**2. [Rule 1 - Bug] Reworded `provider.py`/`postgresProvider.py` docstrings to satisfy the seam-leakage acceptance greps**
- **Found during:** Task 3 (DbProvider ABC + Postgres stub)
- **Issue:** Two acceptance criteria require `rg 'aiosqlite' api/db/provider.py` and (by intent) `asyncpg` in `postgresProvider.py` to be absent. The initial docstrings mentioned the literal tokens `aiosqlite` (describing the seam discipline) and `asyncpg` (naming the hosted-path driver), which a naive grep would flag even though neither is imported or used.
- **Fix:** Reworded both docstrings to drop the literal tokens ("the SQLite-backed v1 self-host store"; "an async Postgres driver") while preserving the seam-discipline and hosted-path intent. No code/type change.
- **Files modified:** api/db/provider.py, api/db/postgresProvider.py
- **Verification:** Confinement check passes (`aiosqlite` only in `sqliteProvider.py`; no `asyncpg` anywhere; postgres stub has exactly 7 `NotImplementedError`); ruff/format/mypy-strict re-run clean.
- **Committed in:** `190dc4c` (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking-issue, 1 acceptance-conformance bug). No architectural changes, no scope creep.
**Impact on plan:** The mypy override is necessary tooling to keep the strict gate green with an untyped third-party dep; the docstring rewords are cosmetic. Both seams are exactly the shapes the plan specified.

## TDD Gate Compliance

Tasks 1 and 3 carried `tdd="true"`, but each task's `<action>` explicitly defers its unit test to Plan 03 ("Unit test `tests/unit/test_fake_compute.py` is authored in Plan 03"; "Unit test `tests/unit/test_db_provider.py` is authored in Plan 03"). No `test(...)` RED commit exists for this plan **by design** — the test substrate (`conftest.py` + `tests/unit/*` + the seam-leakage guard) is Plan 03's deliverable per the phase plan split, consistent with how 00-01 handled the same deferral. Behavior was instead proven by the plan's inline acceptance assertions, all of which passed against the real impls:
- **Compute:** `ComputeProvider()` raises `TypeError` (abstract); `cloneCt`→`startCt`→`getIp` returns a stable, non-None `10.99.0.210`; `getNextVmid` skips `used` and raises `NoFreeVmidError` on exhaustion; `injectBootConfig` no-ops; `waitTask` returns `ok`; `destroyCt` frees the VMID; `FakeFailures` raises `LxcNotReadyError`/`CloneError` on the configured Nth call; no `random`/`asyncio.sleep` present.
- **DB:** `DbProvider()` raises `TypeError`; `migrate()` seeds `templates('default', 9000)`; `createWorkspace`→`getWorkspace` round-trips; `model_dump(by_alias=True)` emits `projectRepo`/`lxcIp`; `listWorkspaces` filters by status; `updateWorkspace` applies status/`lxc_ip`; `logEvent` appends with JSON `data`; `softDeleteWorkspace` excludes the row; `healthcheck()` is `True`.

This is a planned deferral, not a skipped gate.

## Issues Encountered

None beyond the two auto-fixed deviations. The only friction was the `proxmoxer` missing-stubs interaction with `mypy --strict` (resolved via the scoped override) and the two seam-leakage acceptance greps catching docstring tokens (resolved by rewording). All other tasks executed clean against the 00-01 foundation.

## Known Stubs

`ProxmoxComputeProvider` (all 12 methods) and `PostgresProvider` (all 7 methods) raise `NotImplementedError` **by design** — they are the documented Phase-1 / hosted-path skeletons per the plan. Neither flows to any UI. `ProxmoxComputeProvider`'s real `proxmoxer` bodies land in Phase 1 (validated only in the dev homelab); `PostgresProvider` is the additive hosted-path seam, never wired in v1. `FakeComputeProvider` + `SqliteProvider` are the fully-functional v1 impls.

## User Setup Required

None — no external service configuration for this plan. (A real `.env` with Proxmox credentials and a real Proxmox node are only needed when Phase 1 wires the real `ProxmoxComputeProvider`.)

## Next Phase Readiness

- Both ABC surfaces are frozen and CI-verifiable: Plan 03 can wire the app factory (`get_compute()`/`get_db()` DI by `BURROW_COMPUTE`/`BURROW_DB`) and author the deferred unit tests (`test_fake_compute.py`, `test_db_provider.py`) plus the formal seam-leakage guard against these impls.
- Phase 1's saga lands against a stable `ComputeProvider`/`DbProvider` contract and runs hermetically over `FakeComputeProvider` + `SqliteProvider`.
- The Phase-1 `002_*` migration adds the `UNIQUE(vmid) WHERE deletedAt IS NULL` partial index for race-safe VMID reservation (SC-3/SC-4), explicitly deferred from `001_init.sql` here.

## Self-Check: PASSED

All nine created files + the modified `pyproject.toml` verified present on disk; all three task commits (`cb864fb`, `dd520f6`, `190dc4c`) verified in `git log`.

---
*Phase: 00-contracts-seams-golden-template*
*Completed: 2026-06-10*
