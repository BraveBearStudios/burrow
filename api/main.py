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
:mod:`lib.envelope`. The ``/api/v1`` routers, structured JSON logging (PLAT-04),
security headers + non-``*`` CORS (PLAT-05), and the ``get_service`` DI seam are
wired here in :func:`create_app`.
"""

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from compute.fakeProvider import FakeComputeProvider
from compute.provider import ComputeProvider
from compute.proxmoxProvider import ProxmoxComputeProvider
from config import settings
from db.provider import DbProvider
from db.sqliteProvider import SqliteProvider
from lib.envelope import respond_error
from lib.logging import setup_logging
from lib.middleware import SecurityHeadersMiddleware
from services.workspaceService import WorkspaceService


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


def get_service(
    compute: ComputeProvider = Depends(get_compute),
    db: DbProvider = Depends(get_db),
) -> WorkspaceService:
    """Compose the :class:`WorkspaceService` from the provider factories (Pattern 5).

    Routers depend on this rather than on a provider impl: ``get_service`` is the
    single DI seam that hands the orchestration core its two ABCs plus
    ``settings``. The service never names a concrete provider (seam discipline).
    """
    return WorkspaceService(compute=compute, db=db, settings=settings)


def _envelope_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Wrap any uncaught error into the standard error envelope (PLAT-02)."""
    body = respond_error(code="internal_error", message="Internal server error")
    return JSONResponse(status_code=500, content=body)


def create_app() -> FastAPI:
    """Build and configure the Burrow control-plane FastAPI app.

    Installs structured JSON logging (PLAT-04), registers the envelope error
    boundary (PLAT-02), and adds the security-headers + non-``*`` CORS middleware
    (PLAT-05). Middleware add-order is inner→outer, so :class:`SecurityHeadersMiddleware`
    is added FIRST and ``CORSMiddleware`` LAST, making CORS the outermost layer that
    handles preflight + error responses (RESEARCH Pattern 7). CORS is restricted to
    ``settings.allowed_origin`` (a non-``*`` LAN origin; a wildcard origin is
    incompatible with credentials, Pitfall 12). v1 is LAN-only no-auth by design — no
    auth is added here.
    """
    setup_logging()
    app = FastAPI(title="Burrow Control Plane", version="0.1.0")
    app.add_exception_handler(Exception, _envelope_exception_handler)

    # Inner→outer add order: SecurityHeaders first, CORS last (outermost).
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.allowed_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app


app = create_app()
