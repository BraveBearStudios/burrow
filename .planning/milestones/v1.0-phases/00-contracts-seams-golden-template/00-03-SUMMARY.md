<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 00-contracts-seams-golden-template
plan: 03
subsystem: api
tags: [fastapi, pytest, pytest-asyncio, httpx, asgitransport, dependency-injection, seam-leakage]

# Dependency graph
requires:
  - phase: 00-01
    provides: pydantic-settings config, response envelope (respond/respond_error), CamelModel + compute DTOs
  - phase: 00-02
    provides: ComputeProvider/DbProvider ABCs, FakeComputeProvider, SqliteProvider + 001_init.sql, Proxmox skeleton
provides:
  - "FastAPI app factory (create_app) + the single env-driven provider-selection seam (get_compute/get_db)"
  - "Hermetic pytest substrate: conftest fixtures (fake_compute, migrated tmp sqlite_db, ASGITransport client)"
  - "Five unit test files proving PLAT-02/06/07/08/09 green over Fake/Sqlite with zero Proxmox"
  - "tokenize-based seam-leakage guard that fails CI if a driver symbol leaks past its owning provider file"
affects: [phase-01-control-plane-api, saga, routers, health]

# Tech tracking
tech-stack:
  added: []  # no new deps — pytest/pytest-asyncio/httpx already pinned in 00-01
  patterns:
    - "App-factory DI by env: get_compute()/get_db() are the ONLY place concrete impls are named"
    - "Envelope error boundary registered at the ASGI edge (Exception handler -> respond_error)"
    - "tokenize-based static seam guard: strip comments AND docstrings so seam-contract prose can't trip the count"

key-files:
  created:
    - api/main.py
    - api/tests/__init__.py
    - api/tests/conftest.py
    - api/tests/unit/__init__.py
    - api/tests/unit/test_envelope.py
    - api/tests/unit/test_models.py
    - api/tests/unit/test_fake_compute.py
    - api/tests/unit/test_db_provider.py
    - api/tests/unit/test_seam_leakage.py
  modified: []

key-decisions:
  - "Provider selection isolated to get_compute()/get_db() in main.py; BURROW_COMPUTE/BURROW_DB flip the impl with no service edit (verified both fake and proxmox branches at runtime)."
  - "Envelope contract enforced this phase only as an ASGI error boundary (Exception -> respond_error); success-wrapping middleware deferred to Phase 1 with the routers, per plan."
  - "Seam-leakage guard uses Python's tokenize to drop COMMENT and STRING tokens, so the seam *documentation* (docstrings in compute/provider.py and models/compute.py that mention proxmoxer/aiosqlite/SELECT 1) is correctly exempt while real driver usage is caught."
  - "sqlite_db fixture injects a tiny dataclass settings stand-in carrying only database_path, avoiding mutation of the module-level Settings singleton."

patterns-established:
  - "Pattern: the app factory is the lone composition root — concrete providers imported nowhere else."
  - "Pattern: hermetic fixtures (in-memory Fake + migrated tmp SQLite) make the whole contract layer CI-provable with no network/Proxmox/sleeps."
  - "Pattern: static seam enforcement as a unit test (negative-tested: red on an injected leak, green on the tree)."

requirements-completed: [PLAT-06, PLAT-07, PLAT-08, PLAT-02, PLAT-09]

# Metrics
duration: 18min
completed: 2026-06-10
---

# Phase 0 Plan 03: App Factory + Test Substrate Summary

**FastAPI app factory with the single env-driven provider-DI seam (BURROW_COMPUTE/BURROW_DB), plus a hermetic pytest substrate (conftest + 5 unit files) that proves PLAT-02/06/07/08/09 green over Fake/Sqlite with zero Proxmox and a tokenize-based seam-leakage guard.**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-06-10T05:48:00Z (approx — research/read phase)
- **Completed:** 2026-06-10T05:57:20Z
- **Tasks:** 3
- **Files modified:** 9 created

## Accomplishments

- `api/main.py` app factory: `create_app()` registers the envelope error boundary; `get_compute()`/`get_db()` are the sole place concrete impls are named — `BURROW_COMPUTE=fake|proxmox` and `BURROW_DB=sqlite` select the backend with no service edit (both branches verified at runtime).
- `conftest.py` fixtures: `fake_compute` (in-memory deterministic), `sqlite_db` (real `001_init.sql` migration against a `tmp_path` file), and `client` (`httpx.AsyncClient` over `ASGITransport(create_app())`) ready for Phase-1 router tests.
- Four req-anchored unit files — `test_envelope.py` (PLAT-02), `test_models.py` (PLAT-09), `test_fake_compute.py` (PLAT-07/08), `test_db_provider.py` (PLAT-06) — exactly matching the VALIDATION.md verify map.
- `test_seam_leakage.py`: a `tokenize`-based guard confining `proxmoxer`/`ProxmoxAPI` to `compute/proxmoxProvider.py` and `aiosqlite`/raw SQL to `db/sqliteProvider.py` (+ `db/migrations/`); negative-tested (red on an injected `import aiosqlite` probe, green on the tree).
- Full Wave-0 gate green: `uv run pytest` = 28 passed; `ruff check`, `ruff format --check`, `mypy . --strict` (26 files), `uv lock --check`, and `reuse lint` (110/110) all pass.

## Task Commits

Each task was committed atomically (Conventional Commits + `Signed-off-by`):

1. **Task 1: FastAPI app factory + provider DI by env** - `7b9154d` (feat)
2. **Task 2: conftest fixtures + envelope/models/fake-compute/db unit tests** - `4987afc` (test)
3. **Task 3: seam-leakage guard test** - `cfb5025` (test)

**Plan metadata:** _(this commit)_ (docs: complete plan)

## Files Created/Modified

- `api/main.py` - App factory (`create_app`) + envelope error boundary + `get_compute()`/`get_db()` env-driven DI seam.
- `api/tests/__init__.py`, `api/tests/unit/__init__.py` - Test package markers (SPDX-headered).
- `api/tests/conftest.py` - `fake_compute`, migrated `sqlite_db`, and `ASGITransport` `client` fixtures.
- `api/tests/unit/test_envelope.py` - Envelope `{data,meta:{requestId,timestamp},error}` shape, requestId echo, ISO-8601 UTC timestamp (PLAT-02).
- `api/tests/unit/test_models.py` - `Workspace` snake↔camel round-trip + invalid-status rejection (PLAT-09).
- `api/tests/unit/test_fake_compute.py` - clone/start/getIp determinism, vmid reuse + exhaustion, no-op inject, lifecycle, healthcheck (PLAT-07/08).
- `api/tests/unit/test_db_provider.py` - `001_init.sql` migrate, create/get/list-by-status/softDelete/update/logEvent/healthcheck over a temp DB (PLAT-06).
- `api/tests/unit/test_seam_leakage.py` - Driver-symbol confinement guard (PLAT-06/07).

## Decisions Made

- **Provider selection lives in `main.py` only.** `get_compute()`/`get_db()` branch on `settings`; no other module imports a concrete provider. This is the spec's central "swap an impl with one env change" promise.
- **Envelope = error boundary this phase.** Routers (and success-wrapping middleware) are Phase 1; the plan scoped `create_app()` to the factory + the `respond_error` ASGI handler, which is what shipped.
- **Seam guard via `tokenize`, not grep.** A plain grep would false-positive on the seam *documentation* (docstrings in `compute/provider.py`, `models/compute.py`, and the `SELECT 1` mention in `db/provider.py`). Dropping COMMENT and STRING tokens leaves only executable identifiers, so prose can never trip the count — satisfying the plan's "never gate a count `== 0` on an unfiltered file" rule.
- **`sqlite_db` fixture uses a dataclass settings stand-in** (`database_path` only) instead of mutating the global `settings` singleton — keeps tests independent and parallel-safe.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] mypy `--strict` rejected `assert await <coro returning None> is None`**
- **Found during:** Task 2 (db + fake-compute tests)
- **Issue:** Three assertions of the form `assert await provider.method(...) is None` against methods typed `-> None` failed mypy `--strict` with `func-returns-value` (a `is None` check on a statically-None return is pointless), blocking the type-check gate.
- **Fix:** Replaced the `is None` assertions with direct calls plus an observable-side-effect assertion (`logEvent`: the workspace row is unchanged after two appends; `injectBootConfig`: the vmid remains in `usedVmids()`), preserving the behavioral intent (no-op / fire-and-forget, no raise).
- **Files modified:** `api/tests/unit/test_db_provider.py`, `api/tests/unit/test_fake_compute.py`
- **Verification:** `uv run mypy tests/ --strict` clean; the four unit files still 25 passed.
- **Committed in:** `4987afc` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking).
**Impact on plan:** The fix was required for the mypy `--strict` gate and improved the tests (asserting an observable effect rather than a tautological `is None`). No scope creep.

## Issues Encountered

None beyond the deviation above. The negative-test of the seam guard (injecting a temporary `lib/_leak_probe.py` with `import aiosqlite`) confirmed it fails loudly with a `file + symbol` message, then the probe was removed and the tree verified green.

## Known Stubs

None. The app factory's envelope is an error boundary (not a stub) and routers are explicitly Phase 1 per the plan; the Proxmox provider skeleton is owned by 00-02. No placeholder data flows to any UI.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- **Wave 0 closed.** All five VALIDATION.md test files exist at their mapped paths and pass; the per-task verify map is now green. Phase 0 backend contracts are fully CI-provable with zero Proxmox.
- **Phase 1 builds against a stable seam.** `create_app()` + `get_compute()`/`get_db()` are the composition root the create saga, state machine, and `/api/v1` routers plug into; the `client` fixture is ready for in-process router tests; the seam guard will fail CI if Phase-1 code leaks a driver symbol.
- No blockers. Real-Proxmox paths remain the dev-homelab smoke gate (unchanged).

## Self-Check: PASSED

All 9 created files exist on disk; all 3 task commits (`7b9154d`, `4987afc`, `cfb5025`) are present in the git log.

---
*Phase: 00-contracts-seams-golden-template*
*Completed: 2026-06-10*
