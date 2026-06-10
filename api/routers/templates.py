# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Templates router — ``GET /api/v1/templates`` (PLAT-01).

Thin read-only surface: list the seeded golden templates via the DB seam and wrap
them in the standard envelope (camelCase via ``model_dump(by_alias=True)``). No
provider impl, no SQL — the listing lives behind :meth:`DbProvider.listTemplates`.
"""

from fastapi import APIRouter, Depends

from db.provider import DbProvider
from lib.envelope import respond

from main import get_db

router = APIRouter(prefix="/api/v1")


@router.get("/templates")
async def list_templates(db: DbProvider = Depends(get_db)) -> dict[str, object]:
    """Return the seeded golden templates (PLAT-01)."""
    templates = await db.listTemplates()
    return respond([template.model_dump(by_alias=True) for template in templates])
