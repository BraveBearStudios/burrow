# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Credential endpoints contract (ADR-0015), over real temp SQLite + Fake.

``POST``/``GET`` ``/api/v1/setup/credentials``:

- both are admin-gated (``require_admin``): 401 without a valid ``X-Burrow-Admin``;
- a write encrypts at rest, and the status read returns set + last4, NEVER the value;
- a Proxmox token is validated via ``testConnection`` BEFORE persist (a rejected token
  is not stored);
- the saved git-token SENTINEL never lands as plaintext in any cell / envelope / log,
  while the ciphertext IS stored and decrypts back;
- a write with ``BURROW_SECRET_KEY`` unset is a 503 ``credential_store_unconfigured``.
"""

import logging
import secrets
import sqlite3
from collections.abc import Iterator
from io import StringIO

import httpx
import pytest
from pydantic import SecretStr

from config import settings
from lib.logging import JsonFormatter
from lib.secretBox import EnvSecretKeyProvider, SecretBox, generate_key

ADMIN = "test-admin-secret-1234"
GIT_SENTINEL = "ghp-GITTOKEN-SENTINEL-DO-NOT-LEAK-0123456789"
# A per-run unique sentinel so a stale value can never satisfy the leak sweep by
# accident; the ``-DO-NOT-LOG`` suffix makes any leak obvious in output.
CRED_SENTINEL = f"SENTINEL-cred-{secrets.token_hex(8)}-DO-NOT-LOG"


@pytest.fixture
def store_key(monkeypatch: pytest.MonkeyPatch) -> str:
    """Configure a real ``BURROW_SECRET_KEY`` for the duration of a test."""
    key = generate_key()
    monkeypatch.setattr(settings, "burrow_secret_key", SecretStr(key), raising=False)
    return key


@pytest.fixture
def captured_logs() -> Iterator[StringIO]:
    """Duplicate the root logger onto a StringIO at DEBUG to catch any secret leak."""
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.setLevel(logging.DEBUG)
    root = logging.getLogger()
    previous = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    try:
        yield stream
    finally:
        root.removeHandler(handler)
        root.setLevel(previous)


def _all_cells(db_path: str) -> list[str]:
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


async def _set_admin(client: httpx.AsyncClient) -> dict[str, str]:
    resp = await client.post("/api/v1/setup/admin-secret", json={"secret": ADMIN})
    assert resp.status_code == 200, resp.text
    return {"X-Burrow-Admin": ADMIN}


async def test_credential_endpoints_require_admin(
    integration_client: httpx.AsyncClient, store_key: str
) -> None:
    # No admin secret set yet -> the gate rejects (no header).
    assert (await integration_client.get("/api/v1/setup/credentials")).status_code == 401
    blocked = await integration_client.post(
        "/api/v1/setup/credentials", json={"gitToken": "valid-length-token"}
    )
    assert blocked.status_code == 401
    assert blocked.json()["error"]["code"] == "admin_unauthorized"

    headers = await _set_admin(integration_client)
    # A wrong header is still 401.
    wrong = await integration_client.get(
        "/api/v1/setup/credentials", headers={"X-Burrow-Admin": "nope"}
    )
    assert wrong.status_code == 401
    # The correct header -> 200.
    good = await integration_client.get("/api/v1/setup/credentials", headers=headers)
    assert good.status_code == 200


async def test_save_then_status_never_returns_value(
    integration_client: httpx.AsyncClient, store_key: str
) -> None:
    headers = await _set_admin(integration_client)
    saved = await integration_client.post(
        "/api/v1/setup/credentials",
        headers=headers,
        json={"gitToken": "ghp_pat_value_wxyz", "proxmoxTokenValue": "pve_token_value_abcd"},
    )
    assert saved.status_code == 200, saved.text
    data = saved.json()["data"]
    assert data["gitTokenSet"] is True and data["gitTokenLast4"] == "wxyz"
    assert data["proxmoxTokenSet"] is True and data["proxmoxTokenLast4"] == "abcd"
    assert data["updatedAt"] is not None

    status = await integration_client.get("/api/v1/setup/credentials", headers=headers)
    assert "ghp_pat_value_wxyz" not in status.text
    assert "pve_token_value_abcd" not in status.text


async def test_proxmox_token_validated_before_persist(
    integration_client: httpx.AsyncClient, store_key: str
) -> None:
    import main
    from compute.fakeProvider import FakeComputeProvider, FakeFailures

    headers = await _set_admin(integration_client)
    # Seed a failing Fake so testConnection rejects the token before any persist.
    main._compute_singleton = FakeComputeProvider(FakeFailures(setup_auth_fails=True))
    main._compute_kind = settings.compute
    try:
        rejected = await integration_client.post(
            "/api/v1/setup/credentials", headers=headers, json={"proxmoxTokenValue": "bad-token"}
        )
    finally:
        main._compute_singleton = None
        main._compute_kind = None

    assert rejected.json()["error"]["code"] == "setup_auth_failed"
    # The rejected token was NOT persisted.
    status = await integration_client.get("/api/v1/setup/credentials", headers=headers)
    assert status.json()["data"]["proxmoxTokenSet"] is False


async def test_saved_git_token_never_plaintext_at_rest(
    integration_client: httpx.AsyncClient, store_key: str, captured_logs: StringIO
) -> None:
    headers = await _set_admin(integration_client)
    saved = await integration_client.post(
        "/api/v1/setup/credentials", headers=headers, json={"gitToken": GIT_SENTINEL}
    )
    assert saved.status_code == 200, saved.text
    assert GIT_SENTINEL not in saved.text  # status never echoes the value

    cells = _all_cells(settings.database_path)
    assert all(GIT_SENTINEL not in cell for cell in cells), "git token plaintext at rest"

    # The ciphertext IS stored and decrypts back with the same key.
    conn = sqlite3.connect(settings.database_path)
    try:
        row = conn.execute("SELECT gitTokenEnc FROM settings WHERE id = 1").fetchone()
    finally:
        conn.close()
    assert row is not None and row[0] is not None
    assert SecretBox(EnvSecretKeyProvider(store_key)).decrypt(row[0]) == GIT_SENTINEL

    assert GIT_SENTINEL not in captured_logs.getvalue()


async def test_too_short_credential_is_leak_free_422(
    integration_client: httpx.AsyncClient, store_key: str
) -> None:
    headers = await _set_admin(integration_client)
    resp = await integration_client.post(
        "/api/v1/setup/credentials", headers=headers, json={"gitToken": "short"}
    )
    assert resp.status_code == 422, resp.text
    # The submitted value is never echoed (SecretStr mask + input-stripping handler).
    assert "short" not in resp.text


async def test_write_without_store_key_is_503(integration_client: httpx.AsyncClient) -> None:
    # No store_key fixture -> BURROW_SECRET_KEY is the empty default, so the store
    # cannot encrypt and the write is refused with a token-free 503.
    headers = await _set_admin(integration_client)
    resp = await integration_client.post(
        "/api/v1/setup/credentials", headers=headers, json={"gitToken": "anything"}
    )
    assert resp.status_code == 503, resp.text
    assert resp.json()["error"]["code"] == "credential_store_unconfigured"


async def test_cred_sentinel_never_leaks_but_ciphertext_roundtrips(
    integration_client: httpx.AsyncClient, store_key: str, captured_logs: StringIO
) -> None:
    """CRED-07 RED-IF-REGRESSED: a saved credential leaks its plaintext NOWHERE — no
    DB cell (``settings``/``audit_log``), no API envelope (save / status / audit), no
    log line — yet the ciphertext IS stored, is not the plaintext, and decrypts back.
    """
    headers = await _set_admin(integration_client)
    saved = await integration_client.post(
        "/api/v1/setup/credentials", headers=headers, json={"gitToken": CRED_SENTINEL}
    )
    assert saved.status_code == 200, saved.text

    # (a) No cell of ANY table (enumerated from sqlite_master, incl. settings and
    #     audit_log) holds the plaintext.
    cells = _all_cells(settings.database_path)
    assert all(CRED_SENTINEL not in cell for cell in cells), "credential plaintext at rest"

    # (b) No API envelope echoes the plaintext: the save response, the status read,
    #     and the audit read.
    status = await integration_client.get("/api/v1/setup/credentials", headers=headers)
    audit = await integration_client.get("/api/v1/setup/audit", headers=headers)
    assert audit.status_code == 200, audit.text
    assert CRED_SENTINEL not in saved.text, "plaintext leaked into the save envelope"
    assert CRED_SENTINEL not in status.text, "plaintext leaked into the status envelope"
    assert CRED_SENTINEL not in audit.text, "plaintext leaked into the audit envelope"

    # Non-vacuous: the audit read returned the credentials.update row this write left
    # (last4 only, never the value) — proving the audit_log sweep above saw real rows.
    entries = audit.json()["data"]["entries"]
    assert any(entry["action"] == "credentials.update" for entry in entries)

    # (c) No captured log line holds the plaintext.
    assert CRED_SENTINEL not in captured_logs.getvalue(), "plaintext reached a log line"

    # POSITIVE contract: the ciphertext BLOB is stored, is NOT the plaintext, and
    # decrypts back via the same key; the stored last4 == the sentinel's last four.
    conn = sqlite3.connect(settings.database_path)
    try:
        row = conn.execute(
            "SELECT gitTokenEnc, gitTokenLast4 FROM settings WHERE id = 1"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None and row[0] is not None
    assert row[0] != CRED_SENTINEL.encode(), "ciphertext must not be the plaintext bytes"
    assert SecretBox(EnvSecretKeyProvider(store_key)).decrypt(row[0]) == CRED_SENTINEL
    assert row[1] == CRED_SENTINEL[-4:]
