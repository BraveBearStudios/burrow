# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""SETUP-07 hard gate: the sentinel-token leak test (STATE blocker gate #3).

This is the RED-IF-REGRESSED proof that the operator-typed PVE token (the one
HIGH-value asset of the setup flow) never escapes the request boundary. A known
sentinel token value is driven through BOTH setup endpoints, and the sentinel
substring is then asserted absent from:

1. the raw response text of either call (covers ``data`` AND ``error``);
2. EVERY row of EVERY table in the live temp SQLite DB — the table list is
   enumerated from ``sqlite_master`` (NOT hardcoded), so a future table cannot
   silently leak;
3. every captured log line/event (the root JSON handler is duplicated onto a
   StringIO at DEBUG, so even a driver DEBUG line would be caught).

It flips RED the instant anyone:
- logs the settings object or the request body,
- echoes ``str(proxmoxer_exc)`` into an envelope or log, or
- persists the token to any DB row.

The flow runs over the ``integration_client`` fixture (real temp SQLite + the
Fake compute provider). The Fake validates the token in-memory exactly as the
real provider does (never storing/returning/logging it), so the leak surfaces
this test probes — the router body, the envelope, the DB, the logs — are the
SAME control-plane surfaces a real provider would expose.
"""

import logging
import sqlite3
from collections.abc import Iterator
from io import StringIO

import httpx
import pytest

from config import settings
from lib.logging import JsonFormatter

# The known sentinel. If this string appears in a DB row, an envelope, or a log
# line after the setup flow, the token leaked — the gate is RED.
SENTINEL = "SENTINEL-TOKEN-DO-NOT-LEAK"

_CONNECT_BODY = {
    "host": "pve1.local",
    "user": "burrow@pve",
    "tokenName": "burrow",
    "tokenValue": SENTINEL,
}
# verify-template carries no token field, but it is still driven so the whole
# setup surface is swept for the sentinel in one flow.
_TEMPLATE_BODY = {"templateVmid": 9000, "node": "pve1"}


@pytest.fixture
def captured_logs() -> Iterator[StringIO]:
    """Duplicate the root logger onto a StringIO at DEBUG to catch any token leak.

    A second handler (same :class:`JsonFormatter` the app uses) is attached to the
    root logger at ``DEBUG`` BEFORE the request, so a token echoed at ANY level —
    including a driver DEBUG line the app's WARNING pin is meant to suppress — would
    be captured here and fail the assertion. Restored at teardown.
    """
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


def _scan_all_db_cells(db_path: str) -> tuple[list[str], list[str]]:
    """Return ``(every-cell-as-string, table-names)`` (table list from sqlite_master).

    Exhaustive by construction: the table set is read from ``sqlite_master`` rather
    than hardcoded, so a future migration adding a table is swept automatically — a
    new write path that persisted the token could not slip past this scan. The table
    names are returned too so the caller can prove the scan was non-vacuous (it saw
    the ``settings`` table, the most likely token-at-rest target).
    """
    cells: list[str] = []
    conn = sqlite3.connect(db_path)
    try:
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        ]
        assert tables, "expected at least one table in the migrated temp DB"
        for table in tables:
            for row in conn.execute(f'SELECT * FROM "{table}"').fetchall():
                cells.extend(str(value) for value in row)
    finally:
        conn.close()
    return cells, tables


async def test_sentinel_token_never_leaks_to_db_envelope_or_logs(
    integration_client: httpx.AsyncClient, captured_logs: StringIO
) -> None:
    """RED-IF-REGRESSED: the sentinel token is in no DB row, no envelope, no log line."""
    # Migrate the temp DB to its full schema FIRST (a workspaces read triggers
    # _ensure_migrated) so the sqlite_master scan below covers the REAL table set
    # — workspaces, events, settings, schema_migrations — not an empty file. The
    # setup endpoints themselves never touch the DB, which is exactly the point:
    # after the flow, every one of those tables must still be sentinel-free.
    seed_resp = await integration_client.get("/api/v1/workspaces")
    assert seed_resp.status_code == 200, seed_resp.text

    # Drive the full setup surface with the sentinel as the token value.
    connect_resp = await integration_client.post(
        "/api/v1/setup/test-connection", json=_CONNECT_BODY
    )
    template_resp = await integration_client.post(
        "/api/v1/setup/verify-template", json=_TEMPLATE_BODY
    )
    assert connect_resp.status_code == 200, connect_resp.text
    assert template_resp.status_code == 200, template_resp.text

    # (1) Envelope: the sentinel is in neither response's raw text (data AND error).
    assert SENTINEL not in connect_resp.text, "token leaked into the test-connection envelope"
    assert SENTINEL not in template_resp.text, "token leaked into the verify-template envelope"

    # (2) DB: scan EVERY table (enumerated from sqlite_master) — no cell holds it.
    cells, tables = _scan_all_db_cells(settings.database_path)
    # Non-vacuous proof: the scan saw the singleton settings table (the most likely
    # token-at-rest target) — so a sentinel in a settings cell WOULD be caught.
    assert "settings" in tables, f"scan did not reach the settings table: {tables}"
    leaking = [cell for cell in cells if SENTINEL in cell]
    assert not leaking, f"token persisted to a DB row: {leaking}"

    # (3) Logs: the captured DEBUG stream never emitted the sentinel.
    log_output = captured_logs.getvalue()
    assert SENTINEL not in log_output, "token reached a log line/event"


async def test_sentinel_absent_from_422_validation_body(
    integration_client: httpx.AsyncClient, captured_logs: StringIO
) -> None:
    """RED-IF-REGRESSED: a 422 setup body carrying the sentinel token never echoes it.

    WR-05: the 422 handler's leak protection rests on two layers -- (1) the
    RequestValidationError handler drops the raw ``input``/``ctx``, keeping only
    ``loc``/``msg``/``type``; and (2) ``token_value`` is a ``SecretStr`` so the value
    is masked even if a future validator interpolated it into ``msg``. POST a body
    that triggers a 422 (a sibling required field -- ``host`` -- omitted) WITH the
    sentinel as ``tokenValue`` and assert the sentinel is absent from the 422 body
    and the logs. Reverting the handler's input-strip OR the SecretStr field flips
    this RED, locking both backstops together.
    """
    bad_body = {**_CONNECT_BODY}
    del bad_body["host"]  # omit a sibling required field -> 422, sentinel still present

    response = await integration_client.post(
        "/api/v1/setup/test-connection", json=bad_body
    )

    assert response.status_code == 422, response.text
    assert SENTINEL not in response.text, "token leaked into the 422 validation body"
    assert SENTINEL not in captured_logs.getvalue(), "token reached a log line on 422"


async def test_sentinel_absent_even_on_auth_failure_envelope(
    integration_client: httpx.AsyncClient, captured_logs: StringIO
) -> None:
    """Even a rejected-token error path keeps the sentinel out of the envelope + logs.

    Drives the auth-fail branch (the path most likely to echo the rejected token via
    ``str(exc)``) and asserts the sentinel still never reaches the error envelope or
    a log line — the fixed token-free message is what surfaces.
    """
    from compute.fakeProvider import FakeComputeProvider, FakeFailures
    import main

    failing = FakeComputeProvider(FakeFailures(setup_auth_fails=True))
    # Seed the process-wide compute singleton so the endpoint uses the failing Fake.
    monkeypatch_singleton(failing)
    try:
        response = await integration_client.post(
            "/api/v1/setup/test-connection", json=_CONNECT_BODY
        )
    finally:
        main._compute_singleton = None
        main._compute_kind = None

    assert response.json()["error"]["code"] == "setup_auth_failed"
    assert SENTINEL not in response.text, "rejected token leaked into the error envelope"
    assert SENTINEL not in captured_logs.getvalue(), "rejected token reached a log line"


def monkeypatch_singleton(provider: object) -> None:
    """Seed ``main``'s compute singleton so ``get_compute()`` returns ``provider``."""
    import main

    main._compute_singleton = provider  # type: ignore[assignment]
    main._compute_kind = settings.compute
