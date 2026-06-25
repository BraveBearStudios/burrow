# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Migration ledger contract for the 003 persistence + settings migration (WSX-02).

Locks the 003 migration against regression over a REAL ``SqliteProvider`` on a
``tmp_path`` DB:

- the ``persistent`` column lands with a ``DEFAULT 0`` backfill — a v1.2-shaped row
  inserted BEFORE 003 reads back ``persistent is False`` (ADR-0013);
- the ``settings`` singleton is seeded ``id=1, setupCompletedAt IS NULL`` (ADR-0011);
- the ``CHECK (id = 1)`` singleton invariant holds — a second insert collides;
- a fresh DB and a migrated v1.2-shaped DB converge on the same schema.
"""

from dataclasses import dataclass
from pathlib import Path

import aiosqlite
import pytest

from db.sqliteProvider import _MIGRATIONS_DIR, SqliteProvider


@dataclass
class _DbSettings:
    """Minimal settings stand-in: ``SqliteProvider`` only reads ``database_path``."""

    database_path: str


def _provider(tmp_path: Path, name: str) -> SqliteProvider:
    return SqliteProvider(_DbSettings(database_path=str(tmp_path / name)))


async def _apply_pre_003(database_path: str) -> None:
    """Build a "v1.2-shaped" DB: apply ONLY 001 + 002, recording them in the ledger.

    This stands in for an existing v1.2 deployment that predates 003 — used to
    prove the ``DEFAULT 0`` backfill on a row that exists before the column. The
    ledger rows for 001/002 are recorded exactly as a real v1.2 ``migrate()``
    would leave them, so a later ``migrate()`` applies ONLY the unseen 003.
    """
    async with aiosqlite.connect(database_path) as conn:
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version TEXT PRIMARY KEY, appliedAt TEXT NOT NULL "
            "DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')))"
        )
        for stem in ("001_init", "002_vmid_unique"):
            sql = (_MIGRATIONS_DIR / f"{stem}.sql").read_text(encoding="utf-8")
            await conn.executescript(sql)
            await conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (stem,))
        await conn.commit()


def _column_names(rows: list[aiosqlite.Row]) -> set[str]:
    """Column-name set from a ``PRAGMA table_info(...)`` result."""
    return {row["name"] for row in rows}


async def _table_info(database_path: str, table: str) -> list[aiosqlite.Row]:
    async with aiosqlite.connect(database_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(f"PRAGMA table_info({table})")
        rows = await cursor.fetchall()
        await cursor.close()
    return list(rows)


async def test_persistent_backfills_zero_on_preexisting_row(tmp_path: Path) -> None:
    """A v1.2 row inserted before 003 reads back ``persistent is False`` (DEFAULT 0)."""
    db_path = str(tmp_path / "v12.db")
    await _apply_pre_003(db_path)
    # Insert a row WITHOUT a persistent column (it does not exist yet).
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            "INSERT INTO workspaces (id, name, status, node, projectRepo) "
            "VALUES ('legacy', 'pre-003', 'stopped', 'pve1', 'git@example.com:acme/x.git')"
        )
        await conn.commit()

    # Now migrate() applies 003 (the ledger only sees 003 as unapplied).
    provider = SqliteProvider(_DbSettings(database_path=db_path))
    await provider.migrate()

    row = await provider.getWorkspace("legacy")
    assert row is not None
    assert row.persistent is False  # DEFAULT 0 backfilled the pre-existing row


async def test_settings_singleton_seeded(tmp_path: Path) -> None:
    """003 seeds exactly one settings row: ``id=1, setupCompletedAt IS NULL``."""
    provider = _provider(tmp_path, "fresh.db")
    await provider.migrate()
    async with aiosqlite.connect(provider._database_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("SELECT id, setupCompletedAt FROM settings")
        rows = list(await cursor.fetchall())
        await cursor.close()
    assert len(rows) == 1
    assert rows[0]["id"] == 1
    assert rows[0]["setupCompletedAt"] is None


async def test_settings_singleton_invariant_rejects_second_row(tmp_path: Path) -> None:
    """The ``CHECK (id = 1)`` invariant collides a second settings insert."""
    provider = _provider(tmp_path, "single.db")
    await provider.migrate()
    async with aiosqlite.connect(provider._database_path) as conn:
        # id=1 already seeded -> PRIMARY KEY collision.
        with pytest.raises(aiosqlite.IntegrityError):
            await conn.execute("INSERT INTO settings (id, setupCompletedAt) VALUES (1, NULL)")
            await conn.commit()
        # any other id -> CHECK (id = 1) collision.
        with pytest.raises(aiosqlite.IntegrityError):
            await conn.execute("INSERT INTO settings (id, setupCompletedAt) VALUES (2, NULL)")
            await conn.commit()


async def test_fresh_and_migrated_converge(tmp_path: Path) -> None:
    """A fresh DB and a v1.2-shaped DB converge on the same workspaces/settings schema."""
    fresh = _provider(tmp_path, "converge-fresh.db")
    await fresh.migrate()

    migrated_path = str(tmp_path / "converge-v12.db")
    await _apply_pre_003(migrated_path)  # 001 + 002 only, then full migrate() applies 003
    migrated = SqliteProvider(_DbSettings(database_path=migrated_path))
    await migrated.migrate()

    fresh_ws = _column_names(await _table_info(fresh._database_path, "workspaces"))
    migrated_ws = _column_names(await _table_info(migrated_path, "workspaces"))
    assert fresh_ws == migrated_ws
    assert "persistent" in fresh_ws

    fresh_settings = _column_names(await _table_info(fresh._database_path, "settings"))
    migrated_settings = _column_names(await _table_info(migrated_path, "settings"))
    assert fresh_settings == migrated_settings == {"id", "setupCompletedAt"}
