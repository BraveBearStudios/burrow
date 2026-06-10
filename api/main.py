# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""FastAPI application factory + provider dependency injection.

``main.py`` is the ONE place concrete providers are named. :func:`get_compute`
and :func:`get_db` branch on ``settings`` (``BURROW_COMPUTE`` / ``BURROW_DB``) to
pick an impl, so swapping a backend is an env change, never a service edit. No
other module imports a concrete provider — services depend on the ABCs and take
these functions as FastAPI ``Depends`` targets (wired when routers land in
Phase 1).

The envelope contract (PLAT-02) is enforced at the ASGI boundary: an exception
handler wraps any uncaught error into the ``{data, meta, error}`` shape from
:mod:`lib.envelope`. Success-wrapping middleware is deferred to Phase 1 with the
routers; this phase only needs the error boundary and the factory.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from compute.fakeProvider import FakeComputeProvider
from compute.provider import ComputeProvider
from compute.proxmoxProvider import ProxmoxComputeProvider
from config import settings
from db.provider import DbProvider
from db.sqliteProvider import SqliteProvider
from lib.envelope import respond_error


def get_compute() -> ComputeProvider:
    """Return the compute provider selected by ``settings.compute``.

    ``BURROW_COMPUTE=fake`` -> :class:`FakeComputeProvider` (hermetic default);
    anything else -> :class:`ProxmoxComputeProvider`. This is the sole place a
    concrete compute impl is named.
    """
    if settings.compute == "fake":
        return FakeComputeProvider()
    return ProxmoxComputeProvider(settings)


def get_db() -> DbProvider:
    """Return the persistence provider selected by ``settings.db_kind``.

    v1 ships SQLite only; the Postgres path is additive (stub behind the ABC) and
    is not wired here. This is the sole place a concrete db impl is named.
    """
    return SqliteProvider(settings)


def _envelope_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Wrap any uncaught error into the standard error envelope (PLAT-02)."""
    body = respond_error(code="internal_error", message="Internal server error")
    return JSONResponse(status_code=500, content=body)


def create_app() -> FastAPI:
    """Build and configure the Burrow control-plane FastAPI app.

    Registers the envelope error boundary. Routers (Phase 1) are added here; this
    phase ships the factory + DI seam so the rest of the app builds against a
    stable shape.
    """
    app = FastAPI(title="Burrow Control Plane", version="0.1.0")
    app.add_exception_handler(Exception, _envelope_exception_handler)
    return app


app = create_app()
