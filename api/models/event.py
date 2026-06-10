# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Workspace event model (PLAT-09).

Mirrors the ``events`` table (tech-spec §7.1). Append-only audit rows.
"""

from typing import Any

from models.base import CamelModel


class WorkspaceEvent(CamelModel):
    """An append-only workspace event row (tech-spec §7.1)."""

    id: str
    workspace_id: str
    type: str
    data: dict[str, Any]
    created_at: str
