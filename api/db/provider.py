# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Persistence provider seam (PLAT-06).

``DbProvider`` is the abstract contract every persistence backend implements
(tech-spec §6.3 + a ``healthcheck`` for ``/health`` forward-compat). Every method
is ``async`` and returns a Pydantic DTO from :mod:`models` (or ``None``) — no
driver type or raw row ever leaks past this interface.

Implementations:

- :class:`db.sqliteProvider.SqliteProvider` — the SQLite-backed v1 self-host store
  over ``001_init.sql``.
- :class:`db.postgresProvider.PostgresProvider` — hosted-path stub.

Driver symbols stay confined to the concrete impl files (seam-leakage
discipline); this ABC names none of them.
"""

from abc import ABC, abstractmethod
from typing import Any

from models.workspace import Workspace


class DbProvider(ABC):
    """Abstract persistence backend (SQLite or Postgres).

    Cannot be instantiated directly. The concrete impl is chosen once in the app
    factory from ``settings`` (``BURROW_DB=sqlite``); services depend on this ABC,
    never on an impl.
    """

    @abstractmethod
    async def createWorkspace(self, data: dict[str, Any]) -> Workspace:
        """Insert a workspace row and return the created :class:`Workspace`."""
        ...

    @abstractmethod
    async def getWorkspace(self, workspaceId: str) -> Workspace | None:
        """Return the workspace by id, or ``None``; excludes soft-deleted rows."""
        ...

    @abstractmethod
    async def listWorkspaces(self, status: str | None = None) -> list[Workspace]:
        """Return workspaces, optionally filtered by status; excludes soft-deleted."""
        ...

    @abstractmethod
    async def updateWorkspace(self, workspaceId: str, updates: dict[str, Any]) -> Workspace:
        """Apply ``updates`` to a workspace and return the updated row."""
        ...

    @abstractmethod
    async def softDeleteWorkspace(self, workspaceId: str) -> None:
        """Soft-delete a workspace (set ``deletedAt``); the row is retained for audit."""
        ...

    @abstractmethod
    async def logEvent(self, workspaceId: str, eventType: str, data: dict[str, Any]) -> None:
        """Append an event row for a workspace."""
        ...

    @abstractmethod
    async def healthcheck(self) -> bool:
        """Return ``True`` when the store is reachable (cheap ``SELECT 1``, PLAT-03)."""
        ...
