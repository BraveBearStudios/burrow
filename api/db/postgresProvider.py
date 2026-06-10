# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Postgres persistence provider — hosted-path stub (ADR-0001).

This file reserves the hosted-path seam behind :class:`DbProvider`. Every method
raises ``NotImplementedError``: the multi-tenant Postgres impl (RLS, ``user_id``
FKs, an async Postgres driver) is an *additive* hosted path, not part of the v1
self-host build. No driver is imported here so the stub stays inert and the v1
image carries no Postgres dependency.
"""

from typing import Any

from models.event import WorkspaceEvent
from models.workspace import Workspace

from db.provider import DbProvider


class PostgresProvider(DbProvider):
    """Postgres-backed :class:`DbProvider` (hosted-path stub — bodies are hosted-path)."""

    def __init__(self, settings: Any) -> None:
        self._settings = settings

    async def createWorkspace(self, data: dict[str, Any]) -> Workspace:
        raise NotImplementedError("PostgresProvider.createWorkspace — hosted path")

    async def getWorkspace(self, workspaceId: str) -> Workspace | None:
        raise NotImplementedError("PostgresProvider.getWorkspace — hosted path")

    async def listWorkspaces(self, status: str | None = None) -> list[Workspace]:
        raise NotImplementedError("PostgresProvider.listWorkspaces — hosted path")

    async def updateWorkspace(self, workspaceId: str, updates: dict[str, Any]) -> Workspace:
        raise NotImplementedError("PostgresProvider.updateWorkspace — hosted path")

    async def softDeleteWorkspace(self, workspaceId: str) -> None:
        raise NotImplementedError("PostgresProvider.softDeleteWorkspace — hosted path")

    async def logEvent(self, workspaceId: str, eventType: str, data: dict[str, Any]) -> None:
        raise NotImplementedError("PostgresProvider.logEvent — hosted path")

    async def getEvents(self, workspaceId: str) -> list[WorkspaceEvent]:
        raise NotImplementedError("PostgresProvider.getEvents — hosted path")

    async def getByVmid(self, vmid: int) -> Workspace | None:
        raise NotImplementedError("PostgresProvider.getByVmid — hosted path")

    async def healthcheck(self) -> bool:
        raise NotImplementedError("PostgresProvider.healthcheck — hosted path")
