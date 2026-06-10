# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""SQLite persistence provider (PLAT-06).

``SqliteProvider`` implements :class:`DbProvider` over ``aiosqlite`` against the
``001_init.sql`` schema. It is the v1 self-host store.

Seam discipline: ``aiosqlite`` and raw SQL appear ONLY in this file (and the
``migrations/`` dir). Rows are mapped into :class:`Workspace` / :class:`WorkspaceEvent`
DTOs before they cross the seam — no ``aiosqlite.Row`` leaks up.

Column mapping: the SQLite schema (tech-spec §7.1) uses camelCase column names
(``lxcIp``, ``projectRepo`` …); the Pydantic models use snake_case fields. This
file is the single place that bridges the two, by selecting columns ``AS`` their
snake_case field names so a row maps straight onto the model.
"""

import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiosqlite

from models.event import WorkspaceEvent
from models.workspace import Workspace

from db.provider import DbProvider, VmidTakenError

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"

# Select the camelCase columns AS the snake_case model field names so an
# aiosqlite.Row maps directly onto Workspace via populate_by_name.
_WORKSPACE_COLUMNS = (
    "id, name, status, vmid, node, "
    "lxcIp AS lxc_ip, projectRepo AS project_repo, projectBranch AS project_branch, "
    "pluginSet AS plugin_set, createdAt AS created_at, stoppedAt AS stopped_at, "
    "destroyedAt AS destroyed_at, deletedAt AS deleted_at"
)


class SqliteProvider(DbProvider):
    """``aiosqlite``-backed :class:`DbProvider`."""

    def __init__(self, settings: Any) -> None:
        self._database_path: str = settings.database_path
        self._migrated = False

    # ── connection ────────────────────────────────────────────────────────
    @asynccontextmanager
    async def _connect(self) -> AsyncIterator[aiosqlite.Connection]:
        """Yield a connection with foreign-key enforcement turned ON.

        SQLite enforces foreign keys only when ``PRAGMA foreign_keys = ON`` is
        set *per connection* (it defaults OFF), so the ``events.workspaceId``
        FK in ``001_init.sql`` is a no-op unless every connection issues it.
        Routing all methods through this helper closes that gap once, here.
        """
        async with aiosqlite.connect(self._database_path) as conn:
            await conn.execute("PRAGMA foreign_keys = ON")
            yield conn

    # ── migration ─────────────────────────────────────────────────────────
    async def migrate(self) -> None:
        """Apply every ``migrations/*.sql`` in filename order, exactly once.

        A ``schema_migrations`` ledger (version PRIMARY KEY) records which
        migrations have run, so this is idempotent and re-runnable: only files
        whose stem is absent from the ledger are applied, in sorted order. This
        replaces the Phase-0 "skip if the workspaces table exists" check, which
        wrongly skipped ``002`` on a DB that already had ``001`` (Pitfall 6) —
        the partial unique index would never get created.
        """
        files = sorted(_MIGRATIONS_DIR.glob("*.sql"), key=lambda p: p.name)
        async with self._connect() as conn:
            await conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version TEXT PRIMARY KEY, appliedAt TEXT NOT NULL "
                "DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')))"
            )
            cursor = await conn.execute("SELECT version FROM schema_migrations")
            applied = {row[0] for row in await cursor.fetchall()}
            await cursor.close()
            for path in files:
                version = path.stem
                if version in applied:
                    continue
                await conn.executescript(path.read_text(encoding="utf-8"))
                await conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
            await conn.commit()
        self._migrated = True

    async def _ensure_migrated(self) -> None:
        if not self._migrated:
            await self.migrate()

    @staticmethod
    def _row_to_workspace(row: aiosqlite.Row) -> Workspace:
        """Map a workspaces row (snake_case-aliased) onto the Workspace DTO."""
        return Workspace.model_validate(dict(row))

    # ── DbProvider contract ───────────────────────────────────────────────
    async def createWorkspace(self, data: dict[str, Any]) -> Workspace:
        await self._ensure_migrated()
        workspace_id = data.get("id") or uuid.uuid4().hex
        async with self._connect() as conn:
            try:
                await conn.execute(
                    "INSERT INTO workspaces "
                    "(id, name, status, vmid, node, lxcIp, projectRepo, projectBranch, pluginSet) "
                    "VALUES (:id, :name, :status, :vmid, :node, :lxcIp, "
                    ":projectRepo, :projectBranch, :pluginSet)",
                    {
                        "id": workspace_id,
                        "name": data["name"],
                        "status": data.get("status", "creating"),
                        "vmid": data.get("vmid"),
                        "node": data["node"],
                        "lxcIp": data.get("lxc_ip"),
                        "projectRepo": data["project_repo"],
                        "projectBranch": data.get("project_branch", "main"),
                        "pluginSet": data.get("plugin_set", "default"),
                    },
                )
            except aiosqlite.IntegrityError as exc:
                # The 002 partial unique index is the reservation arbiter: a
                # duplicate-active-vmid INSERT is "lost the race" (SC-3), surfaced
                # as the typed VmidTakenError so the service can retry. SQLite
                # reports the violated UNIQUE as the column ("UNIQUE constraint
                # failed: workspaces.vmid"), not the index name — and the partial
                # index is the ONLY uniqueness on workspaces.vmid (001 declares
                # none), so that column phrase is the reliable discriminator. Any
                # other IntegrityError (e.g. the events FK) propagates unchanged.
                if "workspaces.vmid" in str(exc):
                    raise VmidTakenError(str(exc)) from exc
                raise
            await conn.commit()
        created = await self.getWorkspace(workspace_id)
        if created is None:  # pragma: no cover - insert just succeeded
            raise RuntimeError(f"workspace {workspace_id} vanished after insert")
        return created

    async def getWorkspace(self, workspaceId: str) -> Workspace | None:
        await self._ensure_migrated()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                f"SELECT {_WORKSPACE_COLUMNS} FROM workspaces WHERE id = ? AND deletedAt IS NULL",
                (workspaceId,),
            )
            row = await cursor.fetchone()
            await cursor.close()
        return self._row_to_workspace(row) if row is not None else None

    async def listWorkspaces(self, status: str | None = None) -> list[Workspace]:
        await self._ensure_migrated()
        query = f"SELECT {_WORKSPACE_COLUMNS} FROM workspaces WHERE deletedAt IS NULL"
        params: tuple[str, ...] = ()
        if status is not None:
            query += " AND status = ?"
            params = (status,)
        query += " ORDER BY createdAt"
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            await cursor.close()
        return [self._row_to_workspace(row) for row in rows]

    async def updateWorkspace(self, workspaceId: str, updates: dict[str, Any]) -> Workspace:
        await self._ensure_migrated()
        # Map snake_case field names to the camelCase columns we allow updating.
        column_map = {
            "name": "name",
            "status": "status",
            "vmid": "vmid",
            "node": "node",
            "lxc_ip": "lxcIp",
            "project_repo": "projectRepo",
            "project_branch": "projectBranch",
            "plugin_set": "pluginSet",
            "stopped_at": "stoppedAt",
            "destroyed_at": "destroyedAt",
        }
        assignments: list[str] = []
        params: dict[str, Any] = {"id": workspaceId}
        for field_name, value in updates.items():
            column = column_map.get(field_name)
            if column is None:
                raise KeyError(f"unknown workspace field: {field_name}")
            assignments.append(f"{column} = :{field_name}")
            params[field_name] = value
        if assignments:
            async with self._connect() as conn:
                await conn.execute(
                    f"UPDATE workspaces SET {', '.join(assignments)} WHERE id = :id",
                    params,
                )
                await conn.commit()
        updated = await self.getWorkspace(workspaceId)
        if updated is None:
            raise KeyError(f"workspace {workspaceId} not found")
        return updated

    async def softDeleteWorkspace(self, workspaceId: str) -> None:
        await self._ensure_migrated()
        async with self._connect() as conn:
            await conn.execute(
                "UPDATE workspaces "
                "SET deletedAt = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') "
                "WHERE id = ? AND deletedAt IS NULL",
                (workspaceId,),
            )
            await conn.commit()

    async def logEvent(self, workspaceId: str, eventType: str, data: dict[str, Any]) -> None:
        await self._ensure_migrated()
        async with self._connect() as conn:
            await conn.execute(
                "INSERT INTO events (id, workspaceId, type, data) VALUES (?, ?, ?, ?)",
                (uuid.uuid4().hex, workspaceId, eventType, json.dumps(data)),
            )
            await conn.commit()

    async def getEvents(self, workspaceId: str) -> list[WorkspaceEvent]:
        await self._ensure_migrated()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT id, workspaceId AS workspace_id, type, data, "
                "createdAt AS created_at FROM events WHERE workspaceId = ? "
                # rowid is a stable insertion-order tiebreaker so two events
                # logged in the same millisecond still come back oldest-first
                # (the WS-11 ordering guarantee), not in arbitrary order.
                "ORDER BY createdAt, rowid",
                (workspaceId,),
            )
            rows = await cursor.fetchall()
            await cursor.close()
        # WorkspaceEvent's before-validator decodes the TEXT JSON `data` column.
        return [WorkspaceEvent.model_validate(dict(row)) for row in rows]

    async def getByVmid(self, vmid: int) -> Workspace | None:
        await self._ensure_migrated()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                f"SELECT {_WORKSPACE_COLUMNS} FROM workspaces WHERE vmid = ? AND deletedAt IS NULL",
                (vmid,),
            )
            row = await cursor.fetchone()
            await cursor.close()
        return self._row_to_workspace(row) if row is not None else None

    async def healthcheck(self) -> bool:
        async with self._connect() as conn:
            cursor = await conn.execute("SELECT 1")
            row = await cursor.fetchone()
            await cursor.close()
        return row is not None and row[0] == 1
