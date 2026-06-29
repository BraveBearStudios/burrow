# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Admin-secret endpoint contract (ADR-0015), over real temp SQLite + Fake.

Locks ``POST /api/v1/setup/admin-secret``:

- first-run (no secret yet) sets the admin secret UNAUTHENTICATED (the wizard sets it
  before setup completes, under the LAN-only trust boundary);
- CHANGING an existing secret WITHOUT the current one is 401 ``admin_unauthorized``;
- changing WITH the correct current secret succeeds;
- a too-short secret is a leak-free 422;
- the admin-secret SENTINEL never lands in a DB cell (only its argon2id hash), an
  envelope, or a log line.
"""

import logging
import sqlite3
from collections.abc import Iterator
from io import StringIO

import httpx
import pytest

from config import settings
from lib.logging import JsonFormatter

# A recognizable admin secret: if it surfaces anywhere at rest, the gate leaked.
ADMIN_SENTINEL = "ADMIN-SECRET-DO-NOT-LEAK-0123456789"


@pytest.fixture
def captured_logs() -> Iterator[StringIO]:
    """Duplicate the root logger onto a StringIO at DEBUG to catch any secret leak."""
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.setLevel(logging.DEBUG)
    root = logging.getLogger()
    previous_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    try:
        yield stream
    finally:
        root.removeHandler(handler)
        root.setLevel(previous_level)


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


async def test_first_run_sets_then_change_requires_current(
    integration_client: httpx.AsyncClient,
) -> None:
    # First-run: no secret yet -> set it unauthenticated.
    first = await integration_client.post(
        "/api/v1/setup/admin-secret", json={"secret": ADMIN_SENTINEL}
    )
    assert first.status_code == 200, first.text
    assert first.json()["data"]["adminSecretSet"] is True

    # Change WITHOUT the current secret -> 401, oracle-free code.
    no_current = await integration_client.post(
        "/api/v1/setup/admin-secret", json={"secret": "another-secret-value"}
    )
    assert no_current.status_code == 401, no_current.text
    assert no_current.json()["error"]["code"] == "admin_unauthorized"

    # Change WITH the correct current secret -> 200.
    with_current = await integration_client.post(
        "/api/v1/setup/admin-secret",
        json={"secret": "another-secret-value", "currentSecret": ADMIN_SENTINEL},
    )
    assert with_current.status_code == 200, with_current.text


async def test_too_short_secret_is_leak_free_422(
    integration_client: httpx.AsyncClient,
) -> None:
    response = await integration_client.post(
        "/api/v1/setup/admin-secret", json={"secret": "short"}
    )
    assert response.status_code == 422, response.text
    # The submitted value is never echoed (SecretStr mask + input-stripping handler).
    assert "short" not in response.text


async def test_admin_secret_never_leaks_to_db_or_logs(
    integration_client: httpx.AsyncClient, captured_logs: StringIO
) -> None:
    response = await integration_client.post(
        "/api/v1/setup/admin-secret", json={"secret": ADMIN_SENTINEL}
    )
    assert response.status_code == 200, response.text
    assert ADMIN_SENTINEL not in response.text, "secret leaked into the envelope"

    cells = _all_cells(settings.database_path)
    assert all(ADMIN_SENTINEL not in cell for cell in cells), "admin secret plaintext at rest"
    assert any("$argon2id$" in cell for cell in cells), "argon2 hash was not stored"

    assert ADMIN_SENTINEL not in captured_logs.getvalue(), "secret reached a log line"
