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
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiosqlite

from models.event import WorkspaceEvent
from models.template import Template
from models.workspace import Workspace

from db.provider import DbProvider, VmidTakenError

logger = logging.getLogger("burrow.sqlite")

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"

# ADR-0013: `persistent` is create-time only in v1.3, never mutable post-create.
# Enforced at the updateWorkspace seam so the "create-time only" decision is a
# typed policy at the call site, not just prose in the ADR.
_IMMUTABLE_FIELDS = {"persistent"}

# Select the camelCase columns AS the snake_case model field names so an
# aiosqlite.Row maps directly onto Workspace via populate_by_name.
_WORKSPACE_COLUMNS = (
    "id, name, status, vmid, node, persistent, "
    "lxcIp AS lxc_ip, projectRepo AS project_repo, projectBranch AS project_branch, "
    "pluginSet AS plugin_set, createdAt AS created_at, stoppedAt AS stopped_at, "
    "destroyedAt AS destroyed_at, deletedAt AS deleted_at"
)


class SqliteProvider(DbProvider):
    """``aiosqlite``-backed :class:`DbProvider`."""

    # Default busy timeout (ms) a blocked writer waits on a held lock before it
    # gives up. Used when ``settings`` does not carry ``sqlite_busy_timeout_ms``
    # (e.g. the minimal test settings stub). See ``_connect`` for the rationale.
    _DEFAULT_BUSY_TIMEOUT_MS = 5000

    def __init__(self, settings: Any) -> None:
        self._database_path: str = settings.database_path
        self._busy_timeout_ms: int = getattr(
            settings, "sqlite_busy_timeout_ms", self._DEFAULT_BUSY_TIMEOUT_MS
        )
        self._migrated = False

    # ── connection ────────────────────────────────────────────────────────
    @asynccontextmanager
    async def _connect(self) -> AsyncIterator[aiosqlite.Connection]:
        """Yield a connection with FK enforcement, a busy timeout, and WAL on.

        Three per-connection pragmas, all required for correctness because each
        opens a fresh connection (defaults reset every time):

        - ``foreign_keys = ON``: SQLite enforces FKs only when set per connection
          (defaults OFF), so the ``events.workspaceId`` FK in ``001_init.sql`` is
          a no-op without it.
        - ``busy_timeout``: without it a writer blocked by another writer's held
          lock fails *immediately* with ``OperationalError: database is locked``
          *before* the partial-unique-index check runs — so the VMID reservation
          race (SC-3/SC-4) surfaces a raw lock error instead of the retryable
          ``VmidTakenError`` (CR-02). With a timeout the loser waits, then hits
          the real uniqueness check.
        - ``journal_mode = WAL``: lets readers run concurrently with a writer,
          shrinking the lock-contention window the busy timeout has to absorb.
        """
        async with aiosqlite.connect(self._database_path) as conn:
            await conn.execute(f"PRAGMA busy_timeout = {self._busy_timeout_ms}")
            await conn.execute("PRAGMA journal_mode = WAL")
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
                await self._apply_migration_file(conn, path)
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

    @staticmethod
    async def _apply_migration_file(conn: aiosqlite.Connection, path: Path) -> None:
        """Run a migration script, recovering from a partial-apply re-run (WR-03).

        ``executescript`` is non-atomic: it issues an implicit COMMIT before the
        script and does NOT wrap the statements in one transaction. A mid-script
        failure can therefore commit an early ``ALTER TABLE ADD COLUMN`` while the
        ledger row (written by the caller, after this returns) never lands. The next
        ``migrate()`` re-runs the file from the top and the ADD COLUMN now raises
        ``OperationalError: duplicate column name``, wedging migration permanently.

        Recovery: catch exactly that "duplicate column name" error and re-run the
        script with the already-applied ADD COLUMN statements stripped. The rest of
        the migration is authored idempotently (``CREATE TABLE IF NOT EXISTS`` /
        ``INSERT OR IGNORE``), so replaying the remainder is safe and lets the caller
        ledger the version, converging the half-applied DB onto the target schema.
        """
        script = path.read_text(encoding="utf-8")
        try:
            await conn.executescript(script)
        except aiosqlite.OperationalError as exc:
            if "duplicate column name" not in str(exc).lower():
                raise
            logger.warning(
                "migration re-run found an already-applied column; "
                "replaying the idempotent remainder",
                extra={"migration": path.name, "cause": str(exc)},
            )
            remainder = "\n".join(
                line
                for line in script.splitlines()
                if not line.lstrip().upper().startswith("ALTER TABLE")
            )
            await conn.executescript(remainder)

    # ── DbProvider contract ───────────────────────────────────────────────
    async def createWorkspace(self, data: dict[str, Any]) -> Workspace:
        await self._ensure_migrated()
        workspace_id = data.get("id") or uuid.uuid4().hex
        async with self._connect() as conn:
            try:
                await conn.execute(
                    "INSERT INTO workspaces "
                    "(id, name, status, vmid, node, persistent, "
                    "lxcIp, projectRepo, projectBranch, pluginSet) "
                    "VALUES (:id, :name, :status, :vmid, :node, :persistent, :lxcIp, "
                    ":projectRepo, :projectBranch, :pluginSet)",
                    {
                        "id": workspace_id,
                        "name": data["name"],
                        "status": data.get("status", "creating"),
                        "vmid": data.get("vmid"),
                        "node": data["node"],
                        "persistent": data.get("persistent", False),
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
            except aiosqlite.OperationalError as exc:
                # CR-02: under genuinely concurrent create sagas the losing writer
                # can be blocked by the winner's held write lock and, even with a
                # busy_timeout, ultimately fail with "database is locked" BEFORE
                # the partial-unique check evaluates. That is the same "lost the
                # race" outcome as a uniqueness collision, so it is surfaced as the
                # retryable VmidTakenError (the seam-safe signal the service's
                # bounded retry loop re-scans on) rather than escaping as a raw
                # driver error. Any other OperationalError propagates unchanged.
                if "database is locked" in str(exc).lower():
                    # WR-02: this branch launders ANY "database is locked" into the
                    # retryable lost-race signal, so an unrelated lock/IO problem
                    # would otherwise surface as a misleading "pool exhausted"
                    # (NoFreeVmidError) after the service exhausts its retries. Log
                    # the raw cause at WARNING so a real lock problem stays visible.
                    logger.warning(
                        "create INSERT hit a lock; treating as lost-race",
                        extra={"workspace_id": workspace_id, "cause": str(exc)},
                    )
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
            if field_name in _IMMUTABLE_FIELDS:
                # Deliberate policy, not an accidental column_map omission: surface
                # a distinct, self-documenting error rather than the opaque
                # "unknown workspace field" KeyError below (WR-01 / ADR-0013).
                raise ValueError(f"{field_name} is immutable after create (ADR-0013)")
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

    async def listTemplates(self) -> list[Template]:
        await self._ensure_migrated()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT id, name, proxmoxTid AS proxmox_tid, "
                "pluginManifest AS plugin_manifest, createdAt AS created_at "
                "FROM templates ORDER BY name"
            )
            rows = await cursor.fetchall()
            await cursor.close()
        # Template's before-validator decodes the TEXT JSON `pluginManifest` column.
        return [Template.model_validate(dict(row)) for row in rows]

    async def healthcheck(self) -> bool:
        async with self._connect() as conn:
            cursor = await conn.execute("SELECT 1")
            row = await cursor.fetchone()
            await cursor.close()
        return row is not None and row[0] == 1

    async def getSetupState(self) -> dict[str, Any]:
        # ADR-0011: read the singleton settings row (id=1; seeded NULL by the 003
        # migration). READ-ONLY this phase — no INSERT/UPDATE; the setter is
        # deferred to Phase 13. Returns the setup-state shape the wizard consumes.
        await self._ensure_migrated()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT setupCompletedAt AS setup_completed_at FROM settings WHERE id = 1"
            )
            row = await cursor.fetchone()
            await cursor.close()
        return {"setupCompletedAt": row["setup_completed_at"] if row is not None else None}
