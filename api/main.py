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
from compute.provider import ComputeError, ComputeProvider
from compute.proxmoxProvider import ProxmoxComputeProvider
from config import settings
from db.provider import DbProvider
from db.sqliteProvider import SqliteProvider
from lib.envelope import respond_error
from lib.errors import (
    CapacityError,
    IllegalTransitionError,
    IllegalVmidError,
    NoFreeVmidError,
    ServiceError,
    WorkspaceBootError,
    WorkspaceNotFoundError,
)
from lib.logging import setup_logging
from lib.middleware import SecurityHeadersMiddleware
from services.workspaceService import WorkspaceService

# Service-tier error type -> HTTP status. The envelope ``error.code`` comes from
# the error's own ``.code`` attribute; this table only fixes the status (PLAT-02).
_SERVICE_ERROR_STATUS: dict[type[ServiceError], int] = {
    IllegalTransitionError: 409,
    CapacityError: 409,
    NoFreeVmidError: 409,
    WorkspaceNotFoundError: 404,
    # Out-of-pool / source-IP-mismatch bootconfig probe → 404 with NO echo of the
    # probed vmid (enumeration resistance, T-01-17). Same wire shape as not_found.
    IllegalVmidError: 404,
    WorkspaceBootError: 502,
}
# Operator-facing fallback messages keyed by code, so a router never echoes an
# internal exception string into the envelope (ASVS V7, T-01-14).
_SAFE_ERROR_MESSAGES: dict[str, str] = {
    "illegal_transition": "The requested action is not allowed in the current state.",
    "capacity_exceeded": "The selected node is over capacity.",
    "no_free_vmid": "No free workspace slot is available.",
    "not_found": "Workspace not found.",
    # Generic message for the out-of-pool bootconfig probe — never echoes the vmid.
    "illegal_vmid": "Not found.",
    "boot_failed": "The workspace failed to boot.",
    "compute_error": "The compute backend is unavailable.",
    "service_error": "The request could not be completed.",
}


# Process-wide compute singleton. The Fake holds container existence in its own
# memory (PLAT-08), so it MUST be the SAME instance across requests or a workspace
# created by one request is invisible to the next (stop/start/destroy would 502).
# Keyed by the selected kind so a settings change (e.g. tests flipping to ``fake``)
# rebuilds the right impl rather than returning a stale one.
_compute_singleton: ComputeProvider | None = None
_compute_kind: str | None = None


def get_compute() -> ComputeProvider:
    """Return the process-wide compute provider selected by ``settings.compute``.

    ``BURROW_COMPUTE=fake`` -> :class:`FakeComputeProvider` (hermetic default);
    anything else -> :class:`ProxmoxComputeProvider`. This is the sole place a
    concrete compute impl is named. The instance is cached for the process so the
    Fake's in-memory container state survives across requests (lifecycle continuity).
    """
    global _compute_singleton, _compute_kind
    if _compute_singleton is None or _compute_kind != settings.compute:
        _compute_kind = settings.compute
        if settings.compute == "fake":
            _compute_singleton = FakeComputeProvider()
        else:
            _compute_singleton = ProxmoxComputeProvider(settings)
    return _compute_singleton


def reset_compute() -> None:
    """Drop the cached compute singleton (test isolation hook).

    The next :func:`get_compute` rebuilds a fresh provider, so a test starts with an
    empty Fake (no leaked containers/VMIDs from a prior test). Not used in prod.
    """
    global _compute_singleton, _compute_kind
    _compute_singleton = None
    _compute_kind = None


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


def _service_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Map a typed :class:`ServiceError` to its deterministic status + envelope.

    The wire ``code`` is the error's stable ``.code``; the message is a safe,
    operator-facing string (never the raw exception text, T-01-14). Unmapped
    service errors fall back to 400.
    """
    assert isinstance(exc, ServiceError)
    status = _SERVICE_ERROR_STATUS.get(type(exc), 400)
    message = _SAFE_ERROR_MESSAGES.get(exc.code, _SAFE_ERROR_MESSAGES["service_error"])
    return JSONResponse(status_code=status, content=respond_error(code=exc.code, message=message))


def _compute_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Map a compute-seam :class:`ComputeError` to a 502 envelope (no internals)."""
    body = respond_error(code="compute_error", message=_SAFE_ERROR_MESSAGES["compute_error"])
    return JSONResponse(status_code=502, content=body)


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
    app.add_exception_handler(ServiceError, _service_error_handler)
    app.add_exception_handler(ComputeError, _compute_error_handler)

    # Inner→outer add order: SecurityHeaders first, CORS last (outermost).
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.allowed_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Deferred import: routers import the DI seams (get_service/get_compute/get_db)
    # from this module, so they are imported here — after those names are defined —
    # to avoid a circular import at module load.
    from routers import health, internal, templates, workspaces

    app.include_router(workspaces.router)
    app.include_router(templates.router)
    app.include_router(health.router)
    app.include_router(internal.router)
    return app


app = create_app()
