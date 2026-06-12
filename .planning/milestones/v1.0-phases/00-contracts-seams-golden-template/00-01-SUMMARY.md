<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 00-contracts-seams-golden-template
plan: 01
subsystem: api
tags: [fastapi, pydantic, pydantic-settings, uv, mypy, ruff, envelope, camelcase]

# Dependency graph
requires: []
provides:
  - "uv-managed api/ project (burrow-api) with pinned runtime + dev deps and a frozen uv.lock"
  - "ruff (py312, line 100) + mypy strict + pytest (asyncio_mode=auto) tool config in api/pyproject.toml"
  - "Response envelope helper (PLAT-02): respond()/respond_error() + Meta/ApiError in lib/envelope.py"
  - "CamelModel base (PLAT-09) with alias_generator=to_camel + populate_by_name + from_attributes"
  - "Domain models: Workspace/WorkspaceCreate/WorkspaceStatus, WorkspaceEvent, Template"
  - "Compute DTOs for the ComputeProvider ABC: ComputeTask, ComputeStatus, BootConfig"
  - "pydantic-settings Settings reading .env; BURROW_COMPUTE/BURROW_DB select providers"
affects: [00-02-provider-seams, 00-03-app-factory-test-substrate, 00-04-static-ci-gates, phase-1-control-plane-api]

# Tech tracking
tech-stack:
  added:
    - "fastapi==0.136.3, uvicorn[standard]==0.49.0, pydantic==2.13.4, pydantic-settings==2.14.1"
    - "aiosqlite==0.22.1, proxmoxer==2.3.0, httpx==0.28.1"
    - "ruff==0.15.16, mypy==2.1.0, pytest==9.0.3, pytest-asyncio==1.4.0, reuse==6.2.0"
  patterns:
    - "Response envelope as a pure boundary helper (no router/service logic)"
    - "snake_case-in / camelCase-out via a single CamelModel base (no per-field hand-mapping)"
    - "Provider selection by env via Field(validation_alias=BURROW_*)"

key-files:
  created:
    - api/pyproject.toml
    - api/uv.lock
    - api/config.py
    - api/lib/__init__.py
    - api/lib/envelope.py
    - api/models/__init__.py
    - api/models/base.py
    - api/models/workspace.py
    - api/models/event.py
    - api/models/template.py
    - api/models/compute.py
  modified: []

key-decisions:
  - "Used PEP 735 [dependency-groups] for the dev set (portable) over uv-specific [tool.uv] dev-dependencies."
  - "Provider switches use Field(validation_alias=BURROW_COMPUTE/BURROW_DB); a bare field would bind the lowercase env name, not the BURROW_* name."
  - "Typed envelope helpers as data: Any -> dict[str, Any] for mypy --strict cleanliness."
  - "Config docstring/comment avoid the literal token verify_ssl to satisfy the acceptance grep while keeping the never-disable-TLS intent via proxmox_ca_cert_path."

patterns-established:
  - "Envelope helper: {data, meta:{requestId,timestamp}, error}; make_meta() defaults requestId to uuid4 and timestamp to UTC ISO-8601."
  - "CamelModel base: alias_generator=to_camel, populate_by_name=True, from_attributes=True; serialize at the boundary with model_dump(by_alias=True)."
  - "SPDX two-line # header on line 1-2 of every authored .py/.toml source file."

requirements-completed: [PLAT-02, PLAT-09]

# Metrics
duration: 12min
completed: 2026-06-10
---

# Phase 0 Plan 01: Backend Foundation Summary

**uv-managed FastAPI `api/` project with pinned deps + ruff/mypy-strict/pytest config, the `{data, meta:{requestId,timestamp}, error}` envelope helper (PLAT-02), a `CamelModel` snake↔camel base plus Workspace/Event/Template + compute DTOs (PLAT-09), and a `pydantic-settings` config that selects providers via `BURROW_COMPUTE`/`BURROW_DB`.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-06-10T00:33:11Z
- **Completed:** 2026-06-10T00:45:32Z
- **Tasks:** 4
- **Files modified:** 11 created

## Accomplishments
- uv project `burrow-api` (requires-python `==3.12.*`) with exact-pinned runtime + dev deps and a committed frozen `uv.lock`; `uv sync --frozen` and `uv lock --check` both clean.
- Tool config in `api/pyproject.toml`: `[tool.ruff]` (py312, line 100), `[tool.mypy] strict = true`, `[tool.pytest.ini_options]` (`asyncio_mode = "auto"`, `testpaths = ["tests"]`).
- PLAT-02 envelope helper: `respond()` / `respond_error()` + `Meta`/`ApiError`, producing the exact three-key shape with `requestId` + UTC ISO-8601 `timestamp` in `meta`.
- PLAT-09 model layer: `CamelModel` base with `alias_generator=to_camel`; `Workspace`/`WorkspaceCreate`/`WorkspaceStatus`, `WorkspaceEvent`, `Template`, and the `ComputeTask`/`ComputeStatus`/`BootConfig` DTOs the `ComputeProvider` ABC (Plan 02) consumes — all snake↔camel via the alias generator (no hand-mapping).
- `Settings(BaseSettings)` reading `.env` with field names matching `.env.example` exactly; `BURROW_COMPUTE=proxmox` env-binds `settings.compute == "proxmox"`; TLS validated via `proxmox_ca_cert_path`, never disabled.

## Task Commits

Each task was committed atomically:

1. **Task 1: uv project scaffold + pinned deps + tool config** - `7df34d5` (chore)
2. **Task 2: response envelope helper + Meta/ApiError (PLAT-02)** - `7ef870c` (feat)
3. **Task 3: CamelModel base + Workspace/Event/Template/Compute models (PLAT-09)** - `18620a1` (feat)
4. **Task 4: pydantic-settings config + .env contract (provider switch)** - `15b4d6a` (feat)

_Tasks 2 and 3 were marked `tdd="true"` in the plan, but the plan's action explicitly defers the unit tests (`tests/unit/test_envelope.py`, `tests/unit/test_models.py`) to Plan 03; this plan delivers only the helpers/models. Behavior was verified via the plan's inline acceptance assertions (see TDD Gate Compliance below)._

## Files Created/Modified
- `api/pyproject.toml` - uv project + pinned deps + ruff/mypy/pytest config (SPDX-headered)
- `api/uv.lock` - frozen, committed lockfile (48 resolved packages)
- `api/lib/__init__.py` - package marker (SPDX header)
- `api/lib/envelope.py` - PLAT-02 envelope helper: `respond`/`respond_error`/`make_meta`, `Meta`/`ApiError`
- `api/models/__init__.py` - package marker (SPDX header)
- `api/models/base.py` - `CamelModel` base (alias generator)
- `api/models/workspace.py` - `Workspace`, `WorkspaceCreate`, `WorkspaceStatus`
- `api/models/event.py` - `WorkspaceEvent`
- `api/models/template.py` - `Template`
- `api/models/compute.py` - `ComputeTask`, `ComputeStatus`, `BootConfig`
- `api/config.py` - `Settings(BaseSettings)` + module-level `settings`

## Decisions Made
- **PEP 735 dependency-groups** for the dev set (portable) over `[tool.uv] dev-dependencies` (uv-specific), per RESEARCH recommendation.
- **Provider switches use `Field(validation_alias="BURROW_COMPUTE"/"BURROW_DB")`** — a bare `compute: str` would bind the lowercase `compute` env var, not `BURROW_COMPUTE`. Verified the env binding with `BURROW_COMPUTE=proxmox`.
- **`data: Any -> dict[str, Any]` typing on the envelope helpers** to stay `mypy --strict` clean (bare `dict` / untyped params fail strict).
- **`.gitignore` left unchanged**: every artifact the plan named (`__pycache__/`, `*.egg-info/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.venv/`) is already present; `.venv/` already matches `api/.venv/` at any depth, so no append was needed (the plan said "only entries not already present"). Confirmed `api/.venv/` is untracked (correctly ignored).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Reworded config security note to satisfy the `verify_ssl` acceptance grep**
- **Found during:** Task 4 (pydantic-settings config)
- **Issue:** The plan's acceptance criterion requires `rg -n 'verify_ssl' api/config.py` to return nothing. The initial docstring contained the security warning "never reintroduce `verify_ssl=False`", whose literal `verify_ssl` token tripped the grep.
- **Fix:** Reworded the docstring/comment to "never disable TLS verification" / "validate TLS via CA, never disable it", preserving the security intent (CA-cert validation via `proxmox_ca_cert_path`) without the literal token.
- **Files modified:** api/config.py
- **Verification:** `grep -n 'verify_ssl' config.py` returns nothing; ruff/format/mypy-strict re-run clean.
- **Committed in:** `15b4d6a` (Task 4 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — acceptance-criterion conformance)
**Impact on plan:** Cosmetic wording only; the never-disable-TLS posture is unchanged. No scope creep.

## TDD Gate Compliance

Plan tasks 2 and 3 carried `tdd="true"`, but the plan's `<action>` for each explicitly states the corresponding unit tests are authored in **Plan 03** ("The envelope unit test ... is authored in Plan 03; this task only delivers the helper" / "The round-trip unit test ... is authored in Plan 03"). No `test(...)` RED commit exists for this plan **by design** — the test substrate (conftest + `tests/unit/*`) is Plan 03's deliverable per the phase plan split. Behavior was instead proven by the plan's own inline acceptance assertions, all of which passed:
- Envelope: `set(r)=={'data','meta','error'}`, `error is None`, `set(meta)=={'requestId','timestamp'}`, `request_id` echo, ISO-8601 UTC `timestamp`, `respond_error` shape.
- Models: snake_case in → camelCase out (`lxcIp`,`projectRepo`), camelCase input accepted (`populate_by_name`), `WorkspaceStatus` literal set, compute DTO instantiation, `BootConfig` camelCase aliases.
- Config: defaults, `BURROW_COMPUTE=proxmox` env binding, `db_kind=='sqlite'`.

This is a planned deferral, not a skipped gate.

## Issues Encountered
None — all four tasks executed against a clean greenfield `api/` tree. `uv` fetched CPython 3.12.10 automatically (host PATH had 3.13).

## Known Stubs
None that flow to UI. `proxmox_token_value=""` and `config_repo=""` are intentional empty defaults (secrets/config are supplied via gitignored `.env`, never hardcoded — per CLAUDE.md security posture). The Proxmox fields are read this phase but exercised in Phase 1.

## User Setup Required
None — no external service configuration required for this plan. (A real `.env` with Proxmox credentials is only needed when Phase 1 wires the real `ProxmoxComputeProvider`.)

## Next Phase Readiness
- The wire shapes (envelope, snake↔camel, settings keys) are locked and CI-verifiable. Plan 02 (provider seams) can build the `ComputeProvider`/`DbProvider` ABCs against stable `ComputeTask`/`ComputeStatus`/`BootConfig` + `Workspace`/`WorkspaceEvent` models.
- Plan 03 (app factory + test substrate) will author the deferred `tests/unit/test_envelope.py` and `test_models.py` against these helpers.
- Plan 04 (static CI gates + REUSE) must add a `REUSE.toml`/`.reuse/dep5` so `reuse lint` passes for the non-headerable `api/uv.lock`.

## Self-Check: PASSED

All created files verified present on disk; all four task commits verified in `git log`.

---
*Phase: 00-contracts-seams-golden-template*
*Completed: 2026-06-10*
