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
    persistent: bool = False  # WSX-02; stored INTEGER 0/1, Pydantic coerces to bool


class WorkspaceCreate(CamelModel):
    """Request body for creating a workspace.

    ``node`` is OPTIONAL: ``None``/omitted signals AUTO placement (the saga
    selects the least-loaded fitting node via ``WorkspaceService.selectNode``),
    while an explicit node string is the unchanged manual path (WSX-01).
    """

    name: str
    project_repo: str
    project_branch: str = "main"
    plugin_set: str = "default"
    node: str | None = None
    persistent: bool = False  # opt-in; default ephemeral (CONTEXT-locked WSX-02)
