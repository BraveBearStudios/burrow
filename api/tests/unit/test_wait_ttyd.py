# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""``_wait_ttyd`` transport-error handling (step-6 boot-error honesty).

Regression for the boot-failure error-honesty gap: the ttyd-readiness poll must
retry EVERY transport-level failure — not just connect/timeout — so a worker that
accepts the TCP handshake on :7681 then resets or half-serves before valid HTTP
(``ReadError``/``WriteError``/``RemoteProtocolError``) is converted to an honest
``WorkspaceBootError`` (mapped to 502 ``boot_failed``) rather than escaping raw and
surfacing to the operator as a generic 500 that masks the boot failure.

Failing-first: with the pre-fix ``except (httpx.ConnectError, httpx.TimeoutException)``
the ``ReadError``/``RemoteProtocolError`` cases escape ``_wait_ttyd`` unhandled and
these tests raise the raw ``httpx`` error instead of ``WorkspaceBootError``.
"""

from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest

from compute.fakeProvider import FakeComputeProvider
from db.sqliteProvider import SqliteProvider
from lib.errors import WorkspaceBootError
from services.workspaceService import WorkspaceService

from config import settings as real_settings


@dataclass
class _DbSettings:
    database_path: str


@pytest.fixture
async def service(tmp_path: Path) -> WorkspaceService:
    db = SqliteProvider(_DbSettings(database_path=str(tmp_path / "wait-ttyd.db")))
    await db.migrate()
    # _wait_ttyd only reads self.settings / self.compute is unused here.
    return WorkspaceService(compute=FakeComputeProvider(), db=db, settings=real_settings)


@pytest.mark.parametrize(
    "transport_error",
    [
        pytest.param(httpx.ConnectError("connection refused"), id="connect-refused"),
        pytest.param(httpx.ReadTimeout("read timed out"), id="read-timeout"),
        pytest.param(httpx.ReadError("connection reset mid-boot"), id="read-reset"),
        pytest.param(
            httpx.RemoteProtocolError("server disconnected before valid HTTP"),
            id="remote-protocol",
        ),
        pytest.param(httpx.WriteError("write failed"), id="write-error"),
    ],
)
async def test_wait_ttyd_wraps_transport_errors_as_boot_error(
    service: WorkspaceService,
    monkeypatch: pytest.MonkeyPatch,
    transport_error: httpx.TransportError,
) -> None:
    """Every ``httpx.TransportError`` from the poll must retry then raise ``WorkspaceBootError``.

    The pre-fix narrow catch let ``ReadError``/``WriteError``/``RemoteProtocolError``
    escape as a raw ``httpx`` error (generic 500); the honest contract is a
    ``WorkspaceBootError`` -> 502 ``boot_failed`` for any transport failure.
    """
    # Tiny deadline so the retry loop exits fast; no real sleeping between polls.
    monkeypatch.setattr(service.settings, "ttyd_timeout", 0.01)
    monkeypatch.setattr(service.settings, "ttyd_interval", 0.0)

    async def _always_raise(self: httpx.AsyncClient, *args: object, **kwargs: object) -> object:
        raise transport_error

    monkeypatch.setattr(httpx.AsyncClient, "get", _always_raise)

    with pytest.raises(WorkspaceBootError):
        await service._wait_ttyd("10.0.0.201")
