<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

---
phase: 01-control-plane-api
plan: 04
subsystem: api
tags: [fastapi, routers, middleware, cors, json-logging, security-headers, httpx, asgitransport, respx, integration-tests]

# Dependency graph
requires:
  - phase: 01-control-plane-api (Plan 01)
    provides: SqliteProvider (getEvents, getByVmid, VmidTakenError), consolidated Settings (allowed_origin), 002 partial-unique-index migration
  - phase: 01-control-plane-api (Plan 03)
    provides: WorkspaceService (create saga, stop/start/destroy), lib/errors typed service errors, lib/statemachine
provides:
  - "/api/v1 thin routers: workspaces CRUD + stop/start/destroy/events, templates, degrade-not-500 health"
  - "Structured JSON logging (JsonFormatter with field whitelist, no secrets)"
  - "SecurityHeadersMiddleware (4 headers, no HSTS) + non-* CORS from Settings"
  - "get_service DI seam composing WorkspaceService from get_compute + get_db"
  - "ServiceError/.code + ComputeError -> envelope error mapping with deterministic statuses"
  - "DbProvider.listTemplates (ABC + SqliteProvider impl + Postgres stub)"
  - "Integration tier: ASGITransport over real SQLite + Fake compute + respx stub-ttyd"
affects: [phase-02-terminal-proxy, phase-03-reproducible-workers, bootconfig-router]

# Tech tracking
tech-stack:
  added: []  # no new runtime dependency (stdlib logging per Assumption A1); respx/responses were already dev deps
  patterns:
    - "Routers are THIN: parse/validate -> service/db seam -> respond(model_dump(by_alias=True))"
    - "Error mapping via app.add_exception_handler(ServiceError/ComputeError) using .code + a safe-message table"
    - "CORS added LAST so it is outermost (handles preflight + error responses)"
    - "Deferred router import inside create_app() to break the main<->routers cycle"
    - "Process-wide compute singleton so the Fake's in-memory state survives across requests"

key-files:
  created:
    - api/lib/logging.py
    - api/lib/middleware.py
    - api/routers/__init__.py
    - api/routers/workspaces.py
    - api/routers/templates.py
    - api/routers/health.py
    - api/tests/integration/conftest.py
    - api/tests/integration/test_workspaces_api.py
    - api/tests/integration/test_health.py
    - api/tests/integration/test_security_headers.py
  modified:
    - api/main.py
    - api/db/provider.py
    - api/db/sqliteProvider.py
    - api/db/postgresProvider.py

key-decisions:
  - "Added DbProvider.listTemplates (Rule 2) so the templates router stays thin (no SQL in routers)"
  - "get_compute returns a process-wide singleton (Rule 1 fix) so the Fake's container state persists across requests"
  - "JsonFormatter uses an explicit extra-key whitelist rather than a denylist — a secret-shaped extra cannot leak by construction"
  - "Omit HSTS — v1 is a plain-HTTP LAN app; advertising Strict-Transport-Security would be misleading"

patterns-established:
  - "Thin router + Depends(get_service|get_db) + respond(by_alias) envelope wrapping"
  - "Typed-error -> envelope status table in main.py (no isinstance ladder in routers)"
  - "Integration tier: real temp SQLite + Fake compute singleton (reset per test) + respx stub ttyd over the VMID-derived IP"

requirements-completed: [PLAT-01, PLAT-03, PLAT-04, PLAT-05, WS-04, WS-05, WS-11, CICD-02]

# Metrics
duration: 12min
completed: 2026-06-10
---

# Phase 1 Plan 04: /api/v1 Routers, Logging, Security Middleware & Integration Tier Summary

**Thin `/api/v1` routers (workspaces CRUD + stop/start/destroy/events, templates, degrade-not-500 health) wired to WorkspaceService via DI, plus stdlib JSON logging with a field whitelist, a security-headers middleware, non-`*` CORS, and an ASGITransport integration tier over real SQLite + Fake compute + respx stub-ttyd.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-06-10T16:09:42Z
- **Completed:** 2026-06-10T16:21:18Z
- **Tasks:** 3
- **Files modified:** 14 (10 created, 4 modified)

## Accomplishments
- Full `/api/v1` HTTP surface: POST/GET `/workspaces` (status filter), GET `/workspaces/{id}` (404 envelope), `/stop`, `/start`, DELETE (destroy), GET `/events` (oldest-first), GET `/templates`, GET `/health` — all envelope-wrapped, camelCase via `model_dump(by_alias=True)`, mapped from typed service errors to deterministic statuses (409/404/502).
- `/health` aggregates db + compute `healthcheck()` behind a `_safe` guard and returns 200-with-`error` for a down dependency — never a 500 (PLAT-03).
- Structured JSON logging (`JsonFormatter`, stdlib only, no new dep) with an explicit extra-key whitelist so a credential or token can never reach a log line; `SecurityHeadersMiddleware` sets the four headers on every response (no HSTS); CORS restricted to `settings.allowed_origin` (non-`*`), added outermost.
- Integration tier (CICD-02): ASGITransport over a real migrated temp SQLite + the Fake compute provider + a respx stub ttyd — proves the full CRUD lifecycle, the degrade-not-500 health path, and the security/CORS/no-secrets-in-logs invariants.

## Task Commits

1. **Task 1: JSON logging + security headers + non-* CORS** - `4ad0e91` (feat)
2. **Task 2: /api/v1 routers + error mapping** - `151af0b` (feat)
3. **Task 3a: compute singleton bug fix (Rule 1)** - `4c88011` (fix)
4. **Task 3b: integration tier (TDD)** - `86d18b8` (test)

**Plan metadata:** (this commit) `docs(01-04): complete plan`

## Files Created/Modified
- `api/lib/logging.py` - `JsonFormatter` (one-line JSON, field whitelist, no secrets) + `setup_logging`.
- `api/lib/middleware.py` - `SecurityHeadersMiddleware` (nosniff/DENY/no-referrer/CSP; HSTS omitted).
- `api/routers/workspaces.py` - CRUD + stop/start/destroy/events, thin, envelope-wrapped.
- `api/routers/templates.py` - `GET /api/v1/templates` via `DbProvider.listTemplates`.
- `api/routers/health.py` - degrade-not-500 `/api/v1/health`.
- `api/routers/__init__.py` - routers package docstring.
- `api/main.py` - `setup_logging`, SecurityHeaders + CORS (outermost), `get_service` DI, `get_compute` singleton + `reset_compute`, ServiceError/ComputeError handlers, `include_router` x3.
- `api/db/provider.py` / `sqliteProvider.py` / `postgresProvider.py` - `listTemplates` (ABC + impl + stub).
- `api/tests/integration/conftest.py` - ASGITransport client over temp SQLite + Fake (reset per test) + respx stub ttyd.
- `api/tests/integration/test_workspaces_api.py` / `test_health.py` / `test_security_headers.py` - CRUD/health/security coverage.

## Decisions Made
- **`DbProvider.listTemplates` added (Rule 2):** the templates route must read templates without running SQL in the router; a thin DB-seam method is the seam-respecting way. ABC + SqliteProvider impl + Postgres stub kept in sync.
- **`get_compute` is now a process-wide singleton (Rule 1):** the Fake holds container existence in its own memory; a per-request instance made a just-created workspace invisible to the next request (stop/start/destroy 502'd). `reset_compute()` is the per-test isolation hook.
- **Extra-key whitelist over a denylist for logs:** secrets cannot leak by construction; a careless `extra={"git_credential": ...}` is dropped, asserted by a block_on=high test.
- **HSTS omitted:** LAN HTTP app, so advertising it would be misleading (RESEARCH Pattern 7).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added `DbProvider.listTemplates`**
- **Found during:** Task 2 (templates router)
- **Issue:** The templates router needs to read seeded templates, but `DbProvider` exposed no template accessor — and routers must not run SQL (seam discipline).
- **Fix:** Added `listTemplates` to the ABC, a `SqliteProvider` impl (camelCase->snake_case aliasing + TEXT-JSON decode via the model validator), and a Postgres `NotImplementedError` stub.
- **Files modified:** api/db/provider.py, api/db/sqliteProvider.py, api/db/postgresProvider.py
- **Verification:** seam-leakage guard green; templates route serves the seeded `default` template; mypy --strict clean.
- **Committed in:** `151af0b` (Task 2 commit)

**2. [Rule 1 - Bug] Compute provider must be a process-wide singleton**
- **Found during:** Task 3 (integration tier — `test_stop_then_start_round_trip` returned 502)
- **Issue:** `get_compute()` returned a fresh `FakeComputeProvider` per request, so a workspace created by the POST request did not exist in the `/stop` request's new Fake instance → `LxcNotReadyError` → 502. The DB row persisted (real SQLite) but the in-memory container did not.
- **Fix:** `get_compute()` caches a process-wide singleton keyed by `settings.compute`; added `reset_compute()` as the per-test isolation hook (called from the integration fixture so each test starts with an empty Fake).
- **Files modified:** api/main.py, api/tests/integration/conftest.py
- **Verification:** all 13 integration tests pass; full suite 94 passed; mypy --strict + ruff + format + reuse + lock all green.
- **Committed in:** `4c88011` (fix), fixture in `86d18b8`

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 bug)
**Impact on plan:** Both were necessary for correctness — the singleton fix is the linchpin that makes the Fake-backed lifecycle work across HTTP requests (and is the correct behavior for the real provider too). No scope creep; no architectural change.

## Issues Encountered
- The `main` <-> `routers` import cycle (routers import the DI seams from `main`, `main` includes the routers) was resolved by deferring the router import to inside `create_app()`, after the seam functions are defined.
- A docstring in `create_app` originally contained the literal `allow_origins=["*"]` while explaining the pitfall, tripping the acceptance grep; reworded to "a wildcard origin" so the block_on=high guard (`grep -c 'allow_origins=["*"]'` == 0) passes.

## Known Stubs
None — the templates route serves real seeded data; no placeholder/empty data flows to a response. The bootconfig router (Pattern 6) and the Proxmox-provider/vmid-reservation integration files are owned by other plans (01-05 / 01-01 / 01-02), not this one.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The `/api/v1` envelope surface, structured logging, and security middleware are live and CI-proven over the Fake — Phase 2 (terminal proxy + React UI) can build against a stable, camelCase, enveloped API.
- The integration-tier scaffolding (ASGITransport + real SQLite + Fake singleton + respx stub ttyd) is reusable by the bootconfig plan (01-05) to close the remaining CICD-02 gaps.

## Self-Check: PASSED

All 10 created source/test files and the SUMMARY exist on disk; all four task commits (`4ad0e91`, `151af0b`, `4c88011`, `86d18b8`) are present in the git history.

---
*Phase: 01-control-plane-api*
*Completed: 2026-06-10*
