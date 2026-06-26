---
phase: 12-setup-wizard-backend
plan: 02
subsystem: api
tags: [setup-wizard, secretstr, fastapi, proxmox, security, envelope, sentinel-token, adr]

# Dependency graph
requires:
  - phase: 12-setup-wizard-backend
    provides: "Plan 01 ConnectionResult/TemplateResult DTOs, testConnection/verifyTemplate ABC caps on both impls, SetupUnreachableError/SetupAuthError, SecretStr token, setup_logging() driver suppression, getSetupState()"
  - phase: 10-persistence-data-model
    provides: "mocked-proxmoxer integration tier (register_permissions/register_template_config) + singleton settings table"
  - phase: 00-foundation
    provides: "ComputeProvider ABC + Fake/Proxmox impls + CamelModel + the data/meta/error envelope + get_compute DI seam"
provides:
  - "POST /api/v1/setup/test-connection (SETUP-01) + POST /api/v1/setup/verify-template (SETUP-02) over get_compute + the standard envelope"
  - "Four token-free setup error codes mapped at the envelope boundary (setup_unreachable/setup_auth_failed/setup_missing_privileges/setup_template_not_found)"
  - "A leak-free RequestValidationError handler that strips raw submitted input from 422 bodies (token cannot leak via validation errors)"
  - "The SETUP-07 sentinel-token leak hard gate (RED-if-regressed: DB + envelope + logs)"
  - "Read-only/zero-resource proof (GET-only over the mocked tier) + the seam guard extended to the two new caps"
  - "ADR-0012 (ComputeProvider setup capabilities + Fake parity + token-in-memory-only)"
affects: [13-setup-wizard-ui, setup, routers/setup.py]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Setup endpoints read the SecretStr token via .get_secret_value() ONLY at the compute.testConnection() call site; never logged, returned, or persisted"
    - "Setup auth/connect failures map to dedicated token-free envelope codes via a per-subclass exception handler (never str(exc))"
    - "Leak-free 422: a RequestValidationError handler emits loc/msg/type only, never the submitted input, so a request-body secret cannot leak via validation"
    - "Sentinel-token hard gate: drive a known token through the flow, assert absence from every sqlite_master table, both envelopes, and a DEBUG-level log capture"

key-files:
  created:
    - api/routers/setup.py
    - api/tests/integration/test_setup_api.py
    - api/tests/integration/test_setup_token_leak.py
    - docs/adr/ADR-0012-compute-provider-setup-caps.md
  modified:
    - api/main.py
    - api/tests/unit/test_seam_leakage.py

key-decisions:
  - "Missing-privileges and template-not-found are the cap's SUCCESS path (200 with success=False / exists=False), NOT an HTTP error; the setup error codes are reserved for hard failures (unreachable host, rejected token)"
  - "SetupAuthError -> setup_auth_failed (400, operator-fixable input); SetupUnreachableError -> setup_unreachable (502, upstream gateway down); both FIXED token-free messages"
  - "Added a RequestValidationError handler (Rule 2 critical security) because FastAPI's default 422 echoes the raw submitted input, which would leak the SecretStr token"
  - "SETUP-03 readiness reuses GET /api/v1/health unchanged; the no-parallel-readiness-route test locks that no new readiness endpoint was added"
  - "The compute singleton is seeded directly in tests (not get_compute monkeypatch) because the router's Depends(get_compute) captures the callable at import time"

patterns-established:
  - "Per-subclass FastAPI exception handlers give typed errors their own envelope code/status without leaking the exception string"
  - "RED-if-regressed sentinel proof: a deliberate log-the-token regression flips the gate red, proving the gate bites (verified, then reverted)"

requirements-completed: [SETUP-01, SETUP-02, SETUP-03, SETUP-07]

# Metrics
duration: 28min
completed: 2026-06-25
---

# Phase 12 Plan 02: Setup Wizard API Surface + SETUP-07 Hard Gate Summary

**Two read-only `/api/v1/setup/*` endpoints over the get_compute DI + envelope contract, four token-free setup error codes, a leak-free 422 handler, and the RED-if-regressed sentinel-token leak hard gate proving the operator's PVE token never reaches the DB, an envelope, or a log line.**

## Performance

- **Duration:** ~28 min
- **Started:** 2026-06-25 (Phase 12 Plan 02 execution)
- **Completed:** 2026-06-25
- **Tasks:** 3
- **Files modified:** 6 (4 created, 2 modified)

## Accomplishments

- `POST /api/v1/setup/test-connection` (SETUP-01) and `POST /api/v1/setup/verify-template` (SETUP-02) wired over the existing `get_compute` DI seam, returning the standard `{data, meta, error}` envelope with `model_dump(by_alias=True)` camelCase. The request token is `SecretStr`, unwrapped via `.get_secret_value()` only at the `compute.testConnection(...)` call site.
- Four token-free setup error codes in `main.py` `_SAFE_ERROR_MESSAGES`, with a per-subclass exception handler mapping `SetupAuthError` to `setup_auth_failed` (400) and `SetupUnreachableError` to `setup_unreachable` (502) using FIXED messages, never `str(exc)`.
- A `RequestValidationError` handler that re-shapes 422 bodies to carry only `loc`/`msg`/`type`, never the raw submitted `input`, closing the one remaining token-leak surface in validation errors (T-12-04).
- SETUP-03 readiness reuses `GET /api/v1/health` unchanged; a route-presence test asserts no parallel readiness endpoint was introduced.
- The SETUP-07 sentinel-token leak hard gate: a known sentinel driven through both endpoints is provably absent from every `sqlite_master`-enumerated DB table (non-vacuously including `settings`), both response envelopes, and a DEBUG-level log capture. Proven RED-if-regressed by injecting a log-the-token regression (gate failed), then reverting.
- A read-only/zero-resource proof drives the REAL `ProxmoxComputeProvider` over the mocked-proxmoxer tier and asserts GET-only calls (no POST/PUT/DELETE), and the seam-leakage guard now explicitly anchors the two new caps as Proxmox-free in `routers/setup.py` and `models/compute.py`.
- ADR-0012 documents the two provider-neutral caps, Fake parity, the ephemeral read-only validation client, and the token-in-memory-only / no-token-at-rest constraint (Nygard format, zero em dashes, SPDX header).
- Full api suite green: **244 passed** (up from a 228 baseline; +16 new setup tests). Ruff + mypy clean on every changed file.

## Task Commits

Each task was committed atomically:

1. **Task 1: setup router + main.py registration + setup error codes (SETUP-01/02/03)** - `c86bf7c` (feat)
2. **Task 2: sentinel-token leak hard gate + read-only assertion + seam-guard extension (SETUP-07)** - `f869add` (test)
3. **Task 3: ADR-0012 (ComputeProvider setup capabilities)** - `8ab8693` (docs)

**Plan metadata:** (final docs commit)

_Note: Task 1 is `tdd="true"`; its RED tests and GREEN implementation are committed together as one endpoint feature unit (the test file is listed under both Task 1's verify and Task 2's files), and the RED-then-GREEN cycle was driven before the commit (7 endpoint tests RED, then GREEN). Task 2 adds the new sentinel + seam-guard test files._

## Files Created/Modified

- `api/routers/setup.py` (NEW) - The two `/api/v1/setup/*` endpoints; `TestConnectionBody`/`VerifyTemplateBody` CamelModels; SecretStr token read only at the compute call site.
- `api/main.py` - Four setup error codes + `validation_error`; `_SETUP_ERROR_MAP`; `_setup_error_handler`; `_validation_error_handler`; registered both + the `setup` router; extended the deferred import line.
- `api/tests/integration/test_setup_api.py` (NEW) - Endpoint happy/error envelopes over the Fake + read-only/GET-only proof over the mocked-proxmoxer tier + the SETUP-03 health-reuse assertion.
- `api/tests/integration/test_setup_token_leak.py` (NEW) - The SETUP-07 sentinel-token leak hard gate (DB + envelope + logs), plus an auth-fail-path leak check.
- `api/tests/unit/test_seam_leakage.py` - Added the explicit no-Proxmox-in-routers/models anchor for the two new caps + the CamelModel DTO assertion.
- `docs/adr/ADR-0012-compute-provider-setup-caps.md` (NEW) - The ADR for the two new caps.

## Decisions Made

- **Missing privileges / template-not-found are SUCCESS paths, not errors.** A token that authenticates but lacks privileges returns 200 with `success=False` and the missing names; a missing template returns 200 with `exists=False`. The setup error codes are reserved for hard failures (unreachable host, rejected token). Documented in the router docstring for the Phase 13 UI.
- **Error status mapping:** a rejected token is a 400 (operator-fixable input), an unreachable host is a 502 (upstream gateway down). Both messages are fixed and token-free.
- **The compute singleton is seeded directly in negative-path tests** (`main._compute_singleton = failing_fake`) rather than monkeypatching `main.get_compute`, because the router's `Depends(get_compute)` captures the callable object at import time.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Security] Added a leak-free RequestValidationError handler**
- **Found during:** Task 1 (the SecretStr-redacted-on-422 test)
- **Issue:** FastAPI/Pydantic v2's default 422 body echoes the raw submitted `input` for each validation error. When a sibling field (e.g. `host`) is missing, that `input` is the whole submitted body, so the operator-typed `SecretStr` token appeared as a plain string in the 422 response. The SecretStr only redacts the field's own repr, not the error's echoed `input`. This is a direct token-leak surface contradicting SETUP-07 / threat T-12-04 ("the token must never reach a data/error envelope").
- **Fix:** Registered a `RequestValidationError` handler in `main.py` that maps validation errors into the standard error envelope carrying only `loc`/`msg`/`type` per error, never `input`/`ctx`. Added a `validation_error` entry to `_SAFE_ERROR_MESSAGES`. The handler is app-wide and strictly safer for every router.
- **Files modified:** api/main.py
- **Verification:** `test_test_connection_token_is_secretstr_redacted_on_422` asserts the token string is absent from the 422 body; full suite green; ruff + mypy clean.
- **Committed in:** `c86bf7c` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 missing-critical security)
**Impact on plan:** The fix is required for SETUP-07 correctness (the plan's threat register T-12-04 mandates the token never reach an envelope, and the default 422 violated it). No scope creep: it is a single token-leak-closing handler the plan's own hard gate demands.

## Issues Encountered

- **Empty DB in the first sentinel-scan attempt.** The temp SQLite DB is migrated lazily on first DB access, and the setup endpoints never touch the DB, so the initial `sqlite_master` scan found zero tables (the assertion `expected at least one table` fired). Resolved by driving a `GET /api/v1/workspaces` (which triggers `_ensure_migrated`) before the setup flow, so the scan covers the REAL migrated schema (including `settings`); a non-vacuous assertion now confirms the scan reached the `settings` table.

## Deferred Issues

- An order-dependent flake in `tests/boot/test_burrow_boot.py::test_plugin_clone_fails_fast_without_harness_git_terminal_prompt` (fails in some full-suite orderings, passes in isolation, and passed in the final verification run) is in the boot-harness tier, not in any setup-wizard file this plan touches. Logged to `.planning/phases/12-setup-wizard-backend/deferred-items.md`; out of scope per the executor SCOPE BOUNDARY.

## Known Stubs

None. The endpoints return live `ConnectionResult`/`TemplateResult` DTOs from the compute seam; no placeholder/empty data flows to any response.

## User Setup Required

None - no external service configuration required. The Proxmox token stays operator-managed in the gitignored `.env`; the wizard validates a request-body token in memory and persists nothing new.

## Next Phase Readiness

- The wizard backend is callable: both `/api/v1/setup/*` endpoints, the four token-free error codes, the SETUP-03 health reuse, and the SETUP-07 hard gate are in place for the Phase 13 setup-wizard UI to consume.
- The hard gate (STATE blocker gate #3 / milestone criterion 5) is locked RED-if-regressed; Phase 13's `setSetupCompleted` setter must not introduce a token-at-rest write path (the sentinel scan will catch any).
- Seam-leakage guard green; no proxmoxer specifics leak past the ABC for the two new caps. ADR-0012 records the contract.

---
*Phase: 12-setup-wizard-backend*
*Completed: 2026-06-25*

## Self-Check: PASSED

- FOUND: api/routers/setup.py
- FOUND: api/tests/integration/test_setup_api.py
- FOUND: api/tests/integration/test_setup_token_leak.py
- FOUND: docs/adr/ADR-0012-compute-provider-setup-caps.md
- FOUND: .planning/phases/12-setup-wizard-backend/12-02-SUMMARY.md
- FOUND commit: c86bf7c (Task 1)
- FOUND commit: f869add (Task 2)
- FOUND commit: 8ab8693 (Task 3)
