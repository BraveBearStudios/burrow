# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Template model (PLAT-09).

Mirrors the ``templates`` table (tech-spec §7.1). Maps the golden-template
VMID and its plugin manifest.
"""

from typing import Any

from models.base import CamelModel


class Template(CamelModel):
    """A golden-template row (tech-spec §7.1)."""

    id: str
    name: str
    proxmox_tid: int
    plugin_manifest: dict[str, Any]
    created_at: str
