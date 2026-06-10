# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Standalone, protocol-accurate stub ttyd for the Playwright/Fake e2e stack (T-02-07).

This is the e2e-tier counterpart of the in-process ``stub_ttyd_ws`` pytest fixture
(``tests/integration/conftest.py``). It speaks the SAME ``tty`` protocol from a single
shared handler (:func:`handle_ttyd_connection` / :func:`relay_ttyd_frame`) — there is
no second, weaker implementation to drift, so the SC-7 ``.encode()`` corruption bug
cannot hide in the e2e tier either.

It is **NOT a bare echo**. A bare echo would forward bytes regardless of frame type and
never negotiate a subprotocol, so a proxy that drops the ``tty`` subprotocol or
re-encodes a text frame to bytes (the spec §6.4 SC-7 bug) would still pass. This stub
enforces the real ttyd contract so that regression FAILS the e2e journey:

- it advertises + requires the ``tty`` subprotocol on the upgrade,
- it requires the first frame to be the JSON init (``AuthToken/columns/rows``),
- it echoes INPUT (``'0'`` + data) back as OUTPUT (``'0'`` + data) preserving the
  frame's text-vs-binary TYPE, and silently accepts RESIZE (``'1'`` + JSON).

Run it as a process for the e2e stack (the bridge dials ``ws://{lxc_ip}:7681/ws``; the
Fake derives ``lxc_ip`` as ``10.99.0.<vmid % 256>``, so bind on all interfaces / route
``:7681`` to this server in the compose network)::

    python -m tests.e2e.stub_ttyd_server --host 0.0.0.0 --port 7681

Scrollback note (Pitfall 1/7): this stub keeps NO replay buffer. A reconnect attaches to
a fresh stream — blank-then-live — exactly like a persistent real ttyd in v1.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from collections.abc import Callable
from typing import cast

import websockets
from websockets.asyncio.server import ServerConnection, serve

logger = logging.getLogger("burrow.stub_ttyd")

# ttyd command opcodes (verified against ttyd server.h). Centralized so both the
# standalone server and the integration fixture frame against one definition.
INPUT_OPCODE = "0"
OUTPUT_OPCODE = "0"
RESIZE_OPCODE = "1"

# The first client frame must be the JSON init carrying these keys.
_REQUIRED_INIT_KEYS = frozenset({"AuthToken", "columns", "rows"})

# Type of the optional per-frame hook: called with (was_input_text_frame) after each
# INPUT frame is relayed, so the integration fixture can record whether the relay
# preserved frame type end-to-end (the SC-7 gate).
EchoObserver = Callable[[bool], None]


def require_tty_subprotocol(conn: ServerConnection) -> None:
    """Assert the proxy negotiated the ``tty`` subprotocol (TERM-02 gate)."""
    if conn.subprotocol != "tty":
        raise AssertionError(f"expected 'tty' subprotocol, got {conn.subprotocol!r}")


def parse_init_frame(init: str | bytes) -> dict[str, object]:
    """Parse + validate the ttyd JSON init frame; raise if it is not the init.

    The browser's xterm adapter sends ``{AuthToken, columns, rows}`` as the FIRST
    frame; a proxy that swallows or reorders it would fail here.
    """
    raw = init.decode() if isinstance(init, (bytes, bytearray)) else init
    payload = cast("dict[str, object]", json.loads(raw))
    if not _REQUIRED_INIT_KEYS <= payload.keys():
        raise AssertionError(f"init frame missing keys: {_REQUIRED_INIT_KEYS - payload.keys()}")
    return payload


async def relay_ttyd_frame(
    conn: ServerConnection,
    msg: str | bytes,
    on_echo: EchoObserver | None = None,
) -> None:
    """Handle one post-init frame: echo INPUT as OUTPUT (preserving type), drop RESIZE.

    This is the single load-bearing relay rule shared by every stub-ttyd tier. INPUT
    (``'0'`` + data) is echoed back VERBATIM — same bytes, same text-vs-binary frame
    type — so a relay that re-encodes a text frame to bytes (SC-7) is observable
    downstream. RESIZE (``'1'`` + JSON) is accepted and ignored (no echo).
    """
    is_text = isinstance(msg, str)
    head = msg[:1]
    if head in (INPUT_OPCODE, INPUT_OPCODE.encode()):
        if on_echo is not None:
            on_echo(is_text)
        await conn.send(msg)  # verbatim: '0'-prefixed, same frame type
    # head == RESIZE_OPCODE → accept and ignore (no echo)


async def handle_ttyd_connection(
    conn: ServerConnection,
    on_echo: EchoObserver | None = None,
) -> None:
    """Speak the real ttyd ``tty`` protocol for one upstream connection.

    The shared connection handler used by BOTH the standalone server and the
    integration fixture: negotiate ``tty``, require the JSON init, then relay frames.
    ``on_echo`` (optional) lets the fixture record echoed frame type for the SC-7 gate.
    """
    require_tty_subprotocol(conn)
    init = await conn.recv()
    parse_init_frame(init)
    async for msg in conn:
        await relay_ttyd_frame(conn, msg, on_echo)


async def run_server(host: str, port: int) -> None:
    """Serve the protocol-accurate stub ttyd until cancelled (the process entrypoint)."""
    async with serve(
        handle_ttyd_connection,
        host,
        port,
        subprotocols=[websockets.Subprotocol("tty")],
    ) as server:
        bound = server.sockets[0].getsockname()[:2]
        logger.info("stub ttyd listening on ws://%s:%s", *bound)
        await asyncio.get_running_loop().create_future()  # run forever


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="stub_ttyd_server",
        description="Protocol-accurate stub ttyd for the Burrow Playwright/Fake e2e stack.",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",  # noqa: S104 — e2e-only stub on the test compose network
        help="bind address (default: 0.0.0.0 so the bridge reaches it in the compose net)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7681,
        help="bind port (default: 7681, ttyd's default)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """CLI entrypoint: ``python -m tests.e2e.stub_ttyd_server --host 0.0.0.0 --port 7681``."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = _parse_args(argv)
    try:
        asyncio.run(run_server(args.host, args.port))
    except KeyboardInterrupt:  # pragma: no cover - signal-driven shutdown
        logger.info("stub ttyd shutting down")


if __name__ == "__main__":
    main()
