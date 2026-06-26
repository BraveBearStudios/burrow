---
phase: 12-setup-wizard-backend
verified: 2026-06-25T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 12: Setup Wizard Backend Verification Report

**Phase Goal:** The control plane exposes a guided-setup API surface — validate a Proxmox host/token read-only, verify the golden template, and reuse the existing health check — behind two new provider-neutral `ComputeProvider` capabilities, with the powerful PVE token kept `.env`-only and never persisted, returned, or logged.
**Verified:** 2026-06-25
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | POST /api/v1/setup/test-connection validates host+token strictly read-only via the privsep token's /access/permissions, reports success + missing privileges (9-priv BurrowProvisioner set), creates ZERO resources | ✓ VERIFIED | `routers/setup.py:65-79` wires the endpoint over `get_compute`; `proxmoxProvider.py:364-391` builds an EPHEMERAL client (never `self._api`), one GET `eph.access.permissions.get()`, `missing = REQUIRED_PRIVS - present`. `REQUIRED_PRIVS` is the exact 9-priv set (`proxmoxProvider.py:61-73`, behaviorally confirmed). `test_setup_api.py:214-236` drives the REAL provider over the mocked tier and asserts `all(m=="GET")` with only `/access/permissions` hit — zero resources proven. |
| 2 | POST /api/v1/setup/verify-template reports template exists+usable on a node, no mutation; auth errors classify as setup_auth_failed not unreachable (WR-01 fix) | ✓ VERIFIED | `proxmoxProvider.py:393-417` GET-only (`nodes(node).lxc(vmid).config.get()`), `usable=bool(config.get("template"))`, no mutation. WR-01 fix present at lines 409-415: `_is_not_found` → exists=False, then `_is_auth_error` → `SetupAuthError`, else `SetupUnreachableError` — the same triage as `testConnection`. |
| 3 | SETUP-03 readiness reuses GET /api/v1/health (degrade-not-500); no new readiness endpoint | ✓ VERIFIED | No readiness route in `routers/setup.py`; module docstring (lines 14-15) states reuse. `test_setup_api.py:184-190` asserts GET /api/v1/health still returns the `{status, db, compute}` degrade-not-500 shape. Behavioral check: `/api/v1/health` is registered; the only setup routes are `test-connection` + `verify-template`. |
| 4 | testConnection + verifyTemplate on BOTH Fake and Proxmox impls; provider-neutral ConnectionResult/TemplateResult DTOs; NO proxmoxer type past the ABC (seam guard extended + green) | ✓ VERIFIED | Both methods on Proxmox (`proxmoxProvider.py:364,393`), Fake (`fakeProvider.py:239,253`), and `@abstractmethod` on the ABC (`provider.py:191,211`). DTOs are `CamelModel` (`models/compute.py:50,68`). Seam guard extended: `test_seam_leakage.py:152-179` explicitly anchors `routers/setup.py` + `models/compute.py` as proxmoxer/ProxmoxAPI/ResourceException-free; suite green (33/33 setup-related tests pass). |
| 5 | SETUP-07 HARD GATE: PVE token .env-only, validated in-memory via ephemeral client, NEVER persisted/returned/logged; sentinel-leak test genuinely RED-if-regressed (sweeps every sqlite_master table, both envelopes, captured logs); SecretStr on token + body, get_secret_value() only at boundaries; 422 handler strips raw input; driver loggers pinned WARNING; fixed token-free error codes | ✓ VERIFIED | `config.py:40` `proxmox_token_value: SecretStr`; body field `SecretStr` (`setup.py:55`). `.get_secret_value()` only at 3 boundaries (constructor `:89`, router `:77`, ephemeral receives it as a param `:375`). `test_setup_token_leak.py:80-143` sweeps every `sqlite_master` table (non-vacuous: asserts `settings` scanned), both envelopes, and a DEBUG StringIO log capture; plus a 422-body sentinel test (`:146-169`) and an auth-fail-envelope sentinel test (`:172-197`). 422 handler strips `input`/`ctx` (`main.py:243-261`). Loggers pinned WARNING (`logging.py:118-123`, behaviorally confirmed). Fixed token-free codes in `_SAFE_ERROR_MESSAGES` (`main.py:82-89`); errors use `raise ... from None`. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `api/models/compute.py` | ConnectionResult + TemplateResult CamelModel DTOs | ✓ VERIFIED | Both DTOs present (`:50`, `:68`), round-trip camelCase (`missingPrivileges`), provider-neutral. |
| `api/compute/provider.py` | testConnection + verifyTemplate abstract methods + SetupUnreachableError/SetupAuthError | ✓ VERIFIED | Both `@abstractmethod` (`:191`, `:211`); both ComputeError subclasses imported and mapped. |
| `api/compute/proxmoxProvider.py` | Ephemeral read-only impl + REQUIRED_PRIVS 9-set | ✓ VERIFIED | Ephemeral client (`:371-377`), 9-priv frozenset (`:61-73`), `get_secret_value()` at boundary (`:89`), WR-01 triage in verifyTemplate. |
| `api/compute/fakeProvider.py` | Deterministic Fake parity + injectable negatives | ✓ VERIFIED | Both methods (`:239`, `:253`) with `setup_auth_fails`/`setup_missing_privileges`/`setup_template_missing` toggles. |
| `api/db/provider.py` + `sqliteProvider.py` | getSetupState abstract read + read-only impl | ✓ VERIFIED | Abstract (`provider.py:102`); SELECT-only impl (`sqliteProvider.py:370-382`); no setter, no INSERT/UPDATE to settings. |
| `api/routers/setup.py` | Two /setup/* endpoints over get_compute + envelope | ✓ VERIFIED | Both endpoints, SecretStr body, `model_dump(by_alias=True)`, token read only at compute call site. |
| `api/main.py` | Four token-free setup error codes + handlers | ✓ VERIFIED | Codes in `_SAFE_ERROR_MESSAGES` (`:82-89`); `_SETUP_ERROR_MAP` (`:94-97`); `_setup_error_handler` + `_validation_error_handler` registered; setup router included. |
| `api/tests/integration/test_setup_token_leak.py` | SETUP-07 sentinel hard gate | ✓ VERIFIED | Genuinely RED-if-regressed: DB (sqlite_master, non-vacuous) + both envelopes + DEBUG log capture + 422 + auth-fail paths. |
| `docs/adr/ADR-0012-compute-provider-setup-caps.md` | ADR for the two caps + Fake parity + token-in-memory-only | ✓ VERIFIED | SPDX header, Status Accepted, Context/Decision/Consequences/Revisit trigger; em-dash-free (0 matches); next free ADR number. |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `routers/setup.py` | `ComputeProvider.testConnection/verifyTemplate` | `get_compute` DI | ✓ WIRED | `Depends(get_compute)` + `await compute.testConnection/verifyTemplate` at `:73`, `:88`. |
| `main.py` | setup error codes | `setup_unreachable/setup_auth_failed/...` | ✓ WIRED | All four codes mapped; SetupAuthError→setup_auth_failed (400), SetupUnreachableError→setup_unreachable (502). |
| `routers/setup.py` | data/meta/error envelope | `respond(result.model_dump(by_alias=True))` | ✓ WIRED | Both endpoints return `respond(...by_alias=True)`. |
| `proxmoxProvider.testConnection` | ephemeral GET /access/permissions | throwaway ProxmoxAPI from request creds | ✓ WIRED | `eph = proxmoxer.ProxmoxAPI(host,...)`; `eph.access.permissions.get()`; never `self._api`. |
| `proxmoxProvider` | ConnectionResult.missingPrivileges | `REQUIRED_PRIVS - present` | ✓ WIRED | `missing = REQUIRED_PRIVS - present` (`:390`). |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `routers/setup.py` test-connection | `result` (ConnectionResult) | `compute.testConnection()` → real `/access/permissions` GET (mocked tier) or Fake | ✓ Yes | ✓ FLOWING |
| `routers/setup.py` verify-template | `result` (TemplateResult) | `compute.verifyTemplate()` → real template config GET or Fake | ✓ Yes | ✓ FLOWING |
| `getSetupState` | `setupCompletedAt` | SELECT from singleton settings row | ✓ Yes (seeded NULL by design) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Driver loggers pinned WARNING | `setup_logging()` then assert proxmoxer/urllib3/requests level | All WARNING | ✓ PASS |
| SecretStr redaction | `Settings(proxmox_token_value=SecretStr('SENTINEL-XYZ'))` | sentinel absent from str/repr; present via get_secret_value() | ✓ PASS |
| 9-priv set exact | `len(REQUIRED_PRIVS)==9` | 9 privs, exact BurrowProvisioner set | ✓ PASS |
| Routes registered | `create_app()` route paths | test-connection + verify-template + health present | ✓ PASS |
| Setup test files | `pytest test_setup_caps test_setup_api test_setup_token_leak test_seam_leakage` | 33 passed | ✓ PASS |
| Full api suite | `uv run pytest -q` | 246 passed | ✓ PASS |
| Ruff on api | `uv run ruff check .` | All checks passed | ✓ PASS |
| Mypy on api | `uv run mypy .` | 3 errors, ALL in untouched test_node_selection.py (pre-existing, last touched phase 09); 0 in changed files | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| SETUP-01 | 12-01, 12-02 | Read-only host/token validation via /access/permissions, no resource creation | ✓ SATISFIED | Ephemeral GET-only probe + zero-resource test (GET-only assertion). |
| SETUP-02 | 12-01, 12-02 | Golden template exists/usable on target node | ✓ SATISFIED | verifyTemplate GET-only + usable=template-flag; WR-01 auth triage. |
| SETUP-03 | 12-02 | Health/readiness reuses /api/v1/health | ✓ SATISFIED | No new endpoint; health-reuse test asserts degrade-not-500 shape. |
| SETUP-07 | 12-01, 12-02 | Token .env-only, in-memory, never persisted/returned/logged | ✓ SATISFIED | SecretStr + ephemeral client + sentinel-leak hard gate (RED-if-regressed) + 422 strip + logger pins + token-free codes. |

No orphaned requirements: REQUIREMENTS.md maps exactly SETUP-01/02/03/07 to Phase 12, all claimed by the plans.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| (none) | — | No TBD/FIXME/XXX/HACK/PLACEHOLDER in any api Python source | — | No debt markers; no stubs in changed files. |

### Human Verification Required

None. All success criteria are CI-provable over the Fake + the mocked-proxmoxer tier (per ROADMAP `CI-provable: yes`). Real-Proxmox wizard validation is the by-design Phase 14 (ACC-02) smoke, NOT CI-provable here and correctly out of scope for this phase. No visual/UI surface exists this phase (UI is Phase 13).

### Gaps Summary

No gaps. All 5 roadmap success criteria and all 6+6 PLAN must-have truths are verified against real code and tests. The SETUP-07 hard gate is genuinely RED-if-regressed (the sentinel test sweeps every sqlite_master table non-vacuously, both envelopes, and a DEBUG log capture, plus the 422 and auth-fail paths). The WR-01 review finding was fixed in code (verifyTemplate now classifies auth errors as setup_auth_failed). WR-03/IN-02 test-quality findings were also addressed (auth-fail test now uses a multi-char sentinel with a non-vacuous assertion). The 3 mypy errors are confirmed pre-existing in an untouched file (test_node_selection.py, last modified in phase 09) and correctly logged as deferred. WR-02/WR-04 robustness nits are captured as a pending todo, out of scope by design. ADR-0012 is authored, em-dash-free, and honest about scope (no setSetupCompleted setter, no UI, git_credential_token intentionally excluded).

---

_Verified: 2026-06-25_
_Verifier: Claude (gsd-verifier)_
