# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Internal router — pull-at-boot bootconfig endpoint (WORK-03, ADR-0002).

``GET /api/v1/internal/bootconfig/{vmid}`` is the one non-CRUD surface of the
control plane and its single real ASVS L1 threat surface. A worker LXC, knowing
its own VMID from its hostname / static IP (ADR-0004), fetches its **non-secret**
boot identifiers (config + project repo/branch) plus a **short-lived, repo-scoped
git credential** minted per-fetch and discarded (ADR-0002). ``pct exec`` /
``pct push`` are absent from the Proxmox HTTPS API, so config is pulled, not
pushed (ADR-0002).

Threat model (RESEARCH Pattern 6; the plan's ``threat_model``):

- **Enumeration (T-01-17):** ``vmid`` is an ``int`` path param (FastAPI rejects
  non-int, ASVS V5); it must fall in ``[worker_pool_start, worker_pool_end]`` or
  the request 404s WITHOUT echoing the probed value.
- **Secret hygiene (T-01-18, block_on=high):** the minted credential is returned
  ONCE in the response body and is NEVER passed as a log ``extra`` or written to
  event ``data``. The log line carries only ``{vmid, repo}``.
- **Spoofing (T-01-19):** optional source-IP defense-in-depth compares the caller
  IP to the workspace's VMID-derived static IP, gated by
  ``settings.bootconfig_source_ip_check``. This is **defense-in-depth, NOT
  authentication** — v1 is LAN-only no-auth by design; the check is off by default.
- **Over-scoped credential (T-01-20):** issuance is the pluggable
  ``WorkspaceService.mint_repo_credential`` seam (short-lived, single-repo-scoped,
  no hard-coded PAT).

This router is thin: it validates, looks up by vmid, mints the credential, and
wraps the non-secret payload in the standard envelope. No orchestration, no
provider impl, and no driver symbol live here (seam discipline).
"""

import logging

from fastapi import APIRouter, Depends, Request

from config import settings
from lib.envelope import respond
from lib.errors import IllegalVmidError
from services.workspaceService import WorkspaceService

from main import get_service

router = APIRouter(prefix="/api/v1")

# Module logger: only whitelisted, non-secret extras ever reach it (lib.logging
# drops anything outside its allow-list), so the credential cannot leak here.
logger = logging.getLogger("burrow.bootconfig")


def _source_ip_ok(request: Request, expected_ip: str | None) -> bool:
    """Return True when the caller IP matches the workspace's static IP (T-01-19).

    Defense-in-depth ONLY — NOT authentication (v1 is LAN-only no-auth). Compares
    ``request.client.host`` to the VMID-derived static IP the saga resolved onto
    the workspace (``lxc_ip``, ADR-0004). When the workspace has no resolved IP yet
    there is nothing to bind against, so the check passes (it never blocks a
    legitimate boot before the IP is known).
    """
    if expected_ip is None:
        return True
    client = request.client
    return client is not None and client.host == expected_ip


@router.get("/internal/bootconfig/{vmid}")
async def get_bootconfig(
    vmid: int,
    request: Request,
    service: WorkspaceService = Depends(get_service),
) -> dict[str, object]:
    """Serve a worker's non-secret boot config + a short-lived git credential.

    Pull-at-boot (ADR-0002): rejects an out-of-pool ``vmid`` with an
    enumeration-resistant 404, looks up the active workspace, optionally binds the
    source IP (defense-in-depth), mints a per-fetch repo-scoped credential, and
    returns the non-secret payload. The credential is NEVER logged or written to an
    event (T-01-18, block_on=high).
    """
    # (1) vmid-in-pool gate (T-01-17): out-of-pool → 404, no echo of the probe.
    if not (settings.worker_pool_start <= vmid <= settings.worker_pool_end):
        raise IllegalVmidError(vmid)

    # (2) look up the active workspace; no live owner → 404 (same wire shape).
    ws = await service.get_by_vmid(vmid)

    # (3) source-IP defense-in-depth (T-01-19), gated + explicitly NOT auth.
    if settings.bootconfig_source_ip_check and not _source_ip_ok(request, ws.lxc_ip):
        # Mismatch presents as the generic not-found (no enumeration aid).
        raise IllegalVmidError(vmid)

    # (4) mint the short-lived, repo-scoped credential per fetch (pluggable seam).
    git_credential = await service.mint_repo_credential(ws.project_repo)

    # (5) log ONLY non-secret fields — the credential never reaches a log line.
    logger.info("bootconfig.issued", extra={"vmid": vmid, "repo": ws.project_repo})

    # (6) non-secret payload + the ephemeral credential, camelCase keys.
    payload = {
        "configRepo": settings.config_repo,
        "configBranch": settings.config_branch,
        "projectRepo": ws.project_repo,
        "projectBranch": ws.project_branch,
        "gitCredential": git_credential,
    }
    return respond(payload)
