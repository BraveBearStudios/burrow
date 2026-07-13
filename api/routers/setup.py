# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Setup router — ``/api/v1/setup/*`` guided-setup validation (SETUP-01..05).

Thin surface over the :class:`compute.provider.ComputeProvider` seam (the
``get_compute`` DI) and the :class:`db.provider.DbProvider` seam (the ``get_db``
DI). The compute endpoints validate a Proxmox host/token and the golden template
strictly READ-ONLY; the DB endpoints back the first-run gate. All return the
standard envelope:

- ``POST /setup/test-connection`` (SETUP-01) → ``ConnectionResult`` (success +
  missingPrivileges); creates zero resources.
- ``POST /setup/verify-template`` (SETUP-02) → ``TemplateResult`` (exists/usable);
  mutates nothing.
- ``GET /setup/state`` (SETUP-04) → ``{setupCompletedAt}`` for the wizard gate;
  reads the singleton settings row, mutates nothing.
- ``POST /setup/complete`` (SETUP-05) → ``{setupCompletedAt}`` after stamping the
  singleton; no body, no token, idempotent (a second call just re-stamps).

SETUP-03 readiness reuses the existing ``GET /api/v1/health`` (degrade-not-500);
no readiness route is added here.

Token discipline (SETUP-07): the operator-typed PVE token arrives as a transient
``SecretStr`` request-body field. Its raw value is read via ``.get_secret_value()``
ONLY at the ``compute.testConnection(...)`` call site — never logged, never put in
a ``respond_error`` message, never persisted. Auth/connect failures surface as the
typed ``SetupAuthError``/``SetupUnreachableError`` (mapped to fixed token-free
envelope codes in ``main.py``); the raw driver exception string is never echoed.

Contract choice (documented for the Phase 13 UI): a token that authenticates but
is MISSING privileges is the cap's SUCCESS path — it returns 200 with
``success=False`` and the missing privilege names in the body, NOT a
``setup_missing_privileges`` error. The error codes are reserved for hard failures
(unreachable host, rejected token, template not found). A not-found template
likewise returns 200 with ``exists=False`` per the read-only DTO contract.
"""

import logging

from fastapi import APIRouter, Depends, Header, Request
from pydantic import SecretStr, model_validator

from compute.provider import ComputeProvider
from config import settings
from db.provider import DbProvider
from lib.adminGate import MIN_ADMIN_SECRET_LENGTH, hash_admin_secret, verify_admin_secret
from lib.envelope import respond
from lib.errors import AdminAuthError, CredentialStoreError
from lib.secretBox import EnvSecretKeyProvider, SecretBox
from models.base import CamelModel

from main import get_compute, get_db, reset_compute, set_proxmox_token_override

router = APIRouter(prefix="/api/v1")

# Only non-secret context (action names, source IPs) ever reaches this logger.
logger = logging.getLogger("burrow.setup")

# Minimum length for a stored credential. Real PATs / PVE tokens are far longer; this
# rejects a too-short value at the boundary so its full plaintext can never land in a
# last4 column, the audit detail, or the status envelope (ADR-0015 hardening).
MIN_CREDENTIAL_LENGTH = 8


async def _audit(
    db: DbProvider,
    action: str,
    outcome: str,
    *,
    target: str | None = None,
    source_ip: str | None = None,
    detail: str | None = None,
) -> None:
    """Best-effort audit write: a failed audit must NEVER fail the operation it records.

    The ``audit_log`` row is the durable SOC 2 trail (CC7.2/CC7.3); if the write itself
    fails (DB locked, table unavailable), log a warning and continue rather than turning
    an authorized request into a 500. No secret value is ever passed here.
    """
    try:
        await db.writeAudit(action, outcome, target=target, source_ip=source_ip, detail=detail)
    except Exception:
        logger.warning(
            "audit write failed (best-effort); continuing", extra={"auditAction": action}
        )


async def require_admin(
    request: Request,
    x_burrow_admin: str | None = Header(default=None),
    db: DbProvider = Depends(get_db),
) -> None:
    """Gate the credential surface on the local admin secret (ADR-0015).

    Verifies the ``X-Burrow-Admin`` header against the stored argon2id hash. A missing
    hash (no secret set yet), a missing header, and a mismatch all raise the SAME
    ``AdminAuthError`` -> 401 (no oracle on which failed). REJECTIONS are audited (a
    successful gate is implied by the operation's own audit, and skipping the success
    row keeps a polled status read from flooding the trail), with the source IP and
    NEVER the presented secret. Wire as a route dependency (``Depends(require_admin)``).
    """
    source_ip = request.client.host if request.client else None
    stored = await db.getAdminSecretHash()
    ok = (
        stored is not None
        and x_burrow_admin is not None
        and verify_admin_secret(x_burrow_admin, stored)
    )
    if not ok:
        await _audit(db, "admin.verify", "failure", source_ip=source_ip)
        raise AdminAuthError("admin gate rejected")


class TestConnectionBody(CamelModel):
    """Request body for ``POST /setup/test-connection`` (SETUP-01).

    ``token_value`` is a ``SecretStr`` so Pydantic/FastAPI redacts it in a 422
    validation body and in any ``repr`` — the operator-typed token never leaks
    through an error response (SETUP-07).
    """

    host: str
    user: str
    token_name: str
    token_value: SecretStr


class VerifyTemplateBody(CamelModel):
    """Request body for ``POST /setup/verify-template`` (SETUP-02)."""

    template_vmid: int
    node: str


@router.post("/setup/test-connection")
async def test_connection(
    body: TestConnectionBody,
    compute: ComputeProvider = Depends(get_compute),
) -> dict[str, object]:
    """Validate a host/token READ-ONLY; report success + missing privileges (SETUP-01)."""
    # SETUP-07: the raw token is read ONLY here, at the compute call site, via
    # .get_secret_value(). The body is never logged; the token is never returned.
    result = await compute.testConnection(
        host=body.host,
        user=body.user,
        token_name=body.token_name,
        token_value=body.token_value.get_secret_value(),
    )
    return respond(result.model_dump(by_alias=True))


@router.post("/setup/verify-template")
async def verify_template(
    body: VerifyTemplateBody,
    compute: ComputeProvider = Depends(get_compute),
) -> dict[str, object]:
    """Verify the golden template exists and is usable, READ-ONLY (SETUP-02)."""
    result = await compute.verifyTemplate(template_vmid=body.template_vmid, node=body.node)
    return respond(result.model_dump(by_alias=True))


@router.get("/setup/state")
async def get_setup_state(db: DbProvider = Depends(get_db)) -> dict[str, object]:
    """Return the first-run gate state ``{setupCompletedAt}`` READ-ONLY (SETUP-04)."""
    return respond(await db.getSetupState())


@router.post("/setup/complete")
async def complete_setup(db: DbProvider = Depends(get_db)) -> dict[str, object]:
    """Stamp setup complete and return ``{setupCompletedAt}``; idempotent (SETUP-05).

    No request body and no token: the setter only writes a timestamp onto the
    singleton settings row, so it cannot fail on a valid singleton and re-calling
    it simply re-stamps. No new error code is needed.
    """
    return respond(await db.setSetupCompleted())


class AdminSecretBody(CamelModel):
    """Request body for ``POST /setup/admin-secret`` (ADR-0015).

    ``secret`` is a ``SecretStr`` so it is masked in any 422/``repr``. ``current_secret``
    is required to CHANGE an existing admin secret, so a LAN actor cannot silently
    take over the gate once it is set.
    """

    secret: SecretStr
    current_secret: SecretStr | None = None

    @model_validator(mode="after")
    def _min_length(self) -> "AdminSecretBody":
        if len(self.secret.get_secret_value()) < MIN_ADMIN_SECRET_LENGTH:
            # Fixed message, no secret value — the leak-free 422 handler keeps only
            # loc/msg/type, and SecretStr masks the value regardless.
            raise ValueError(f"admin secret must be at least {MIN_ADMIN_SECRET_LENGTH} characters")
        return self


@router.post("/setup/admin-secret")
async def set_admin_secret(
    body: AdminSecretBody,
    request: Request,
    db: DbProvider = Depends(get_db),
) -> dict[str, object]:
    """Set or change the credential-surface admin secret (ADR-0015).

    First-run (no secret yet) is unauthenticated by design — the setup wizard sets it
    before setup completes, under the LAN-only trust boundary. CHANGING an existing
    secret requires the current one (``currentSecret``), so the gate cannot be silently
    taken over post-setup. Only the argon2id hash is stored; the plaintext is never
    persisted, logged, or returned.
    """
    source_ip = request.client.host if request.client else None
    existing = await db.getAdminSecretHash()
    if existing is not None:
        current = body.current_secret.get_secret_value() if body.current_secret else ""
        if not verify_admin_secret(current, existing):
            await _audit(db, "admin.set", "failure", source_ip=source_ip)
            raise AdminAuthError("current admin secret mismatch")
    await db.setAdminSecret(hash_admin_secret(body.secret.get_secret_value()))
    await _audit(db, "admin.set", "success", source_ip=source_ip)
    return respond({"adminSecretSet": True})


class SaveCredentialsBody(CamelModel):
    """Request body for ``POST /setup/credentials`` (ADR-0015).

    Both fields are optional ``SecretStr`` (set one or both; masked in any 422/``repr``).
    At least one must be present — a no-op write is a 422. Values are stored encrypted
    and are NEVER returned.
    """

    proxmox_token_value: SecretStr | None = None
    git_token: SecretStr | None = None

    @model_validator(mode="after")
    def _validate(self) -> "SaveCredentialsBody":
        provided = [self.proxmox_token_value, self.git_token]
        if all(value is None for value in provided):
            raise ValueError("provide proxmoxTokenValue and/or gitToken")
        for value in provided:
            # Fixed message, no secret — the leak-free 422 handler keeps only
            # loc/msg/type and SecretStr masks the value regardless.
            if value is not None and len(value.get_secret_value()) < MIN_CREDENTIAL_LENGTH:
                raise ValueError(
                    f"a credential must be at least {MIN_CREDENTIAL_LENGTH} characters"
                )
        return self


def _secret_box() -> SecretBox:
    """Build the credential ``SecretBox``, or raise if the store key is unset (ADR-0015)."""
    key = settings.burrow_secret_key.get_secret_value()
    if not key:
        # The store cannot encrypt without a key. 503, names no secret.
        raise CredentialStoreError("the credential store is unconfigured (BURROW_SECRET_KEY unset)")
    return SecretBox(EnvSecretKeyProvider(key))


@router.post("/setup/credentials", dependencies=[Depends(require_admin)])
async def save_credentials(
    body: SaveCredentialsBody,
    request: Request,
    db: DbProvider = Depends(get_db),
    compute: ComputeProvider = Depends(get_compute),
) -> dict[str, object]:
    """Store the Proxmox token and/or GitHub PAT encrypted at rest (ADR-0015).

    Admin-gated (``require_admin``). A Proxmox token is VALIDATED read-only via
    ``testConnection`` (an ephemeral client built from the new token, ADR-0012) BEFORE
    it is persisted, so a broken token is never stored; on success the runtime override
    is set + the compute provider rebuilt, applying it WITHOUT a restart. The store is
    write-only: this returns status (set + last4), never a value. Each write is audited
    with the source IP and the last4 — never the secret.
    """
    source_ip = request.client.host if request.client else None
    box = _secret_box()

    if body.proxmox_token_value is not None:
        token = body.proxmox_token_value.get_secret_value()
        # Validate the NEW token against the configured host/user/token-name BEFORE
        # persisting. A hard failure (auth/unreachable) raises -> a fixed token-free
        # envelope, and nothing is stored. A missing-privileges result still
        # authenticated, so the token is valid to store.
        await compute.testConnection(
            host=settings.proxmox_host,
            user=settings.proxmox_user,
            token_name=settings.proxmox_token_name,
            token_value=token,
        )
        await db.setCredentials(
            {"proxmox_token_enc": box.encrypt(token), "proxmox_token_last4": token[-4:]}
        )
        # Apply without a restart: rebind the provider to the new token on next build.
        set_proxmox_token_override(token)
        reset_compute()
        await _audit(
            db,
            "credentials.update",
            "success",
            target="proxmoxToken",
            source_ip=source_ip,
            detail=f"****{token[-4:]}",
        )

    if body.git_token is not None:
        git = body.git_token.get_secret_value()
        await db.setCredentials({"git_token_enc": box.encrypt(git), "git_token_last4": git[-4:]})
        await _audit(
            db,
            "credentials.update",
            "success",
            target="gitToken",
            source_ip=source_ip,
            detail=f"****{git[-4:]}",
        )

    return respond(await db.getCredentialStatus())


@router.get("/setup/credentials", dependencies=[Depends(require_admin)])
async def get_credentials(db: DbProvider = Depends(get_db)) -> dict[str, object]:
    """Return credential status (set + last4 + updatedAt) ONLY — never a value (ADR-0015)."""
    return respond(await db.getCredentialStatus())


# Bounds for the audit-read page size: clamp (never reject) an out-of-range ``limit``.
_AUDIT_LIMIT_MIN = 1
_AUDIT_LIMIT_MAX = 500
_AUDIT_LIMIT_DEFAULT = 100


@router.get("/setup/audit", dependencies=[Depends(require_admin)])
async def get_audit(
    limit: int = _AUDIT_LIMIT_DEFAULT, db: DbProvider = Depends(get_db)
) -> dict[str, object]:
    """Return recent audit_log entries newest-first — admin-gated, READ-ONLY (CRED-05).

    The audit trail is the durable SOC 2 record (CC7.2/CC7.3). This NEVER returns a
    secret value: the rows never contain one by construction (``writeAudit`` forbids
    it, and only non-secret columns exist), so the read is safe behind the admin gate.
    ``limit`` is clamped to ``1..500`` (default ``100``).
    """
    clamped = max(_AUDIT_LIMIT_MIN, min(limit, _AUDIT_LIMIT_MAX))
    return respond({"entries": await db.listAudit(clamped)})
