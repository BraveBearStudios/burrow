# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Workspace event model (PLAT-09).

Mirrors the ``events`` table (tech-spec §7.1). Append-only audit rows.
"""

import json
from typing import Any

from pydantic import field_validator

from models.base import CamelModel


class WorkspaceEvent(CamelModel):
    """An append-only workspace event row (tech-spec §7.1)."""

    id: str
    workspace_id: str
    type: str
    data: dict[str, Any]
    created_at: str

    @field_validator("data", mode="before")
    @classmethod
    def _decode_data(cls, value: Any) -> Any:
        """Parse the column's TEXT JSON into a dict on the read path.

        ``001_init.sql`` stores ``data`` as a TEXT JSON blob (``logEvent`` writes
        ``json.dumps(data)``), so a row read hands this field a ``str``. Decode it
        here so the round-trip yields the declared ``dict`` instead of raising a
        ValidationError; a dict input passes through unchanged.
        """
        if isinstance(value, str):
            return json.loads(value)
        return value
