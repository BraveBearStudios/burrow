# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Workspace models (PLAT-09).

Mirror the ``workspaces`` table (tech-spec §7.1). Fields are snake_case in
Python and serialize to camelCase JSON via :class:`CamelModel`.
"""

from typing import Literal

from models.base import CamelModel

WorkspaceStatus = Literal["creating", "running", "stopped", "error", "destroyed"]


class Workspace(CamelModel):
    """A worker workspace row (tech-spec §7.1)."""

    id: str
    name: str
    status: WorkspaceStatus
    vmid: int | None
    node: str
    lxc_ip: str | None
    project_repo: str
    project_branch: str
    plugin_set: str
    created_at: str
    stopped_at: str | None
    destroyed_at: str | None
    deleted_at: str | None


class WorkspaceCreate(CamelModel):
    """Request body for creating a workspace."""

    name: str
    project_repo: str
    project_branch: str = "main"
    plugin_set: str = "default"
    node: str
