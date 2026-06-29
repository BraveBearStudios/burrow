# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Migration ledger contract for the 003 + 004 settings migrations (WSX-02 / ADR-0015).

Locks the 003 and 004 migrations against regression over a REAL ``SqliteProvider``
on a ``tmp_path`` DB:

- the ``persistent`` column lands with a ``DEFAULT 0`` backfill — a v1.2-shaped row
  inserted BEFORE 003 reads back ``persistent is False`` (ADR-0013);
- the ``settings`` singleton is seeded ``id=1, setupCompletedAt IS NULL`` (ADR-0011);
- the ``CHECK (id = 1)`` singleton invariant holds — a second insert collides;
- a fresh DB and a migrated v1.2-shaped DB converge on the same schema;
- 004 (ADR-0015) adds the nullable credential columns to ``settings`` and the
  append-only ``audit_log`` table, and re-runs idempotently after a partial apply.
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
    assert fresh_settings == migrated_settings
    # 004 (ADR-0015) widens the settings singleton with the credential columns; the
    # fully converged schema is the 003 shape plus those.
    assert fresh_settings == {
        "id",
        "setupCompletedAt",
        "proxmoxTokenEnc",
        "proxmoxTokenLast4",
        "gitTokenEnc",
        "gitTokenLast4",
        "adminSecretHash",
        "credentialsUpdatedAt",
    }


async def _apply_partial_003(database_path: str) -> None:
    """Simulate a 003 apply that died mid-script: column added, 003 unledgered.

    ``executescript`` is non-atomic, so a failure after statement (1) commits leaves
    the ``persistent`` column durably added while the 003 ledger row is never written
    (the caller writes it only after the whole script returns). This reproduces that
    half-applied state: 001 + 002 ledgered, the ``persistent`` ALTER committed, the
    ``settings`` table absent, and NO ledger row for 003 (WR-03).
    """
    await _apply_pre_003(database_path)
    async with aiosqlite.connect(database_path) as conn:
        await conn.executescript(
            "ALTER TABLE workspaces ADD COLUMN persistent INTEGER NOT NULL DEFAULT 0;"
        )
        await conn.commit()


async def test_migrate_recovers_from_partial_003_apply(tmp_path: Path) -> None:
    """A re-run after a partial 003 apply converges instead of wedging (WR-03).

    Before the fix, the re-run's ``ALTER TABLE ... ADD COLUMN persistent`` raised
    ``OperationalError: duplicate column name`` and migration wedged permanently.
    The fix catches that on re-run and replays the idempotent remainder, so this
    asserts ``migrate()`` succeeds, 003 ends ledgered, the column survives, and the
    ``settings`` singleton is seeded.
    """
    db_path = str(tmp_path / "partial.db")
    await _apply_partial_003(db_path)

    provider = SqliteProvider(_DbSettings(database_path=db_path))
    await provider.migrate()  # must NOT raise "duplicate column name"

    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("SELECT version FROM schema_migrations")
        applied = {row["version"] for row in await cursor.fetchall()}
        await cursor.close()
        cursor = await conn.execute("SELECT id, setupCompletedAt FROM settings")
        settings_rows = list(await cursor.fetchall())
        await cursor.close()
    assert "003_persistent_and_settings" in applied
    assert "persistent" in _column_names(await _table_info(db_path, "workspaces"))
    assert len(settings_rows) == 1
    assert settings_rows[0]["id"] == 1
    assert settings_rows[0]["setupCompletedAt"] is None


# ── 004: credential store + audit log (ADR-0015) ────────────────────────────

_CREDENTIAL_COLUMNS = (
    "proxmoxTokenEnc",
    "proxmoxTokenLast4",
    "gitTokenEnc",
    "gitTokenLast4",
    "adminSecretHash",
    "credentialsUpdatedAt",
)


def _column_info(rows: list[aiosqlite.Row]) -> dict[str, aiosqlite.Row]:
    """Map column name -> its ``PRAGMA table_info`` row (notnull, dflt_value, pk)."""
    return {row["name"]: row for row in rows}


async def test_004_credential_columns_present_and_nullable(tmp_path: Path) -> None:
    """004 adds the six credential columns to ``settings``, all nullable, no default."""
    provider = _provider(tmp_path, "creds.db")
    await provider.migrate()
    info = _column_info(await _table_info(provider._database_path, "settings"))
    for column in _CREDENTIAL_COLUMNS:
        assert column in info, f"{column} missing from settings"
        assert info[column]["notnull"] == 0, f"{column} must be nullable (unconfigured deploy)"
        assert info[column]["dflt_value"] is None, f"{column} must have no default"
    # A freshly migrated deployment is unconfigured: every credential cell is NULL.
    async with aiosqlite.connect(provider._database_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT proxmoxTokenEnc, gitTokenEnc, adminSecretHash, credentialsUpdatedAt "
            "FROM settings WHERE id = 1"
        )
        row = await cursor.fetchone()
        await cursor.close()
    assert row is not None
    assert all(row[c] is None for c in row.keys())


async def test_audit_log_table_present_and_appendable(tmp_path: Path) -> None:
    """004 creates the append-only ``audit_log`` with an auto-stamped ``createdAt``."""
    provider = _provider(tmp_path, "audit.db")
    await provider.migrate()
    cols = _column_names(await _table_info(provider._database_path, "audit_log"))
    assert cols == {"id", "action", "target", "outcome", "sourceIp", "detail", "createdAt"}
    async with aiosqlite.connect(provider._database_path) as conn:
        conn.row_factory = aiosqlite.Row
        # action + outcome are NOT NULL; createdAt auto-stamps; no secret value present.
        await conn.execute(
            "INSERT INTO audit_log (id, action, outcome, sourceIp, detail) "
            "VALUES ('a1', 'credentials.update', 'success', '10.0.0.5', 'proxmoxToken ****1234')"
        )
        await conn.commit()
        cursor = await conn.execute("SELECT action, outcome, createdAt FROM audit_log WHERE id = 'a1'")
        row = await cursor.fetchone()
        await cursor.close()
    assert row is not None
    assert row["action"] == "credentials.update"
    assert row["outcome"] == "success"
    assert row["createdAt"] is not None  # DEFAULT strftime stamped it


async def test_migrate_recovers_from_partial_004_apply(tmp_path: Path) -> None:
    """A re-run after a partial 004 apply converges instead of wedging (WR-03).

    Reproduces the realistic half-applied state: the 004 script applied (all six
    credential ADD COLUMNs + the ``audit_log`` table) but the ``schema_migrations``
    ledger row was never written. The re-run's first ``ADD COLUMN`` raises
    ``duplicate column name``; ``migrate()``'s recovery strips the already-applied
    ALTERs and replays the idempotent ``CREATE TABLE IF NOT EXISTS audit_log``
    remainder, then the caller re-ledgers 004. A pre-existing audit row must survive
    (the table is append-only and IF NOT EXISTS preserves it).
    """
    db_path = str(tmp_path / "partial004.db")
    provider = SqliteProvider(_DbSettings(database_path=db_path))
    await provider.migrate()  # full 001-004, all ledgered
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            "INSERT INTO audit_log (id, action, outcome) VALUES ('keep', 'admin.verify', 'success')"
        )
        # Simulate "004 applied but never ledgered": drop only its ledger row.
        await conn.execute(
            "DELETE FROM schema_migrations WHERE version = '004_credentials_and_audit'"
        )
        await conn.commit()

    rerun = SqliteProvider(_DbSettings(database_path=db_path))
    await rerun.migrate()  # must NOT raise "duplicate column name"

    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("SELECT version FROM schema_migrations")
        applied = {row["version"] for row in await cursor.fetchall()}
        await cursor.close()
        cursor = await conn.execute("SELECT id FROM audit_log WHERE id = 'keep'")
        kept = await cursor.fetchone()
        await cursor.close()
    assert "004_credentials_and_audit" in applied
    assert _column_names(await _table_info(db_path, "settings")) >= set(_CREDENTIAL_COLUMNS)
    assert kept is not None  # append-only: recovery preserved the existing audit row


async def _apply_through_003(database_path: str) -> None:
    """001 + 002 + 003 applied and ledgered (the post-003 state, pre-004)."""
    await _apply_pre_003(database_path)
    async with aiosqlite.connect(database_path) as conn:
        sql = (_MIGRATIONS_DIR / "003_persistent_and_settings.sql").read_text(encoding="utf-8")
        await conn.executescript(sql)
        await conn.execute(
            "INSERT INTO schema_migrations (version) VALUES ('003_persistent_and_settings')"
        )
        await conn.commit()


async def test_migrate_recovers_from_mid_sequence_004_apply(tmp_path: Path) -> None:
    """A 004 re-run after only SOME of the six ADD COLUMNs applied still converges (WR-03).

    The earlier recovery stripped EVERY ALTER on a duplicate-column re-run, so a crash
    part-way through 004's six sequential ADD COLUMNs would drop the not-yet-added
    columns and wedge the store while ledgering 004 as done. The per-column recovery
    keeps the still-missing ALTERs: here columns 1-3 are pre-applied (unledgered) and
    the re-run must add columns 4-6 + create audit_log, then ledger 004.
    """
    db_path = str(tmp_path / "mid004.db")
    await _apply_through_003(db_path)
    # Apply ONLY the first three 004 credential ADD COLUMNs; the rest (+ audit_log) and
    # the 004 ledger row are absent — a faithful mid-sequence half-apply.
    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript(
            "ALTER TABLE settings ADD COLUMN proxmoxTokenEnc BLOB;"
            "ALTER TABLE settings ADD COLUMN proxmoxTokenLast4 TEXT;"
            "ALTER TABLE settings ADD COLUMN gitTokenEnc BLOB;"
        )
        await conn.commit()

    provider = SqliteProvider(_DbSettings(database_path=db_path))
    await provider.migrate()  # must converge, not wedge on "duplicate column name"

    settings_cols = _column_names(await _table_info(db_path, "settings"))
    assert set(_CREDENTIAL_COLUMNS) <= settings_cols, "the not-yet-applied columns were added"
    audit_cols = _column_names(await _table_info(db_path, "audit_log"))
    assert "action" in audit_cols, "audit_log was created by the recovery"
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("SELECT version FROM schema_migrations")
        applied = {row["version"] for row in await cursor.fetchall()}
        await cursor.close()
    assert "004_credentials_and_audit" in applied
