# Phase 12: Setup Wizard Backend - Context

**Gathered:** 2026-06-25
**Status:** Ready for planning

<domain>
## Phase Boundary

The control plane exposes a guided-setup API surface: validate a Proxmox host/token strictly
read-only, verify the golden template, and reuse the existing health check — behind two new
provider-neutral `ComputeProvider` capabilities (`testConnection`/`verifyTemplate`), with the
powerful PVE token kept `.env`-only and never persisted, returned, or logged. Requirements:
SETUP-01, SETUP-02, SETUP-03, SETUP-07. CI-provable over the Fake (implementing the two caps)
plus the Phase 10 mocked-proxmoxer tier for real-shaped error/permission paths; no real Proxmox.
ADRs authored in-phase: ADR-0012 (the two new ComputeProvider capabilities + Fake parity).
ADR-0011 (settings store) already landed in Phase 10.

Out of scope: the setup wizard UI / first-run gate (Phase 13); SETTING setupCompletedAt (Phase 13
owns the setter; Phase 12 only READS it); creating the first workspace (Phase 13); any real-infra
acceptance (Phase 14).
</domain>

<decisions>
## Implementation Decisions

### Token flow & security (SETUP-07 — the hard gate)
- Token arrives in the **request body, transient**: the wizard POSTs host + user + token_name +
  token_value; `testConnection` builds an **ephemeral read-only proxmoxer client** from the passed
  creds, validates in-memory, and DISCARDS it. It NEVER touches `self._api`, NEVER writes the token
  to the DB, NEVER returns it in any `data`/`error` envelope, and NEVER writes it to any log line or
  event blob. The operator commits the validated token to the gitignored `.env` separately (for the
  runtime provider's `__init__`).
- Redaction hardening: wrap the config token field (`proxmox_token_value`) AND the request-body
  token in Pydantic `SecretStr` (so `__repr__`/validation errors redact it); suppress the
  `proxmoxer`, `urllib3`, and `requests` loggers to WARNING in `setup_logging()` (so the driver
  cannot echo the token at DEBUG). Add the criterion-5 **sentinel-token test**: drive a setup flow
  with a known sentinel token value and assert it appears in NO DB row, NO response envelope, and NO
  emitted log line / event.
- `setupCompletedAt`: Phase 12 adds a **read-only** `getSetupState()` on the DbProvider seam; the
  setter (`setSetupCompleted`) is DEFERRED to Phase 13 (the UI completes setup). Phase 12 mutates
  nothing.
- Required-privilege set asserted by `testConnection`: the documented **BurrowProvisioner 9-priv
  set** — `VM.Audit VM.Clone VM.Allocate VM.Config.Network VM.Config.Options VM.PowerMgmt
  Datastore.AllocateSpace Datastore.Audit Sys.Audit` (the exact set host-prime
  `00-api-user-role.sh` grants). Missing privileges are reported, none are created.

### API contract & ABC shape
- Two new ABC methods on `ComputeProvider` (after `healthcheck()`), implemented on BOTH Proxmox and
  Fake (seam-leakage guard stays green — no Proxmox specifics past the ABC):
  - `testConnection(host, user, token_name, token_value) -> ConnectionResult` (auth + privilege
    assertion, read-only).
  - `verifyTemplate(template_vmid, node) -> TemplateResult` (template availability, read-only).
- Return types are provider-neutral Pydantic `CamelModel` DTOs in `api/models/compute.py`:
  - `ConnectionResult { success: bool, missingPrivileges: list[str] }` (flat privilege-name list,
    empty when success).
  - `TemplateResult { exists: bool, usable: bool, vmid: int, node: str }`.
- Endpoints (new `api/routers/setup.py`, registered in `main.py` under `/api/v1`):
  - `POST /api/v1/setup/test-connection` (SETUP-01)
  - `POST /api/v1/setup/verify-template` (SETUP-02)
  - SETUP-03 readiness **reuses the existing `/api/v1/health`** directly (degrade-not-500 shape) —
    NO new readiness endpoint.

### Error contract & template check
- New setup-specific envelope `error.code`s so the Phase 13 UI can differentiate:
  `setup_unreachable`, `setup_auth_failed`, `setup_missing_privileges`, `setup_template_not_found`.
  Error messages are token-free (no raw proxmoxer exception text that could embed creds).
- `verifyTemplate` "usable" = exists AND is a template (the `template` flag set) AND reachable on the
  target node.
- Read-only proof: `testConnection` issues only `GET /access/permissions` and `verifyTemplate` only
  template GETs — zero POST/clone. A test asserts zero resources / CTs are created (no test-clone,
  no orphan), satisfying SETUP-01's "creating zero resources."

### Claude's Discretion
- Exact ephemeral-client construction helper, the precise SecretStr plumbing, and the internal
  shape of the read-only-assertion test, at the implementer's discretion within the above.
- Whether `ConnectionResult`/`TemplateResult` live in `models/compute.py` or a new `models/setup.py`
  — implementer's call, as long as they stay provider-neutral.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `api/compute/provider.py:47-166` — ComputeProvider ABC (13 methods; constructor takes `settings`,
  holds connection state; new caps slot in after `healthcheck()` :163).
- `api/compute/proxmoxProvider.py:51-64` — `proxmoxer.ProxmoxAPI(host, user, token_name,
  token_value, verify_ssl=ca_cert_path)` client init; GET pattern `self._api.<path>.get(...)` via
  `asyncio.to_thread`; `_is_not_found` (:344) inspects `status_code`/text WITHOUT importing the
  driver type (seam discipline).
- `api/compute/fakeProvider.py:64-218` — in-memory Fake; new caps return deterministic success;
  `FakeFailures` (:51-61) for injectable failures.
- `api/config.py:18-129` — Pydantic `BaseSettings`, `env_file=".env"`; token fields :33-38
  (`proxmox_token_value: str = ""` — NO SecretStr yet, the SETUP-07 risk to fix).
- `.gitignore:5-6` — `.env` / `.env.*` ignored, `!.env.example`; `.env.example:8-12` shows the shape.
- `api/routers/health.py:33-48` — `/health` degrade-not-500 (`respond({status, db, compute})`); reused for SETUP-03.
- `api/lib/envelope.py:42-57` — `respond(data)` / `respond_error(code, message)`.
- `api/main.py:249-262` — deferred router imports + `include_router`; `:53-75` `_SERVICE_ERROR_STATUS`
  / `_SAFE_ERROR_MESSAGES` for ServiceError mapping (add setup codes here).
- `api/db/migrations/003_persistent_and_settings.sql:24-28` — singleton `settings(id=1 CHECK,
  setupCompletedAt TEXT)`; `api/db/provider.py:39-99` DbProvider ABC (no setup methods yet — add
  `getSetupState()`).
- `api/lib/logging.py:25-39` `_ALLOWED_EXTRA_KEYS` whitelist (token not in it → dropped, good);
  :71-94 JsonFormatter; :97-116 `setup_logging()` (add driver-logger suppression here).
- `docs/adr/ADR-0011-setup-state-store.md` / `ADR-0013` — ADR format for ADR-0012 (no em dashes).

### Established Patterns
- `/api/v1` routes + data/meta/error envelope via `respond`/`respond_error`.
- snake_case DB → camelCase JSON via CamelModel; provider seams (DbProvider/ComputeProvider) abstract.
- Structured JSON logs with a key whitelist; secrets must never reach a log line.
- proxmoxer is synchronous → wrap in `asyncio.to_thread`; CA-pinned TLS (`verify_ssl=ca_cert_path`),
  never disabled.

### Integration Points
- `api/compute/provider.py` — add `testConnection`/`verifyTemplate` abstract methods.
- `api/compute/proxmoxProvider.py` — implement via ephemeral client + `GET /access/permissions` +
  template GET; map ResourceException → setup error codes (token-free).
- `api/compute/fakeProvider.py` — Fake parity (deterministic success + injectable failure).
- `api/models/compute.py` (or new `models/setup.py`) — `ConnectionResult`, `TemplateResult`.
- `api/config.py` — `SecretStr` for `proxmox_token_value`.
- `api/lib/logging.py` — suppress proxmoxer/urllib3/requests loggers.
- `api/routers/setup.py` (NEW) + `api/main.py` — two `/api/v1/setup/*` endpoints.
- `api/db/provider.py` + `api/db/sqliteProvider.py` — `getSetupState()` (read-only).
- `docs/adr/ADR-0012-compute-provider-setup-caps.md` (NEW).
- Tests: Fake-backed integration for the endpoints + the mocked-proxmoxer tier for the
  real-shaped permission/error paths + the sentinel-token leak test.
</code_context>

<specifics>
## Specific Ideas

- The sentinel-token test is the SETUP-07 centerpiece (STATE hard gate #3): a known sentinel value
  flows through test-connection and must appear in NO DB row, NO envelope, NO log line/event.
- `testConnection`'s ephemeral client is the load-bearing security design: a NEW token (not yet in
  `.env`) is validated with a throwaway read-only client; the runtime client (`self._api`) is built
  only from `.env` at provider init and is never the validation path.
- The 9-priv set ties the wizard's capability assertion to exactly what host-prime grants, so a
  partially-provisioned host surfaces precise missing privileges.
</specifics>

<deferred>
## Deferred Ideas

- Setting `setupCompletedAt` (the setter) + the first-run gate + create-first-workspace — Phase 13.
- The setup wizard UI — Phase 13.
- Real Proxmox validation of the wizard — Phase 14 (ACC-02).
- Persisting the token anywhere other than the operator-managed `.env` — explicitly out of scope by
  design (token-at-rest ADR avoided).
</deferred>
