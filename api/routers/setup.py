# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Setup router — ``/api/v1/setup/*`` guided-setup validation (SETUP-01/02/03).

Thin surface over the :class:`compute.provider.ComputeProvider` seam (the
``get_compute`` DI). Two endpoints validate a Proxmox host/token and the golden
template strictly READ-ONLY, returning the standard envelope:

- ``POST /setup/test-connection`` (SETUP-01) → ``ConnectionResult`` (success +
  missingPrivileges); creates zero resources.
- ``POST /setup/verify-template`` (SETUP-02) → ``TemplateResult`` (exists/usable);
  mutates nothing.

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

from fastapi import APIRouter, Depends
from pydantic import SecretStr

from compute.provider import ComputeProvider
from lib.envelope import respond
from models.base import CamelModel

from main import get_compute

router = APIRouter(prefix="/api/v1")


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
    result = await compute.verifyTemplate(
        template_vmid=body.template_vmid, node=body.node
    )
    return respond(result.model_dump(by_alias=True))
