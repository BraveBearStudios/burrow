# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Compute DTOs consumed by the ComputeProvider ABC (Plan 02).

These are the typed return/argument shapes the compute seam exposes. They are
provider-agnostic: the Proxmox impl populates them from proxmoxer responses and
the Fake impl from in-memory state, but neither leaks past these DTOs.
"""

from typing import Literal

from models.base import CamelModel


class ComputeTask(CamelModel):
    """Result of a compute task (clone/start/stop/destroy).

    The Fake provider always returns ``status="ok"``; the Proxmox impl
    populates from ``Tasks.blocking_status``.
    """

    upid: str | None
    status: Literal["ok", "failed"]
    exitstatus: str | None


class ComputeStatus(CamelModel):
    """Runtime status of a worker container."""

    status: str
    uptime: int
    mem: int
    maxmem: int
    cpu: float


class BootConfig(CamelModel):
    """Non-secret boot configuration delivered pull-at-boot (SC-4).

    Contains NO secrets: the short-lived git credential is fetched separately at
    boot, never carried in this DTO.
    """

    config_repo: str
    config_branch: str
    project_repo: str
    project_branch: str


class ConnectionResult(CamelModel):
    """Outcome of a read-only Proxmox setup connection check (SETUP-01).

    Provider-neutral: the Proxmox impl computes it from the privsep token's
    effective ``/access/permissions`` map and the Fake from in-memory state.
    Carries NO secret: the operator-typed token is validated in-memory and is
    never echoed back through this DTO (SETUP-07).

    - ``success`` is ``True`` only when every required BurrowProvisioner
      privilege is present.
    - ``missing_privileges`` (JSON ``missingPrivileges``) lists the missing
      privilege names sorted; it is empty when ``success`` is ``True``.
    """

    success: bool
    missing_privileges: list[str]


class TemplateResult(CamelModel):
    """Outcome of a read-only golden-template verification (SETUP-02).

    Provider-neutral and read-only: reports whether the template exists and is
    usable on the target node without mutating anything.

    - ``exists``: the VMID resolved to a container on the node.
    - ``usable``: it exists AND is a template (the ``template`` flag is set).
    - ``vmid`` / ``node``: echo the checked target.
    """

    exists: bool
    usable: bool
    vmid: int
    node: str
