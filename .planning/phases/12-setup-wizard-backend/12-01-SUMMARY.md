---
phase: 12-setup-wizard-backend
plan: 01
subsystem: api
tags: [proxmox, proxmoxer, secretstr, compute-provider, setup-wizard, pydantic, security]

# Dependency graph
requires:
  - phase: 10-persistence-data-model
    provides: "003 migration singleton settings(id=1, setupCompletedAt) table + the mocked-proxmoxer integration tier (mock_proxmox factories)"
  - phase: 00-foundation
    provides: "ComputeProvider ABC + FakeComputeProvider + ProxmoxComputeProvider + CamelModel + DbProvider seam"
provides:
  - "ConnectionResult/TemplateResult provider-neutral CamelModel DTOs"
  - "ComputeProvider.testConnection/verifyTemplate abstract caps + both impls (Proxmox ephemeral read-only client + Fake parity)"
  - "SetupUnreachableError/SetupAuthError token-free ComputeError subclasses"
  - "proxmox_token_value as SecretStr (read only via get_secret_value at the proxmoxer boundary)"
  - "setup_logging() pins proxmoxer/urllib3/requests loggers to WARNING"
  - "DbProvider.getSetupState() read-only singleton-settings read"
  - "mock_proxmox register_permissions/register_template_config factories"
affects: [13-setup-wizard-ui, setup, routers/setup.py, ADR-0012]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Ephemeral read-only validation client: a request-body token is validated via a throwaway proxmoxer client built from the passed creds, never self._api, discarded after one GET"
    - "SecretStr at the seam: the secret is read only via .get_secret_value() at the proxmoxer boundary; masked everywhere else"
    - "Token-free fixed error messages: setup errors never interpolate the raw driver exception string"

key-files:
  created:
    - api/tests/unit/test_setup_caps.py
  modified:
    - api/models/compute.py
    - api/compute/provider.py
    - api/compute/proxmoxProvider.py
    - api/compute/fakeProvider.py
    - api/config.py
    - api/lib/logging.py
    - api/db/provider.py
    - api/db/sqliteProvider.py
    - api/tests/integration/mock_proxmox.py
    - api/tests/integration/test_mock_proxmox.py
    - api/tests/integration/test_proxmox_provider.py

key-decisions:
  - "testConnection builds an EPHEMERAL proxmoxer client from the passed request-body creds (never self._api) and issues exactly one read-only GET /access/permissions; zero resources created (SETUP-01)"
  - "REQUIRED_PRIVS is the exact host-prime BurrowProvisioner 9-priv frozenset; missing = REQUIRED_PRIVS - present, returned sorted; present privs unioned across all permission paths"
  - "proxmox_token_value converted to SecretStr; git_credential_token left UNTOUCHED (out of SETUP-07 scope, has other consumers)"
  - "setup errors carry FIXED token-free messages; the raw proxmoxer exception string is never interpolated (SETUP-07)"
  - "getSetupState is read-only this phase; the setter is deferred to Phase 13 (ADR-0011)"

patterns-established:
  - "Ephemeral-client read-only validation for operator-typed secrets (validate-in-memory, never persisted)"
  - "FakeFailures setup toggles (setup_missing_privileges/setup_auth_fails/setup_template_missing) for declarative negative-path parity"

requirements-completed: [SETUP-01, SETUP-02, SETUP-07]

# Metrics
duration: 22min
completed: 2026-06-25
---

# Phase 12 Plan 01: Setup Wizard Backend Foundation Summary

**Two read-only ComputeProvider setup caps (testConnection over an ephemeral GET /access/permissions 9-priv probe + verifyTemplate) with Fake parity, SecretStr token hardening, driver-logger suppression, and a read-only getSetupState seam.**

## Performance

- **Duration:** ~22 min
- **Started:** 2026-06-25 (Phase 12 execution)
- **Completed:** 2026-06-25
- **Tasks:** 3
- **Files modified:** 11 (1 created, 10 modified)

## Accomplishments

- `ConnectionResult` / `TemplateResult` provider-neutral CamelModel DTOs that round-trip camelCase (`missingPrivileges`).
- `testConnection`/`verifyTemplate` on the `ComputeProvider` ABC plus BOTH implementations: the real Proxmox impl validates an operator-typed token with an EPHEMERAL throwaway client over a single read-only `GET /access/permissions`, asserts the documented 9-priv BurrowProvisioner set, creates zero resources, and maps auth/connect failures to token-free `SetupAuthError`/`SetupUnreachableError`; the Fake is deterministic with three injectable negative paths.
- SETUP-07 token defenses: `proxmox_token_value` is now `SecretStr` (read only via `.get_secret_value()` at the proxmoxer boundary), and `setup_logging()` pins `proxmoxer`/`urllib3`/`requests` to WARNING so the driver cannot echo the token at DEBUG.
- `DbProvider.getSetupState()` read-only seam reading the singleton `settings` row (no setter this phase).
- Full api suite green: **228 passed** (up from a 217 baseline; +11 new setup-cap tests). Seam-leakage guard stays green — no proxmoxer type crosses the ABC.

## Task Commits

Each task was committed atomically:

1. **Task 1: DTOs + ABC methods + setup ComputeError subclasses + getSetupState seam** - `304b504` (feat)
2. **Task 2: Proxmox + Fake implementations + sqlite getSetupState** - `b8af4a2` (feat)
3. **Task 3: Token hardening - SecretStr config + driver-logger suppression + tests** - `a3f513a` (feat)

**Plan metadata:** (final docs commit)

## Files Created/Modified

- `api/models/compute.py` - Added `ConnectionResult` + `TemplateResult` CamelModel DTOs.
- `api/compute/provider.py` - Added `testConnection`/`verifyTemplate` abstract methods + `SetupUnreachableError`/`SetupAuthError`.
- `api/compute/proxmoxProvider.py` - `REQUIRED_PRIVS` 9-set, ephemeral read-only `testConnection`, GET-only `verifyTemplate`, `_flatten_privileges`/`_is_auth_error` helpers, `.get_secret_value()` at the token boundary.
- `api/compute/fakeProvider.py` - Deterministic `testConnection`/`verifyTemplate` + `FakeFailures` setup toggles.
- `api/config.py` - `proxmox_token_value` -> `SecretStr` (git_credential_token untouched).
- `api/lib/logging.py` - `setup_logging()` pins proxmoxer/urllib3/requests to WARNING (idempotent).
- `api/db/provider.py` - `getSetupState()` abstract read.
- `api/db/sqliteProvider.py` - `getSetupState()` singleton-row read (read-only).
- `api/tests/integration/mock_proxmox.py` - `register_permissions`/`register_template_config` factories.
- `api/tests/integration/test_mock_proxmox.py`, `test_proxmox_provider.py` - `_Settings` stubs -> SecretStr.
- `api/tests/unit/test_setup_caps.py` (NEW) - 6 Proxmox cap cases + 4 Fake-parity cases + SecretStr redaction proof.

## Decisions Made

- The ephemeral validation client is the load-bearing security design: a NOT-yet-`.env` token is validated with a throwaway read-only client, never `self._api`. The token is never stored, returned, or logged.
- `_flatten_privileges` unions present privilege names across ALL permission paths (the privsep token grants the 9 privs at pool/storage/node paths), so a priv present at any relevant path counts.
- Setup errors use fixed token-free messages keyed by failure kind, not the raw proxmoxer exception text.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated the two `_Settings` stubs to SecretStr in Task 2 instead of Task 3**
- **Found during:** Task 2 (Proxmox impl)
- **Issue:** Task 2 wired `.get_secret_value()` at the constructor `token_value=` site, which immediately broke the two existing `_Settings` test stubs (plain-str `proxmox_token_value`) with `AttributeError` — the mocked-proxmoxer / proxmox-provider suites would have gone red between Task 2 and Task 3.
- **Fix:** Converted `proxmox_token_value` to `SecretStr("test-token")` in `test_mock_proxmox.py` and `test_proxmox_provider.py` as part of Task 2 (the plan lists these files under Task 3, but the breaking change is introduced in Task 2). Keeps the suite green incrementally.
- **Files modified:** api/tests/integration/test_mock_proxmox.py, api/tests/integration/test_proxmox_provider.py
- **Verification:** `tests/integration/test_mock_proxmox.py` + `test_proxmox_provider.py` green after Task 2 (34 passed including seam-leakage).
- **Committed in:** b8af4a2 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** The stub update was always required for the SecretStr change; only its commit boundary moved earlier (Task 2 vs Task 3) to keep the suite green at every commit. No scope change — the same edits the plan prescribed, end state identical.

## Issues Encountered

- None during planned work. The SecretStr boundary, ephemeral client, logger suppression, and getSetupState all landed as designed.

## Deferred Issues

- 3 pre-existing mypy errors in `api/tests/unit/test_node_selection.py` (LogRecord dynamic `extra=` attributes `considered`/`threshold`) are unrelated to this plan (the file is untouched) and out of scope per the executor SCOPE BOUNDARY. Logged to `.planning/phases/12-setup-wizard-backend/deferred-items.md`. All files changed by this plan are ruff + mypy clean.

## Known Stubs

None. `getSetupState()` returning `{"setupCompletedAt": None}` for an unconfigured store is the seeded singleton default by design (the setter is Phase 13 per ADR-0011 / CONTEXT), not a stub.

## User Setup Required

None - no external service configuration required. The Proxmox token remains operator-managed in the gitignored `.env`; no new secret-at-rest.

## Next Phase Readiness

- The ABC, DTOs, SecretStr boundary, token-free setup errors, and `getSetupState()` are all in place for Plan 02 (the `/api/v1/setup/*` router + the sentinel-token leak hard-gate test) to consume.
- ADR-0012 (the two new ComputeProvider capabilities + Fake parity) is anticipated for this phase and should be authored in Plan 02 or as a docs follow-up — not authored in this plan.
- Seam-leakage guard green; no proxmoxer specifics leak past the ABC.

---
*Phase: 12-setup-wizard-backend*
*Completed: 2026-06-25*

## Self-Check: PASSED

- FOUND: api/tests/unit/test_setup_caps.py
- FOUND: .planning/phases/12-setup-wizard-backend/12-01-SUMMARY.md
- FOUND commit: 304b504 (Task 1)
- FOUND commit: b8af4a2 (Task 2)
- FOUND commit: a3f513a (Task 3)
