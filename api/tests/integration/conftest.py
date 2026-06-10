# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Integration-tier fixtures: ASGITransport over real SQLite + Fake compute + stub ttyd.

The ``integration_client`` fixture builds the real app (``create_app``) bound to an
``httpx.ASGITransport`` and drives it in-process — no live server. The app runs over:

- the **Fake** compute provider (``BURROW_COMPUTE=fake``, the shipped hermetic impl), and
- a **real** temp-SQLite DB (``settings.database_path`` pointed at ``tmp_path``), so the
  001+002 migrations actually run (exercises Plan 01).

The create saga's step-6 ttyd health GET is a real ``httpx`` call against the Fake's
VMID-derived IP (``10.99.0.<vmid>``). ``respx`` mocks that one httpx leg, returning 200
for ``http://10.99.0.*:7681/`` so ``_wait_ttyd`` resolves — the protocol-accurate
stub-ttyd for this tier (the tty subprotocol bridge is Phase 2). ``respx`` is the right
tool here: the ttyd leg is httpx, and proxmoxer (requests-based) is not involved over
the Fake.
"""

import json
import re
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import pytest
import respx
import websockets
from websockets.asyncio.server import ServerConnection, serve

from config import settings

# The Fake derives a worker IP from the VMID (10.99.0.<vmid % 256>); the stub ttyd
# answers the health GET on :7681 for any address in that range.
_TTYD_URL_PATTERN = re.compile(r"http://10\.99\.0\.\d+:7681/")


@pytest.fixture
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the shared settings at a temp DB + a known non-* CORS origin.

    ``get_db`` constructs a fresh ``SqliteProvider`` per request from
    ``settings.database_path``, so overriding it on the singleton is sufficient to
    isolate each test to its own migrated DB file. ``monkeypatch`` restores the
    originals at teardown.
    """
    monkeypatch.setattr(settings, "compute", "fake", raising=False)
    monkeypatch.setattr(settings, "database_path", str(tmp_path / "burrow-int.db"), raising=False)
    monkeypatch.setattr(settings, "allowed_origin", "http://burrow-ui.lan:5173", raising=False)


@pytest.fixture
def stub_ttyd() -> Iterator[respx.MockRouter]:
    """Mock the httpx ttyd-health GET so the create/start saga resolves (200)."""
    with respx.mock(assert_all_called=False) as router:
        router.get(url__regex=_TTYD_URL_PATTERN.pattern).mock(return_value=httpx.Response(200))
        yield router


@pytest.fixture
async def integration_client(
    _isolated_settings: None, stub_ttyd: respx.MockRouter
) -> AsyncIterator[httpx.AsyncClient]:
    """An ``httpx.AsyncClient`` bound to the real app over temp SQLite + Fake + stub ttyd."""
    # Import here so the settings overrides above are in effect when the app builds.
    from main import create_app, reset_compute

    # Fresh Fake compute per test: drop the process-wide singleton so no container
    # or VMID leaks from a prior test (the DB is already per-test via tmp_path).
    reset_compute()
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ─────────────────────────────────────────────────────────────────────────────
# Protocol-accurate stub ttyd (Phase 2 — the WS terminal bridge counterpart)
#
# This is NOT a bare echo. A bare echo would forward bytes regardless of frame
# type and never negotiate a subprotocol, so a proxy that drops the ``tty``
# subprotocol or ``.encode()``\s a text frame (the spec §6.4 SC-7 corruption bug)
# would still pass. This stub enforces the real ttyd ``tty`` contract so that
# regression FAILS CI:
#
#   - it advertises + requires the ``tty`` subprotocol on the upgrade,
#   - it requires the first frame to be the JSON init (``AuthToken/columns/rows``),
#   - it echoes INPUT (``'0'`` + data) back as OUTPUT (``'0'`` + data) preserving
#     the frame's text-vs-binary type, and silently accepts RESIZE (``'1'`` + JSON).
#
# A separate ``websockets.serve`` server (a different transport from the respx
# httpx health mock above) backs it on an ephemeral loopback port.
# ─────────────────────────────────────────────────────────────────────────────


class StubTtyd:
    """A live, protocol-accurate stub ttyd plus the bookkeeping tests assert on.

    ``url`` is the ``ws://host:port`` the proxy should dial. ``live`` is the count
    of currently-open upstream connections (the teardown-no-leak test asserts it
    returns to zero once the browser leg closes). ``text_echo`` records whether the
    most recent INPUT was echoed as a TEXT frame, so the SC-7 gate can prove the
    relay preserved frame type end-to-end.
    """

    def __init__(self, url: str) -> None:
        self.url = url
        self.live = 0
        self.connections = 0
        self.text_echo: bool | None = None


async def _stub_ttyd_handler(conn: ServerConnection, state: StubTtyd) -> None:
    """Speak the real ttyd ``tty`` protocol against the bridge's upstream leg."""
    # 1) The proxy MUST have negotiated the 'tty' subprotocol (TERM-02).
    assert conn.subprotocol == "tty", f"expected 'tty' subprotocol, got {conn.subprotocol!r}"
    state.connections += 1
    state.live += 1
    try:
        # 2) The first frame MUST be the JSON init (AuthToken/columns/rows).
        init = await conn.recv()
        raw_init = init.decode() if isinstance(init, (bytes, bytearray)) else init
        payload = json.loads(raw_init)
        assert {"AuthToken", "columns", "rows"} <= payload.keys()
        # 3) Echo INPUT ('0'+data) as OUTPUT ('0'+data) preserving frame TYPE so a
        #    relay that re-encodes a text frame to bytes (SC-7) is observable; accept
        #    RESIZE ('1'+JSON) silently.
        async for msg in conn:
            is_text = isinstance(msg, str)
            head = msg[:1]
            if head in ("0", b"0"):
                state.text_echo = is_text
                await conn.send(msg)  # verbatim: '0'-prefixed, same text-vs-binary type
            # head == '1' → RESIZE: accept and ignore (no echo)
    finally:
        state.live -= 1


@pytest.fixture
async def stub_ttyd_ws() -> AsyncIterator[StubTtyd]:
    """Start a protocol-accurate stub ttyd and yield its handle.

    The proxy's production dial is ``ws://{lxc_ip}:7681/ws``; point that at this
    stub in a test by monkeypatching ``routers.terminal._ttyd_url`` to return
    ``state.url`` (a test-only seam — the production URL construction is unchanged).
    """
    state: StubTtyd | None = None

    async def handler(conn: ServerConnection) -> None:
        assert state is not None
        await _stub_ttyd_handler(conn, state)

    async with serve(
        handler, "127.0.0.1", 0, subprotocols=[websockets.Subprotocol("tty")]
    ) as server:
        host, port = server.sockets[0].getsockname()[:2]
        state = StubTtyd(url=f"ws://{host}:{port}")
        yield state
