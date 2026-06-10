# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Proxmox compute provider — Phase-1 skeleton.

This file establishes the seam shape only. Every method raises
``NotImplementedError`` — the real ``proxmoxer`` bodies (UPID waits, ``--full``
clone, static-IP ``net0`` set, capacity query) land in Phase 1 and are validated
only against a real Proxmox node in the dev homelab.

``proxmoxer`` is imported at module top to prove the dependency resolves and to
keep the Proxmox driver symbols confined to this file (seam-leakage discipline).

TLS posture: where a client is ever constructed, it MUST validate the node CA via
``settings.proxmox_ca_cert_path`` — never disable verification. The cert path is
read in ``__init__`` so the contract is explicit even before any call is wired.
"""

from typing import Any

import proxmoxer  # noqa: F401  # dependency-resolution + seam confinement

from models.compute import BootConfig, ComputeStatus, ComputeTask

from compute.provider import ComputeProvider


class ProxmoxComputeProvider(ComputeProvider):
    """Proxmox-backed :class:`ComputeProvider` (skeleton — bodies are Phase 1)."""

    def __init__(self, settings: Any) -> None:
        self._settings = settings
        # CA-pinned TLS: validate the node cert at this path, never disable it.
        self._ca_cert_path: str = settings.proxmox_ca_cert_path

    async def getNextVmid(self, pool_start: int, pool_end: int, used: set[int]) -> int:
        raise NotImplementedError("ProxmoxComputeProvider.getNextVmid — Phase 1")

    async def usedVmids(self) -> set[int]:
        raise NotImplementedError("ProxmoxComputeProvider.usedVmids — Phase 1")

    async def cloneCt(
        self,
        template_vmid: int,
        new_vmid: int,
        name: str,
        node: str,
        full: bool = True,
    ) -> ComputeTask:
        raise NotImplementedError("ProxmoxComputeProvider.cloneCt — Phase 1")

    async def injectBootConfig(self, vmid: int, config: BootConfig) -> None:
        raise NotImplementedError("ProxmoxComputeProvider.injectBootConfig — Phase 1")

    async def startCt(self, node: str, vmid: int) -> ComputeTask:
        raise NotImplementedError("ProxmoxComputeProvider.startCt — Phase 1")

    async def stopCt(self, node: str, vmid: int) -> ComputeTask:
        raise NotImplementedError("ProxmoxComputeProvider.stopCt — Phase 1")

    async def destroyCt(self, node: str, vmid: int) -> ComputeTask:
        raise NotImplementedError("ProxmoxComputeProvider.destroyCt — Phase 1")

    async def getStatus(self, node: str, vmid: int) -> ComputeStatus:
        raise NotImplementedError("ProxmoxComputeProvider.getStatus — Phase 1")

    async def getIp(self, node: str, vmid: int) -> str | None:
        raise NotImplementedError("ProxmoxComputeProvider.getIp — Phase 1")

    async def getNodeMemory(self, node: str) -> float:
        raise NotImplementedError("ProxmoxComputeProvider.getNodeMemory — Phase 1")

    async def waitTask(self, node: str, upid: str, timeout: float) -> ComputeTask:
        raise NotImplementedError("ProxmoxComputeProvider.waitTask — Phase 1")

    async def healthcheck(self) -> bool:
        raise NotImplementedError("ProxmoxComputeProvider.healthcheck — Phase 1")
