# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Workspaces router — ``/api/v1/workspaces`` CRUD + lifecycle (WS-01/04/05/06/07/08/11).

Thin surface over :class:`services.workspaceService.WorkspaceService` (mutations)
and :class:`db.provider.DbProvider` (reads). Every handler validates input
(Pydantic), calls the service or the DB seam, and wraps the result in the standard
envelope with ``model_dump(by_alias=True)`` so JSON stays camelCase (PLAT-09). No
orchestration, no provider impl, no SQL lives here (Architectural Responsibility
Map); typed service errors are mapped to envelope codes by the ``main.py`` handler.
"""

from fastapi import APIRouter, Depends

from db.provider import DbProvider
from lib.envelope import respond
from lib.errors import WorkspaceNotFoundError
from models.workspace import Workspace, WorkspaceCreate
from services.workspaceService import WorkspaceService

from main import get_db, get_service

router = APIRouter(prefix="/api/v1")


@router.post("/workspaces")
async def create_workspace(
    payload: WorkspaceCreate,
    service: WorkspaceService = Depends(get_service),
) -> dict[str, object]:
    """Create a workspace and run the create saga to ``running`` (WS-01)."""
    workspace = await service.createWorkspace(payload)
    return respond(workspace.model_dump(by_alias=True))


@router.get("/workspaces")
async def list_workspaces(
    status: str | None = None,
    db: DbProvider = Depends(get_db),
) -> dict[str, object]:
    """List workspaces, optionally filtered by ``status`` (WS-04)."""
    workspaces = await db.listWorkspaces(status)
    return respond([ws.model_dump(by_alias=True) for ws in workspaces])


@router.get("/workspaces/{workspace_id}")
async def get_workspace(
    workspace_id: str,
    db: DbProvider = Depends(get_db),
) -> dict[str, object]:
    """Fetch a single workspace by id, or 404 envelope if absent (WS-05)."""
    workspace = await db.getWorkspace(workspace_id)
    if workspace is None:
        raise WorkspaceNotFoundError(workspace_id)
    return respond(workspace.model_dump(by_alias=True))


@router.post("/workspaces/{workspace_id}/stop")
async def stop_workspace(
    workspace_id: str,
    service: WorkspaceService = Depends(get_service),
) -> dict[str, object]:
    """Stop a running workspace; state preserved (WS-06)."""
    workspace = await service.stopWorkspace(workspace_id)
    return respond(workspace.model_dump(by_alias=True))


@router.post("/workspaces/{workspace_id}/start")
async def start_workspace(
    workspace_id: str,
    service: WorkspaceService = Depends(get_service),
) -> dict[str, object]:
    """Start a stopped workspace and await ttyd health (WS-07)."""
    workspace = await service.startWorkspace(workspace_id)
    return respond(workspace.model_dump(by_alias=True))


@router.delete("/workspaces/{workspace_id}")
async def destroy_workspace(
    workspace_id: str,
    service: WorkspaceService = Depends(get_service),
) -> dict[str, object]:
    """Destroy a workspace (stop+destroy CT, soft-delete row) (WS-08)."""
    await service.destroyWorkspace(workspace_id)
    return respond({"id": workspace_id, "status": "destroyed"})


@router.get("/workspaces/{workspace_id}/events")
async def list_workspace_events(
    workspace_id: str,
    db: DbProvider = Depends(get_db),
) -> dict[str, object]:
    """Return a workspace's event log oldest-first (WS-11)."""
    workspace: Workspace | None = await db.getWorkspace(workspace_id)
    if workspace is None:
        raise WorkspaceNotFoundError(workspace_id)
    events = await db.getEvents(workspace_id)
    return respond([event.model_dump(by_alias=True) for event in events])
