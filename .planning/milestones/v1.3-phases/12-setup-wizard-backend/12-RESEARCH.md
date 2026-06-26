# Phase 12: Setup Wizard Backend - Research

**Researched:** 2026-06-25
**Confidence:** HIGH — codebase claims verified by scout against live files; proxmoxer permission/auth semantics and FastAPI/Pydantic SecretStr behavior are stable, well-documented.

## What must be true (SETUP-01/02/03/07)

A guided-setup API: (1) `POST /api/v1/setup/test-connection` validates host+token strictly
read-only via the privsep token's `/access/permissions`, reports success + missing privileges,
creates zero resources; (2) `POST /api/v1/setup/verify-template` reports template exists+usable on a
node without mutating; (3) SETUP-03 readiness reuses `/api/v1/health` (degrade-not-500); (4)
`testConnection`/`verifyTemplate` exist on BOTH Fake and Proxmox with no Proxmox specifics past the
ABC; (5) the PVE token is `.env`-only, validated in-memory, NEVER persisted/returned/logged.

## Security architecture (the load-bearing design — SETUP-07, hard gate #3)

### Ephemeral validation client
The runtime `ProxmoxComputeProvider._api` is built from `.env` settings at init. The wizard validates
a token the operator just TYPED, which is NOT yet in `.env`. Therefore `testConnection` must build a
**throwaway** `proxmoxer.ProxmoxAPI(host, user=user, token_name=token_name, token_value=token_value,
verify_ssl=ca_cert_path)` from the request-body creds, run exactly one read-only call, and let it go
out of scope. It MUST NOT assign to `self._api`, MUST NOT write the token anywhere, and the function
must not return or log the token. CA-pinned TLS still applies (`verify_ssl=ca_cert_path`); never
disable verification even during setup.

### Why `GET /access/permissions` is the right read-only probe
With token auth, `GET /access/permissions` returns the EFFECTIVE permissions of the calling
identity, i.e. the privsep `user ∩ token` intersection (exactly what host-prime's GATE check uses:
`pvesh get /access/permissions --token ...`). The response is a path→{priv:1} map. Phase 12 asserts
the 9 BurrowProvisioner privileges are present at the relevant paths (pool/storage/node/template) and
reports any missing. This is a pure GET — it creates nothing, so SETUP-01's "zero resources" holds
trivially. A failed/invalid token raises a proxmoxer `ResourceException` (401/403) — caught, mapped
to `setup_auth_failed`, message token-free.

### Token redaction (defense in depth)
- `config.py`: change `proxmox_token_value: str = ""` to `SecretStr`. `SecretStr.__repr__`/`__str__`
  render `**********`, so an accidental `f"{settings}"` or validation-error never prints the token.
  Read the real value only at the proxmoxer boundary via `.get_secret_value()`.
- Request body model: the token field is `SecretStr` too (FastAPI/Pydantic redacts it in 422 bodies
  and repr).
- `setup_logging()`: set `proxmoxer`, `urllib3`, `requests` loggers to WARNING so the driver cannot
  emit the Authorization header / token at DEBUG. (The existing `_ALLOWED_EXTRA_KEYS` whitelist
  already drops a token passed via `extra=`, but does NOT stop a driver DEBUG line or an exception
  string — both are covered here.)
- Error handlers: never put a raw `str(proxmoxer_exception)` into an envelope or log — map to a
  fixed token-free message keyed by error code.

### The sentinel-token test (criterion 5 centerpiece)
Drive `test-connection` (and verify-template) with a known sentinel token value (e.g.
`SENTINEL-TOKEN-DO-NOT-LEAK`) over the mocked-proxmoxer tier, then assert the sentinel string appears
in: NO DB row (scan all tables), NO response body (`data` and `error`), and NO captured log
line/event. Use `caplog` (or the JSON log capture) + a DB scan + the response JSON. RED-if-regressed:
if anyone logs the settings object, echoes the exception text, or stores the token, the test fails.

## API contract

### ABC additions (provider-neutral)
```
async def testConnection(self, host, user, token_name, token_value) -> ConnectionResult
async def verifyTemplate(self, template_vmid, node) -> TemplateResult
```
Return DTOs (CamelModel, provider-neutral) in `api/models/compute.py`:
- `ConnectionResult { success: bool, missingPrivileges: list[str] }`
- `TemplateResult { exists: bool, usable: bool, vmid: int, node: str }`

### Proxmox impl
- `testConnection`: build ephemeral client → `to_thread(self._eph.access.permissions.get)` → compute
  `missing = REQUIRED_PRIVS - present` → `ConnectionResult(success=not missing, missingPrivileges=sorted(missing))`. On `ResourceException` 401/403 → raise `SetupAuthError` (→ `setup_auth_failed`); on connect failure → `SetupUnreachableError` (→ `setup_unreachable`).
- `verifyTemplate`: GET the template's config/status on the node; `exists` = found, `usable` = is a
  template (the `template` flag set) AND on/reachable from `node`. Not found → `TemplateResult(exists=False, usable=False, ...)` (or `setup_template_not_found` at the router, per the contract).

### Fake impl (parity, hermetic)
- `testConnection`: deterministic `ConnectionResult(success=True, missingPrivileges=[])`; honor an
  injectable `FakeFailures` toggle to return a missing-privs / auth-fail result for the negative tests.
- `verifyTemplate`: `TemplateResult(exists=True, usable=True, vmid, node)` by default; injectable
  not-found.

### Endpoints (`api/routers/setup.py`, prefix `/api/v1`)
- `POST /setup/test-connection` — body: host, user, token_name, token_value(SecretStr) → ConnectionResult envelope.
- `POST /setup/verify-template` — body: template_vmid, node → TemplateResult envelope.
- Readiness: reuse existing `GET /api/v1/health` (no new endpoint).
- New error codes in `main.py` `_SAFE_ERROR_MESSAGES`: `setup_unreachable`, `setup_auth_failed`,
  `setup_missing_privileges`, `setup_template_not_found` (all messages token-free).

### Settings read
- `DbProvider.getSetupState() -> dict` reads the singleton `settings` row (id=1; setupCompletedAt).
  Read-only this phase; the setter is Phase 13.

## Pitfalls

- Do NOT reuse `self._api` to validate a request-body token — that validates the `.env` token, not
  the operator's new one, and risks coupling. Build an ephemeral client.
- Do NOT let a raw proxmoxer exception string reach an envelope or log (it can embed auth context).
  Map to fixed codes/messages.
- Do NOT add a SecretStr without updating every read site to `.get_secret_value()` at the proxmoxer
  boundary (a SecretStr passed as a token_value would send `**********` and silently fail auth).
- Keep the two new methods provider-neutral — no `proxmoxer`/`ResourceException` type leaks past the
  ABC (the seam-leakage guard test stays green); inspect exceptions by attribute like the existing
  `_is_not_found`.
- SETUP-03 is "reuse `/api/v1/health`" — do NOT build a parallel readiness path that diverges from
  the degrade-not-500 contract.
- `testConnection` must create zero resources — only GETs. A test asserts no CT/clone appears.

## Validation Architecture

**Framework:** pytest (api). CI-provable over the Fake (endpoint happy/negative paths) + the Phase 10
mocked-proxmoxer integration tier (real-shaped `/access/permissions` map + `ResourceException`
401/403 + template-not-found). No real Proxmox.

**Wave 0 / key tests:**
- Sentinel-token leak test (criterion 5): sentinel value absent from DB / envelope / logs. HARD GATE.
- Read-only assertion: `testConnection`/`verifyTemplate` issue only GETs; zero resources created
  (assert no CT/clone, no orphan) — over the mocked-proxmoxer tier.
- Missing-privilege path: a token missing privileges → `success=False` + the exact missing names.
- Seam-leakage guard: no `proxmoxer`/Proxmox type imported in `models/`/`routers/`; the two ABC
  methods return neutral DTOs (extend the existing seam test).
- Fake parity: both methods exist + behave deterministically on the Fake.
- Health reuse: `/api/v1/health` still degrade-not-500.

**Manual-only / deferred:** real-Proxmox wizard validation → Phase 14 (ACC-02).

**Sampling:** `cd api && uv run pytest tests/integration tests/unit -q` after each task; full
`uv run pytest -q` before verification; `uv run ruff check . && uv run mypy` clean on changed files.

**Security (ASVS L1, block on HIGH):** the one HIGH-value asset is the PVE token (full
clone/start/stop/destroy authority). Threats: token-at-rest (mitigated: never persisted, `.env`-only,
SecretStr), token-in-transit-logs (mitigated: logger suppression + token-free errors + the sentinel
test), and over-privileged validation (mitigated: read-only GET-only, CA-pinned TLS, zero resources).
No new auth surface beyond v1 LAN-only (the wizard is LAN-only like the rest of v1).

## RESEARCH COMPLETE
