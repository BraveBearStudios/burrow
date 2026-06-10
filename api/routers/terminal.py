# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Terminal bridge router — ``/ws/workspaces/{id}/terminal`` (TERM-01..04).

An opaque, type-preserving WebSocket relay between the browser's xterm client and
the worker's ttyd. It is deliberately a *dumb* relay: the browser owns ttyd's
``tty`` protocol (the JSON init, ``'0'``-prefixed INPUT, ``'1'``-prefixed RESIZE),
so the proxy forwards every frame VERBATIM, preserving text-vs-binary. It never
parses, re-encodes, or logs frame content.

The single load-bearing correctness rule (SC-7): NEVER ``.encode()`` a text frame.
A ``str`` frame is relayed with ``send_text``, a ``bytes`` frame with
``send_bytes`` — on BOTH legs. Re-encoding a ttyd text control frame to bytes
(spec §6.4) produces a connected-but-dead terminal; the protocol-accurate stub
ttyd in the test suite makes that regression fail CI.

Security (this is the one WS surface; v1 is LAN-only no-auth by design):

- **SSRF guard (T-02-01):** the upstream URL is built ONLY from the looked-up
  ``workspace.lxc_ip`` (``ws://{lxc_ip}:7681/ws``) — never from a header, query
  param, or sub-path. Client input selects only the workspace *id* (path), which
  resolves to a DB row; the host is never client-controlled.
- **Access gate (T-02-02):** a missing / non-``running`` / IP-less workspace is
  rejected with WS close ``1008`` BEFORE ``accept`` (no upstream dial).
- **CSWSH gate (T-02-03):** Starlette WebSockets do NOT honor the HTTP CORS
  middleware, so the ``Origin`` header is checked explicitly against
  ``settings.allowed_origin`` and a mismatch closes ``1008`` before accept.
- **No info leak (T-02-05):** ``terminal.connected`` / ``terminal.disconnected``
  events carry ``{}`` only — no ``lxc_ip``, no terminal content.

Teardown (T-02-04 / SC-10): the two relay directions race under
``asyncio.wait(FIRST_COMPLETED)``; the loser is cancelled and awaited, and the
upstream is dialed with ``ping_interval`` keepalive, so a dead browser leg can
never leave a half-open upstream connection (bounded FD growth).
"""

import asyncio
import os

from fastapi import APIRouter, WebSocket
from websockets import Subprotocol
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from config import settings

from main import get_db

router = APIRouter(prefix="/ws")

# ttyd's default port + path on the worker. Centralized so the production dial has
# exactly one definition (and the SSRF-relevant host is interpolated in one place).
_TTYD_PORT = 7681
_TTYD_PATH = "/ws"

# WS close code for a policy violation (RFC 6455 1008). Used for every pre-accept
# rejection: non-running workspace and Origin mismatch.
_POLICY_VIOLATION = 1008

# E2E-only dial override (NOT for production). When set, the upstream ttyd host is
# this fixed value instead of the workspace's VMID-derived IP, so the Tier-3
# Playwright stack can reach a single local/standalone stub ttyd without a routable
# 10.99.0.x worker network. It is an OPERATOR-controlled env var, never client input,
# so the SSRF posture is unchanged (the access gate still requires a running
# workspace with a resolved IP; this only retargets the reachable test stub). Leave
# it unset in any real deployment.
_E2E_TTYD_HOST_ENV = "BURROW_E2E_TTYD_HOST"


def _ttyd_url(lxc_ip: str) -> str:
    """Build the upstream ttyd URL from the workspace's own IP only (SSRF guard).

    Isolated as a module function so the host is interpolated in exactly one place
    (never from client input) and so the integration tests can redirect the dial at
    a stub server without changing this production construction. The e2e-only
    ``BURROW_E2E_TTYD_HOST`` override (operator env, never client input) retargets the
    host to a single local stub for the Tier-3 stack; absent it, production behavior
    (dial the workspace's own IP) is unchanged.
    """
    host = os.environ.get(_E2E_TTYD_HOST_ENV) or lxc_ip
    return f"ws://{host}:{_TTYD_PORT}{_TTYD_PATH}"


@router.websocket("/workspaces/{workspace_id}/terminal")
async def terminal_proxy(websocket: WebSocket, workspace_id: str) -> None:
    """Bridge the browser terminal to the workspace's ttyd (opaque ``tty`` relay)."""
    db = get_db()

    # ── CSWSH gate (T-02-03): Starlette WS bypasses CORS, so check Origin here. ──
    origin = websocket.headers.get("origin")
    if origin is not None and origin != settings.allowed_origin:
        await websocket.close(code=_POLICY_VIOLATION)
        return

    # ── Access gate (T-02-02) + SSRF source (T-02-01): only a running workspace
    #    with a resolved IP is proxied, and the upstream host comes solely from the
    #    DB row. Close BEFORE accept so a rejected upgrade never dials upstream. ──
    workspace = await db.getWorkspace(workspace_id)
    if workspace is None or workspace.status != "running" or not workspace.lxc_ip:
        await websocket.close(code=_POLICY_VIOLATION)
        return

    await websocket.accept()  # browser leg: do NOT advertise a subprotocol here
    ttyd_url = _ttyd_url(workspace.lxc_ip)

    try:
        async with connect(
            ttyd_url,
            # Negotiate ttyd's protocol on the UPSTREAM leg (TERM-02).
            subprotocols=[Subprotocol("tty")],
            ping_interval=20,
            ping_timeout=20,
        ) as ttyd:
            await db.logEvent(workspace_id, "terminal.connected", {})

            async def pump_up() -> None:
                """browser → ttyd, preserving frame TYPE (A1: init may be a text frame)."""
                while True:
                    message = await websocket.receive()
                    if message["type"] == "websocket.disconnect":
                        return
                    text = message.get("text")
                    if text is not None:
                        await ttyd.send(text)  # str → text frame, verbatim
                    else:
                        await ttyd.send(message["bytes"])  # bytes → binary frame, verbatim

            async def pump_down() -> None:
                """ttyd → browser, preserving frame TYPE — NEVER .encode() (SC-7)."""
                async for frame in ttyd:
                    if isinstance(frame, str):
                        await websocket.send_text(frame)
                    else:
                        await websocket.send_bytes(frame)

            tasks = {asyncio.create_task(pump_up()), asyncio.create_task(pump_down())}
            _done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
    except (ConnectionClosed, OSError):
        # Upstream ttyd unreachable or dropped → typed error frame, then close (TERM-03).
        await _safe_send_error(websocket)
    finally:
        await db.logEvent(workspace_id, "terminal.disconnected", {})
        await _safe_close(websocket)


async def _safe_send_error(websocket: WebSocket) -> None:
    """Emit the typed ``LXC_NOT_READY`` error frame; ignore an already-closed leg."""
    try:
        await websocket.send_json({"type": "error", "code": "LXC_NOT_READY"})
    except (RuntimeError, ConnectionClosed):
        pass


async def _safe_close(websocket: WebSocket) -> None:
    """Close the browser leg, tolerating an already-closed socket."""
    try:
        await websocket.close()
    except (RuntimeError, ConnectionClosed):
        pass
