# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Template model (PLAT-09).

Mirrors the ``templates`` table (tech-spec §7.1). Maps the golden-template
VMID and its plugin manifest.
"""

import json
from typing import Any

from pydantic import field_validator

from models.base import CamelModel


class Template(CamelModel):
    """A golden-template row (tech-spec §7.1)."""

    id: str
    name: str
    proxmox_tid: int
    plugin_manifest: dict[str, Any]
    created_at: str

    @field_validator("plugin_manifest", mode="before")
    @classmethod
    def _decode_plugin_manifest(cls, value: Any) -> Any:
        """Parse the column's TEXT JSON into a dict on the read path.

        ``001_init.sql`` stores ``pluginManifest`` as a TEXT JSON blob, so a row
        read (``Template.model_validate(dict(row))``) hands this field a ``str``.
        Decode it here so the round-trip yields the declared ``dict`` instead of
        raising a ValidationError; a dict input passes through unchanged.
        """
        if isinstance(value, str):
            return json.loads(value)
        return value
