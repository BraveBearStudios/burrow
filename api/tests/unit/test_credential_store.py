# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Provider-level credential store + audit contract (ADR-0015).

Over a REAL ``SqliteProvider`` on a ``tmp_path`` DB, locks that:

- ``setCredentials`` stores Fernet CIPHERTEXT, never the plaintext, and
  ``getCredentialStatus`` returns status (set + last4) ONLY — never the value
  (the SETUP-07 never-round-tripped guarantee, extended to the at-rest store);
- the plaintext credential appears in NO cell of ANY table (a ``sqlite_master``
  scan), while the ciphertext IS present and round-trips back through ``SecretBox``;
- a partial write touches one credential without clearing the other;
- the admin secret is stored as an opaque hash, never as plaintext;
- ``writeAudit`` appends immutable rows carrying no secret value.
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pytest

from db.sqliteProvider import SqliteProvider
from lib.secretBox import EnvSecretKeyProvider, SecretBox, generate_key

# A recognizable plaintext: if it surfaces in any DB cell the store leaked.
PLAINTEXT = "glpat-REAL-SECRET-PAT-VALUE-DO-NOT-LEAK"


@dataclass
class _DbSettings:
    """Minimal settings stand-in: ``SqliteProvider`` only reads ``database_path``."""

    database_path: str


def _provider(tmp_path: Path, name: str = "creds.db") -> SqliteProvider:
    return SqliteProvider(_DbSettings(database_path=str(tmp_path / name)))


def _box() -> SecretBox:
    return SecretBox(EnvSecretKeyProvider(generate_key()))


def _all_cells(db_path: str) -> list[str]:
    """Every cell of every table (table list from ``sqlite_master``) as a string."""
    conn = sqlite3.connect(db_path)
    try:
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        ]
        cells: list[str] = []
        for table in tables:
            for row in conn.execute(f'SELECT * FROM "{table}"').fetchall():
                cells.extend(str(value) for value in row)
        return cells
    finally:
        conn.close()


async def test_setcredentials_stores_ciphertext_not_plaintext(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    box = _box()
    enc = box.encrypt(PLAINTEXT)
    await provider.setCredentials({"git_token_enc": enc, "git_token_last4": PLAINTEXT[-4:]})

    status = await provider.getCredentialStatus()
    assert status["gitTokenSet"] is True
    assert status["gitTokenLast4"] == PLAINTEXT[-4:]
    assert status["updatedAt"] is not None
    # Status must carry neither the plaintext nor the ciphertext.
    assert PLAINTEXT not in str(status)
    assert enc.decode("utf-8") not in str(status)

    # The plaintext appears in NO cell; the ciphertext IS persisted.
    cells = _all_cells(provider._database_path)
    assert all(PLAINTEXT not in cell for cell in cells), "plaintext credential leaked to a cell"
    assert any(enc.decode("utf-8") in cell for cell in cells), "ciphertext was not persisted"

    # The stored ciphertext round-trips back to the plaintext through SecretBox.
    got = await provider.getCredentialCiphertext("git_token")
    assert got is not None
    assert box.decrypt(got) == PLAINTEXT


async def test_partial_write_does_not_clear_other_credential(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    box = _box()
    await provider.setCredentials(
        {"proxmox_token_enc": box.encrypt("pve-token-value"), "proxmox_token_last4": "alue"}
    )
    await provider.setCredentials(
        {"git_token_enc": box.encrypt("git-pat-value"), "git_token_last4": "alue"}
    )
    status = await provider.getCredentialStatus()
    assert status["proxmoxTokenSet"] is True
    assert status["gitTokenSet"] is True
    assert status["proxmoxTokenLast4"] == "alue"
    assert status["gitTokenLast4"] == "alue"


async def test_unset_credentials_report_not_set(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    await provider.migrate()
    status = await provider.getCredentialStatus()
    assert status == {
        "proxmoxTokenSet": False,
        "proxmoxTokenLast4": None,
        "gitTokenSet": False,
        "gitTokenLast4": None,
        "updatedAt": None,
    }
    assert await provider.getCredentialCiphertext("git_token") is None


async def test_unknown_credential_field_rejected(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    await provider.migrate()
    with pytest.raises(KeyError):
        await provider.setCredentials({"bogus": b"x"})
    with pytest.raises(KeyError):
        await provider.getCredentialCiphertext("bogus")


async def test_admin_secret_hash_round_trips_without_plaintext(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    await provider.migrate()
    assert await provider.getAdminSecretHash() is None
    # The gate computes the argon2 hash; the provider stores the opaque string only.
    admin_hash = "$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQ$abcdefghij012345"
    await provider.setAdminSecret(admin_hash)
    assert await provider.getAdminSecretHash() == admin_hash
    cells = _all_cells(provider._database_path)
    assert any(admin_hash in cell for cell in cells)  # the hash is stored
    # The plaintext admin secret is never handed to the provider, so it is not at rest.
    assert all("super-secret-admin-password" not in cell for cell in cells)


async def test_writeaudit_appends_rows_without_secret(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    await provider.migrate()
    await provider.writeAudit(
        "credentials.update", "success", target="gitToken", source_ip="10.0.0.5", detail="****-pat"
    )
    await provider.writeAudit("admin.verify", "failure", source_ip="10.0.0.9")
    conn = sqlite3.connect(provider._database_path)
    try:
        rows = conn.execute(
            "SELECT action, outcome, target, sourceIp, detail, createdAt "
            "FROM audit_log ORDER BY createdAt, rowid"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 2
    assert rows[0][0] == "credentials.update" and rows[0][1] == "success"
    assert rows[1][0] == "admin.verify" and rows[1][1] == "failure"
    assert all(row[5] is not None for row in rows)  # createdAt auto-stamped
    assert all(PLAINTEXT not in str(value) for row in rows for value in row)
