# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Health router — degrade-not-500 ``/api/v1/health`` (PLAT-03).

Aggregates the db and compute ``healthcheck()`` behind a ``_safe`` guard so a
single down dependency yields a 200 response with that dependency reported as
``error`` — never a 500 (PLAT-03). The body carries only ``ok``/``error`` per
dependency: no exception text, connection string, or other internal leaks
(T-01-15).
"""

from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends

from compute.provider import ComputeProvider
from db.provider import DbProvider
from lib.envelope import respond

from main import get_compute, get_db

router = APIRouter(prefix="/api/v1")


async def _safe(check: Callable[[], Awaitable[bool]]) -> bool:
    """Run a provider ``healthcheck`` returning ``False`` on any error (no leak)."""
    try:
        return await check()
    except Exception:
        return False


@router.get("/health")
async def health(
    compute: ComputeProvider = Depends(get_compute),
    db: DbProvider = Depends(get_db),
) -> dict[str, object]:
    """Report overall + per-dependency health; degrade to 200, never 500 (PLAT-03)."""
    db_ok = await _safe(db.healthcheck)
    compute_ok = await _safe(compute.healthcheck)
    overall = "ok" if (db_ok and compute_ok) else "degraded"
    return respond(
        {
            "status": overall,
            "db": "ok" if db_ok else "error",
            "compute": "ok" if compute_ok else "error",
        }
    )
