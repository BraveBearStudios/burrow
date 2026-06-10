# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Integration: the ``/ws/workspaces/{id}/terminal`` tty-subprotocol bridge (TERM-01..04).

Drives the REAL FastAPI app under an in-process ``uvicorn.Server`` (so the native
Starlette WebSocket route runs end-to-end) bridging the browser leg to the
**protocol-accurate** stub ttyd from ``conftest.stub_ttyd_ws``. Everything lives on
the one pytest-asyncio event loop: the app server, the stub ttyd, and the browser
``websockets`` client. The proxy's production dial is ``ws://{lxc_ip}:7681/ws``; a
test-only seam (``routers.terminal._ttyd_url``) redirects it at the stub's ephemeral
port without changing the production URL construction (SSRF guard stays intact).

Proven here:

- TERM-01/02: the bridge negotiates ``tty`` and relays frames opaquely both ways.
- SC-7: a TEXT frame survives as TEXT (a ``.encode()``/``send_bytes`` regression on
  the down leg FAILS ``test_preserves_text_frame`` — the stub records the echoed type).
- TERM-03: a typed ``{"type":"error","code":"LXC_NOT_READY"}`` frame is emitted when
  ttyd is unreachable; ``terminal.connected``/``terminal.disconnected`` events carry
  ``{}`` (no lxc_ip, no frame content).
- TERM-04: closing the browser leg tears the upstream down (no half-open leak); a
  non-running / missing / wrong-origin upgrade closes with 1008 BEFORE accept.
"""

import asyncio
import contextlib
import json
import socket
from collections.abc import AsyncIterator
from typing import Any

import pytest
import uvicorn
import websockets
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from config import settings

from .conftest import StubTtyd

# A workspace whose terminal the bridge will proxy. The Fake/DB is bypassed for the
# bridge unit-of-test: we monkeypatch ``db.getWorkspace`` to return this row so the
# test stays focused on the relay rather than re-running the create saga.
_RUNNING_WS = {
    "id": "ws-running",
    "name": "alpha",
    "status": "running",
    "vmid": 201,
    "node": "pve1",
    "lxc_ip": "10.99.0.201",
    "project_repo": "git@example.com:acme/alpha.git",
    "project_branch": "main",
    "plugin_set": "default",
    "created_at": "2026-06-10T00:00:00+00:00",
    "stopped_at": None,
    "destroyed_at": None,
    "deleted_at": None,
}

_TTYD_INIT = json.dumps({"AuthToken": "", "columns": 80, "rows": 24})


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port: int = sock.getsockname()[1]
    sock.close()
    return port


class _Bridge:
    """Handle for a running in-process app: ``ws_url(id)`` builds the browser-leg URL."""

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self.events: list[tuple[str, str, dict[str, Any]]] = []

    def ws_url(self, workspace_id: str) -> str:
        return f"ws://{self._host}:{self._port}/ws/workspaces/{workspace_id}/terminal"


@pytest.fixture
async def bridge(
    _isolated_settings: None,
    stub_ttyd_ws: StubTtyd,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[_Bridge]:
    """Boot the real app on an ephemeral port with the upstream dial pointed at the stub.

    The browser leg hits the real Starlette WS route; the upstream leg dials the stub
    ttyd via the ``routers.terminal._ttyd_url`` seam. ``db.getWorkspace`` and
    ``db.logEvent`` are stubbed so the test exercises only the relay (no saga), and
    every logged event is captured on the handle for the connect/disconnect assertions.
    """
    from main import create_app, reset_compute
    import routers.terminal as terminal_module

    reset_compute()
    host, port = "127.0.0.1", _free_port()
    handle = _Bridge(host, port)

    # Redirect the production ``ws://{lxc_ip}:7681/ws`` dial at the stub's port.
    monkeypatch.setattr(terminal_module, "_ttyd_url", lambda lxc_ip: stub_ttyd_ws.url)

    # Stub the DB seam the bridge reads: a single running workspace + event capture.
    workspaces: dict[str, dict[str, Any]] = {_RUNNING_WS["id"]: _RUNNING_WS}

    async def fake_get_workspace(self: Any, workspace_id: str) -> Any:
        from models.workspace import Workspace

        row = workspaces.get(workspace_id)
        return Workspace(**row) if row is not None else None

    async def fake_log_event(
        self: Any, workspace_id: str, event_type: str, data: dict[str, Any]
    ) -> None:
        handle.events.append((workspace_id, event_type, data))

    from db.sqliteProvider import SqliteProvider

    monkeypatch.setattr(SqliteProvider, "getWorkspace", fake_get_workspace)
    monkeypatch.setattr(SqliteProvider, "logEvent", fake_log_event)
    handle.workspaces = workspaces  # type: ignore[attr-defined]

    config = uvicorn.Config(
        create_app(), host=host, port=port, log_level="warning", lifespan="off"
    )
    server = uvicorn.Server(config)
    serve_task = asyncio.create_task(server.serve())
    try:
        while not server.started:
            await asyncio.sleep(0.01)
        yield handle
    finally:
        server.should_exit = True
        await serve_task


async def _open_browser_leg(url: str) -> Any:
    """Open the browser-side WS and send the ttyd JSON init (as the xterm adapter does)."""
    conn = await connect(url)
    await conn.send(_TTYD_INIT)
    return conn


async def test_bridges_both_directions(bridge: _Bridge) -> None:
    """Browser sends INPUT ('0'+data); the stub echoes OUTPUT ('0'+data) back (TERM-01)."""
    async with await _open_browser_leg(bridge.ws_url("ws-running")) as conn:
        await conn.send("0hello")
        reply = await asyncio.wait_for(conn.recv(), timeout=2)
        assert (reply.decode() if isinstance(reply, bytes) else reply) == "0hello"


async def test_preserves_text_frame(bridge: _Bridge, stub_ttyd_ws: StubTtyd) -> None:
    """A TEXT frame round-trips as TEXT — a .encode()/send_bytes regression FAILS (SC-7)."""
    async with await _open_browser_leg(bridge.ws_url("ws-running")) as conn:
        await conn.send("0text-frame")  # str → TEXT frame
        reply = await asyncio.wait_for(conn.recv(), timeout=2)
        # The stub echoed the down-leg frame; it recorded whether the relay kept it TEXT.
        assert stub_ttyd_ws.text_echo is True
        assert isinstance(reply, str), "down-leg TEXT frame must arrive as str, not bytes"
        assert reply == "0text-frame"


async def test_error_frame_when_ttyd_unreachable(
    bridge: _Bridge, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no ttyd listening, the browser leg gets {type:error, code:LXC_NOT_READY} (TERM-03)."""
    import routers.terminal as terminal_module

    # Point the dial at a closed port so the upstream connect fails.
    dead = f"ws://127.0.0.1:{_free_port()}"
    monkeypatch.setattr(terminal_module, "_ttyd_url", lambda lxc_ip: dead)

    async with await _open_browser_leg(bridge.ws_url("ws-running")) as conn:
        raw = await asyncio.wait_for(conn.recv(), timeout=2)
        payload = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
        assert payload == {"type": "error", "code": "LXC_NOT_READY"}


async def test_teardown_no_halfopen(bridge: _Bridge, stub_ttyd_ws: StubTtyd) -> None:
    """Closing the browser leg closes the upstream — no leaked half-open connection (TERM-04)."""
    conn = await _open_browser_leg(bridge.ws_url("ws-running"))
    await conn.send("0ping")
    assert (await asyncio.wait_for(conn.recv(), timeout=2)) is not None
    assert stub_ttyd_ws.live == 1  # upstream is open while the browser leg is open
    await conn.close()
    # The bridge must observe the browser close and cancel the upstream pump.
    for _ in range(200):
        if stub_ttyd_ws.live == 0:
            break
        await asyncio.sleep(0.01)
    assert stub_ttyd_ws.live == 0, "upstream ttyd connection leaked (half-open)"


@pytest.mark.parametrize("workspace_id", ["ws-creating", "ws-missing"])
async def test_rejects_non_running(bridge: _Bridge, workspace_id: str) -> None:
    """A creating/missing workspace closes with 1008 BEFORE accept (TERM-04 / access)."""
    if workspace_id == "ws-creating":
        bridge.workspaces["ws-creating"] = {  # type: ignore[attr-defined]
            **_RUNNING_WS,
            "id": "ws-creating",
            "status": "creating",
            "lxc_ip": None,
            "vmid": 202,
        }
    with pytest.raises(ConnectionClosed) as excinfo:
        async with await _open_browser_leg(bridge.ws_url(workspace_id)) as conn:
            await conn.recv()
    assert excinfo.value.rcvd is not None
    assert excinfo.value.rcvd.code == 1008


async def test_rejects_bad_origin(bridge: _Bridge) -> None:
    """A mismatched Origin header closes with 1008 before accept (CSWSH defense)."""
    with pytest.raises(ConnectionClosed) as excinfo:
        async with connect(
            bridge.ws_url("ws-running"), additional_headers={"Origin": "http://evil.example"}
        ) as conn:
            await conn.recv()
    assert excinfo.value.rcvd is not None
    assert excinfo.value.rcvd.code == 1008


async def test_allows_configured_origin(bridge: _Bridge) -> None:
    """The configured LAN Origin is accepted (the gate is allow-list, not deny-all)."""
    async with connect(
        bridge.ws_url("ws-running"), additional_headers={"Origin": settings.allowed_origin}
    ) as conn:
        await conn.send(_TTYD_INIT)
        await conn.send("0ok")
        reply = await asyncio.wait_for(conn.recv(), timeout=2)
        assert (reply.decode() if isinstance(reply, bytes) else reply) == "0ok"


async def test_logs_connect_disconnect(bridge: _Bridge) -> None:
    """connect/disconnect events are logged with {} data — no lxc_ip, no frame content (TERM-03/V7)."""
    conn = await _open_browser_leg(bridge.ws_url("ws-running"))
    await conn.send("0x")
    await asyncio.wait_for(conn.recv(), timeout=2)
    await conn.close()
    # Allow the server-side finally block to run.
    for _ in range(200):
        types = [evt[1] for evt in bridge.events]
        if "terminal.connected" in types and "terminal.disconnected" in types:
            break
        await asyncio.sleep(0.01)
    types = [evt[1] for evt in bridge.events]
    assert "terminal.connected" in types
    assert "terminal.disconnected" in types
    for _wid, evt_type, data in bridge.events:
        if evt_type.startswith("terminal."):
            assert data == {}, "terminal events must carry empty data (no lxc_ip / no content)"
