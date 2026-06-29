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

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from compute.fakeProvider import FakeComputeProvider
from compute.provider import (
    ComputeError,
    ComputeProvider,
    SetupAuthError,
    SetupUnreachableError,
)
from compute.proxmoxProvider import ProxmoxComputeProvider
from config import settings
from db.provider import DbProvider
from db.sqliteProvider import SqliteProvider
from lib.credentialResolver import CredentialResolver
from lib.envelope import respond_error
from lib.errors import (
    AdminAuthError,
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
from services.reconciler import Reconciler
from services.workspaceService import WorkspaceService

logger = logging.getLogger("burrow.main")

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
    # Credential-surface admin gate rejection (ADR-0015): 401 with a fixed,
    # oracle-free message (never reveals no-secret-set vs wrong-secret).
    AdminAuthError: 401,
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
    "admin_unauthorized": "Admin authorization required.",
    "compute_error": "The compute backend is unavailable.",
    "service_error": "The request could not be completed.",
    "validation_error": "Request validation failed.",
    # Setup-wizard codes (SETUP-07). Every message is FIXED and token-free: the raw
    # proxmoxer exception string (which can embed auth context / the rejected token)
    # is NEVER interpolated, so the operator-typed token cannot leak through an error.
    "setup_unreachable": "Could not reach the Proxmox host.",
    "setup_auth_failed": "The Proxmox token was rejected.",
    "setup_missing_privileges": "The Proxmox token is missing required privileges.",
    "setup_template_not_found": "The worker template was not found on the target node.",
}

# Setup ComputeError subclass -> (envelope code, HTTP status). A rejected token is a
# 400 (operator-fixable input); an unreachable host is a 502 (upstream gateway down).
# Both emit a FIXED token-free message from ``_SAFE_ERROR_MESSAGES`` — never str(exc).
_SETUP_ERROR_MAP: dict[type[ComputeError], tuple[str, int]] = {
    SetupAuthError: ("setup_auth_failed", 400),
    SetupUnreachableError: ("setup_unreachable", 502),
}


# Process-wide compute singleton. The Fake holds container existence in its own
# memory (PLAT-08), so it MUST be the SAME instance across requests or a workspace
# created by one request is invisible to the next (stop/start/destroy would 502).
# Keyed by the selected kind so a settings change (e.g. tests flipping to ``fake``)
# rebuilds the right impl rather than returning a stale one.
_compute_singleton: ComputeProvider | None = None
_compute_kind: str | None = None

# ADR-0015: the GUI-set Proxmox token (decrypted from the store) as a runtime
# override for the provider's .env token. Set at startup (from the store, if any) and
# on every credential write, paired with reset_compute() so the next build rebinds the
# proxmoxer client to the new token — no restart. None = use the .env value.
_proxmox_token_override: str | None = None


def set_proxmox_token_override(token: str | None) -> None:
    """Set (or clear) the runtime Proxmox-token override (ADR-0015).

    Callers pair this with :func:`reset_compute` so the next :func:`get_compute`
    rebuilds the provider bound to the new token. The plaintext lives only in this
    process holder (as proxmoxer already holds it); it is never logged or persisted.
    """
    global _proxmox_token_override
    _proxmox_token_override = token


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
            _compute_singleton = ProxmoxComputeProvider(
                settings, token_override=_proxmox_token_override
            )
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


def build_reconciler() -> Reconciler:
    """Build the fleet :class:`Reconciler` from the SAME singletons the request path uses.

    The reconciler MUST receive the process-wide ``get_compute()`` instance (the
    Fake holds container state in its own memory, PLAT-08) — a fresh provider would
    see an empty fleet and reap nothing / everything. ``get_db()`` and the
    ``WorkspaceService`` are composed the same way ``get_service`` composes them, so
    the reaper and the idle auto-stop act on exactly the state the routers mutate.
    """
    compute = get_compute()
    db = get_db()
    service = WorkspaceService(compute=compute, db=db, settings=settings)
    return Reconciler(compute=compute, db=db, settings=settings, service=service)


async def _reconcile_loop(reconciler: Reconciler, period_s: float) -> None:
    """Run ``reconcile_once()`` forever on a fixed cadence, surviving a bad pass.

    Each pass is wrapped in a broad ``except`` so one failed reconcile (e.g. a
    transient Proxmox blip in the homelab) is logged and the loop continues —
    a single bad pass must NOT kill the reconciler (RESEARCH Pattern 1 / Pitfall
    4). ``CancelledError`` is NOT caught here: it must propagate so the lifespan's
    ``await task`` unwinds cleanly on shutdown.
    """
    while True:
        try:
            await reconciler.reconcile_once()
        except asyncio.CancelledError:
            raise  # shutdown: let the cancel propagate to the lifespan
        except Exception:
            logger.exception("reconcile pass failed; continuing")
        await asyncio.sleep(period_s)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Own the periodic reconcile task: spawn on startup, cancel cleanly on shutdown.

    Spawns ``_reconcile_loop`` as an asyncio task on uvicorn's loop, built from the
    request-path singletons (``build_reconciler``). On shutdown it cancels the task
    and awaits it, suppressing the resulting ``CancelledError`` so the cancel does
    not dirty the shutdown (Pitfall 4) — no leaked task, no surfaced error.
    """
    # ADR-0015: load a GUI-set Proxmox token from the store into the runtime override
    # BEFORE the first provider build, so a token set via the UI survives a restart.
    # A store-read failure must NOT prevent startup: fall back to the .env token
    # (the override stays None) and log it, rather than crashing the app. A genuinely
    # broken DB surfaces on the first request anyway; this is not the place to die.
    try:
        set_proxmox_token_override(await CredentialResolver(get_db(), settings).proxmox_token())
    except Exception:
        logger.warning("could not load the stored Proxmox token at startup; using the .env fallback")
    reconciler = build_reconciler()
    task = asyncio.create_task(_reconcile_loop(reconciler, settings.reconciler_period_s))
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


def _envelope_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Wrap any uncaught error into the standard error envelope (PLAT-02)."""
    body = respond_error(code="internal_error", message="Internal server error")
    return JSONResponse(status_code=500, content=body)


def _service_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Map a typed :class:`ServiceError` to its deterministic status + envelope.

    The wire ``code`` is the error's stable ``.code``; the message is a safe,
    operator-facing string (never the raw exception text, T-01-14). A per-instance
    ``safe_message`` is preferred when the error carries one (an author-curated
    literal, e.g. the auto no-fit manual-pick hint), else the static
    ``_SAFE_ERROR_MESSAGES`` entry for ``.code`` is used. Raw ``str(exc)`` is NEVER
    surfaced. Unmapped service errors fall back to 400.
    """
    assert isinstance(exc, ServiceError)
    status = _SERVICE_ERROR_STATUS.get(type(exc), 400)
    message = getattr(exc, "safe_message", None) or _SAFE_ERROR_MESSAGES.get(
        exc.code, _SAFE_ERROR_MESSAGES["service_error"]
    )
    return JSONResponse(status_code=status, content=respond_error(code=exc.code, message=message))


def _compute_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Map a compute-seam :class:`ComputeError` to a 502 envelope (no internals)."""
    body = respond_error(code="compute_error", message=_SAFE_ERROR_MESSAGES["compute_error"])
    return JSONResponse(status_code=502, content=body)


def _validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Map a 422 :class:`RequestValidationError` to a leak-free envelope (T-12-04).

    FastAPI's default 422 body echoes the raw submitted ``input`` for each error,
    which would leak a request-body secret (the operator-typed ``SecretStr`` token
    on ``/setup/test-connection``, SETUP-07). This handler re-shapes validation
    errors into the standard error envelope carrying ONLY each error's ``loc``,
    ``msg``, and ``type`` — never the submitted ``input``/``ctx``. So a token sent
    alongside a missing/invalid field can never reach the 422 response.
    """
    assert isinstance(exc, RequestValidationError)
    safe_errors = [
        {"loc": list(err.get("loc", ())), "msg": err.get("msg", ""), "type": err.get("type", "")}
        for err in exc.errors()
    ]
    body = respond_error(code="validation_error", message="Request validation failed.")
    assert isinstance(body["error"], dict)
    body["error"]["details"] = safe_errors
    return JSONResponse(status_code=422, content=body)


def _setup_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Map a setup-validation :class:`ComputeError` to its token-free envelope code.

    The wizard's auth/connect failures (``SetupAuthError``/``SetupUnreachableError``)
    get their OWN ``error.code`` so the Phase 13 UI can differentiate, with a FIXED
    operator-facing message from ``_SAFE_ERROR_MESSAGES``. The raw ``str(exc)`` is
    NEVER surfaced — it can embed the rejected token (SETUP-07). An unmapped setup
    error falls back to the generic compute envelope.
    """
    assert isinstance(exc, ComputeError)
    mapping = _SETUP_ERROR_MAP.get(type(exc))
    if mapping is None:
        return _compute_error_handler(request, exc)
    code, status = mapping
    body = respond_error(code=code, message=_SAFE_ERROR_MESSAGES[code])
    return JSONResponse(status_code=status, content=body)


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
    app = FastAPI(title="Burrow Control Plane", version="0.1.0", lifespan=lifespan)
    app.add_exception_handler(Exception, _envelope_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(ServiceError, _service_error_handler)
    app.add_exception_handler(ComputeError, _compute_error_handler)
    # More-specific setup handlers: a SetupAuthError/SetupUnreachableError gets its
    # own token-free envelope code/status rather than the generic compute_error 502.
    app.add_exception_handler(SetupAuthError, _setup_error_handler)
    app.add_exception_handler(SetupUnreachableError, _setup_error_handler)

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
    from routers import health, internal, nodes, setup, templates, terminal, workspaces

    app.include_router(workspaces.router)
    app.include_router(templates.router)
    app.include_router(health.router)
    app.include_router(internal.router)
    app.include_router(nodes.router)
    app.include_router(setup.router)
    # The terminal bridge lives OUTSIDE /api/v1 by design (CLAUDE.md /ws/* WS
    # convention); its prefix is /ws.
    app.include_router(terminal.router)
    return app


app = create_app()
