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

from models.event import WorkspaceEvent
from models.template import Template
from models.workspace import Workspace


class VmidTakenError(Exception):
    """Raised when a workspace INSERT collides on the active-vmid unique index.

    The DB-seam analogue of "lost the VMID race": the ``002`` partial unique
    index (``WHERE deletedAt IS NULL``) is the cross-process reservation arbiter
    (SC-3/SC-4), so a duplicate-active-vmid INSERT surfaces here. Declared on the
    ABC module so the service can catch it ("collision → retry the scan") without
    importing the ``aiosqlite`` driver — preserving the seam.
    """


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
    async def getEvents(self, workspaceId: str) -> list[WorkspaceEvent]:
        """Return a workspace's event log oldest-first (WS-11)."""
        ...

    @abstractmethod
    async def getByVmid(self, vmid: int) -> Workspace | None:
        """Return the active workspace owning ``vmid``, or ``None``.

        Excludes soft-deleted rows so a recycled vmid resolves to the live owner
        (feeds the bootconfig router + saga compensation lookups).
        """
        ...

    @abstractmethod
    async def listTemplates(self) -> list[Template]:
        """Return the seeded golden templates (feeds ``GET /api/v1/templates``)."""
        ...

    @abstractmethod
    async def healthcheck(self) -> bool:
        """Return ``True`` when the store is reachable (cheap ``SELECT 1``, PLAT-03)."""
        ...

    @abstractmethod
    async def getSetupState(self) -> dict[str, Any]:
        """Return the singleton setup-state row (``id=1``), READ-ONLY this phase.

        Reads ``settings.setupCompletedAt`` (``003`` migration; seeded ``NULL``)
        as ``{"setupCompletedAt": <iso str | None>}``. The setter
        (``setSetupCompleted``) is DEFERRED to Phase 13 — Phase 12 only reads, it
        mutates nothing (ADR-0011).
        """
        ...
