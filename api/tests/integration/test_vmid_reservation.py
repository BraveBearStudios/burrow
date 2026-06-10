# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""WS-10 integration: race-safe VMID reservation over real SQLite.

Proves the ``002`` partial unique index is the reservation arbiter (SC-3/SC-4):

- the index ``idx_workspaces_vmid_active`` exists after ``migrate()`` (guards the
  Pitfall-6 landmine where the Phase-0 ``migrate()`` applied only ``001``);
- a duplicate *active* vmid INSERT raises the typed ``VmidTakenError`` (not a bare
  IntegrityError) — the "lost the race" signal the saga retries on;
- destroy-then-recreate reuses the vmid (the partial ``WHERE deletedAt IS NULL``
  predicate excludes the tombstone — guards a plain-UNIQUE regression, Pitfall 9);
- two distinct active vmids coexist;
- ``getByVmid`` resolves the active owner and returns ``None`` once soft-deleted;
  ``getEvents`` returns the log oldest-first.

Real Proxmox is not involved — this is the CI proof; the homelab smoke covers the
real clone/boot path. Integration tests are exempt from the seam guard, so the
index-presence check opens its own ``aiosqlite`` connection.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import aiosqlite
import pytest

from db.provider import VmidTakenError
from db.sqliteProvider import SqliteProvider


def _ws_data(name: str, vmid: int | None, status: str = "creating") -> dict[str, object]:
    """A valid ``createWorkspace`` payload differing only by name/vmid/status."""
    return {
        "name": name,
        "status": status,
        "vmid": vmid,
        "node": "pve1",
        "project_repo": f"git@example.com:acme/{name}.git",
        "project_branch": "main",
        "plugin_set": "default",
    }


async def test_partial_unique_index_exists_after_migrate(sqlite_db: SqliteProvider) -> None:
    """The 002 index must exist post-migration (guards Pitfall 6: migrate ran only 001)."""
    async with aiosqlite.connect(sqlite_db._database_path) as conn:
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'index' AND name = 'idx_workspaces_vmid_active'"
        )
        row = await cursor.fetchone()
        await cursor.close()
    assert row is not None, "002 partial unique index missing — migrate() did not apply 002"


async def test_duplicate_active_vmid_raises_vmid_taken(sqlite_db: SqliteProvider) -> None:
    """Two active rows can never share a vmid; the second INSERT raises VmidTakenError."""
    first = await sqlite_db.createWorkspace(_ws_data("alpha", 205))
    assert first.vmid == 205

    with pytest.raises(VmidTakenError):
        await sqlite_db.createWorkspace(_ws_data("beta", 205))


async def test_destroy_then_recreate_reuses_vmid(sqlite_db: SqliteProvider) -> None:
    """A soft-deleted vmid is reusable — the partial index excludes the tombstone."""
    original = await sqlite_db.createWorkspace(_ws_data("gamma", 206))
    await sqlite_db.softDeleteWorkspace(original.id)

    # Must NOT raise: the tombstone is outside `WHERE deletedAt IS NULL`.
    recreated = await sqlite_db.createWorkspace(_ws_data("gamma-2", 206))
    assert recreated.vmid == 206
    assert recreated.id != original.id


async def test_distinct_active_vmids_coexist(sqlite_db: SqliteProvider) -> None:
    """Different active vmids do not collide."""
    a = await sqlite_db.createWorkspace(_ws_data("d1", 205))
    b = await sqlite_db.createWorkspace(_ws_data("d2", 206))
    assert {a.vmid, b.vmid} == {205, 206}


async def test_get_by_vmid_resolves_active_and_excludes_soft_deleted(
    sqlite_db: SqliteProvider,
) -> None:
    """getByVmid returns the active owner, then None after soft-delete."""
    ws = await sqlite_db.createWorkspace(_ws_data("lookup", 205))

    found = await sqlite_db.getByVmid(205)
    assert found is not None
    assert found.id == ws.id

    await sqlite_db.softDeleteWorkspace(ws.id)
    assert await sqlite_db.getByVmid(205) is None


async def test_get_events_returns_log_oldest_first(sqlite_db: SqliteProvider) -> None:
    """getEvents returns the workspace's events oldest-first with JSON data decoded."""
    ws = await sqlite_db.createWorkspace(_ws_data("evt", 205))
    await sqlite_db.logEvent(ws.id, "workspace.created", {"step": 1})
    await sqlite_db.logEvent(ws.id, "workspace.started", {"step": 2})

    events = await sqlite_db.getEvents(ws.id)
    assert [e.type for e in events] == ["workspace.created", "workspace.started"]
    assert events[0].data == {"step": 1}
    assert events[1].data == {"step": 2}


async def test_connect_sets_wal_and_busy_timeout_pragmas(sqlite_db: SqliteProvider) -> None:
    """CR-02: every connection runs WAL journal mode + a non-zero busy timeout.

    Without these a concurrent writer fails immediately with "database is locked"
    before the partial-unique reservation check can fire, so the loser never
    surfaces the retryable VmidTakenError. WAL persists at the DB level; the busy
    timeout is per-connection.
    """
    async with sqlite_db._connect() as conn:
        journal_cursor = await conn.execute("PRAGMA journal_mode")
        journal_row = await journal_cursor.fetchone()
        await journal_cursor.close()

        busy_cursor = await conn.execute("PRAGMA busy_timeout")
        busy_row = await busy_cursor.fetchone()
        await busy_cursor.close()

    assert journal_row is not None and str(journal_row[0]).lower() == "wal"
    assert busy_row is not None and int(busy_row[0]) == sqlite_db._busy_timeout_ms
    assert sqlite_db._busy_timeout_ms > 0


class _LockOnceProvider(SqliteProvider):
    """SqliteProvider that injects a one-shot "database is locked" on INSERT.

    CR-02 substrate: simulates the concurrent-writer loss where the blocked
    writer ultimately fails with ``OperationalError: database is locked`` rather
    than reaching the uniqueness check. The lock is injected at the connection's
    ``execute`` (where a real held-lock would surface) so the provider's
    OperationalError->VmidTakenError mapping is exercised; the service's bounded
    retry loop then re-scans instead of crashing the saga with an uncaught 500.
    """

    def __init__(self, settings: Any) -> None:
        super().__init__(settings)
        self._lock_inserts_remaining = 1

    @asynccontextmanager
    async def _connect(self) -> AsyncIterator[aiosqlite.Connection]:
        async with super()._connect() as conn:
            original_execute = conn.execute

            async def _execute(sql: str, *args: Any, **kwargs: Any) -> Any:
                if sql.startswith("INSERT INTO workspaces") and self._lock_inserts_remaining > 0:
                    self._lock_inserts_remaining -= 1
                    raise aiosqlite.OperationalError("database is locked")
                return await original_execute(sql, *args, **kwargs)

            conn.execute = _execute  # type: ignore[method-assign]
            yield conn


async def test_locked_insert_maps_to_retryable_vmid_taken(tmp_path: Any) -> None:
    """CR-02: a "database is locked" OperationalError surfaces as VmidTakenError."""
    from dataclasses import dataclass

    @dataclass
    class _Settings:
        database_path: str

    db = _LockOnceProvider(_Settings(database_path=str(tmp_path / "lock.db")))
    await db.migrate()

    # The injected lock turns the first INSERT into a retryable loss, not a crash.
    with pytest.raises(VmidTakenError):
        await db.createWorkspace(_ws_data("locked", 205))
