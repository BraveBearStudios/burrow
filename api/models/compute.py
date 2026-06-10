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
