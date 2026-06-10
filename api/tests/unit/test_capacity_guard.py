# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Capacity guard tests (CAP-01, CAP-04).

Create is refused when the operator-selected node's used-memory fraction exceeds
the configured threshold (0.80). The refusal happens at step 0, BEFORE any row is
persisted or VMID reserved, so a refused create leaves no trace. CAP-04: the node
queried is exactly ``payload.node`` (operator selection is honored).
"""

from dataclasses import dataclass
from pathlib import Path

import pytest

from compute.fakeProvider import FakeComputeProvider
from db.sqliteProvider import SqliteProvider
from lib.errors import CapacityError
from models.workspace import WorkspaceCreate
from services.workspaceService import WorkspaceService

from config import settings as real_settings


@dataclass
class _DbSettings:
    database_path: str


@pytest.fixture
async def db(tmp_path: Path) -> SqliteProvider:
    provider = SqliteProvider(_DbSettings(database_path=str(tmp_path / "cap.db")))
    await provider.migrate()
    return provider


def _payload(node: str = "pve1") -> WorkspaceCreate:
    return WorkspaceCreate(
        name="cap",
        project_repo="git@example.com:acme/cap.git",
        node=node,
    )


async def test_create_refused_when_node_over_threshold(db: SqliteProvider) -> None:
    # Fake reports 0.90 used memory > 0.80 threshold.
    compute = FakeComputeProvider(node_memory=0.90)
    service = WorkspaceService(compute=compute, db=db, settings=real_settings)

    with pytest.raises(CapacityError):
        await service.createWorkspace(_payload())

    # No row was created — the guard fired before reservation (step 0).
    assert await db.listWorkspaces() == []


async def test_capacity_refusal_creates_no_vmid_reservation(db: SqliteProvider) -> None:
    compute = FakeComputeProvider(node_memory=0.95)
    service = WorkspaceService(compute=compute, db=db, settings=real_settings)

    with pytest.raises(CapacityError):
        await service.createWorkspace(_payload())

    # The Fake never cloned anything, so no VMID is held.
    assert await compute.usedVmids() == set()


async def test_capacity_guard_queries_the_operator_selected_node(
    db: SqliteProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CAP-04: the node passed to getNodeMemory is exactly payload.node."""
    compute = FakeComputeProvider(node_memory=0.90)
    queried: list[str] = []

    original = compute.getNodeMemory

    async def _spy(node: str) -> float:
        queried.append(node)
        return await original(node)

    monkeypatch.setattr(compute, "getNodeMemory", _spy)
    service = WorkspaceService(compute=compute, db=db, settings=real_settings)

    with pytest.raises(CapacityError):
        await service.createWorkspace(_payload(node="pve-chosen"))

    assert queried == ["pve-chosen"]


async def test_create_allowed_at_exactly_threshold(
    db: SqliteProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard refuses only when strictly ABOVE the threshold (> 0.80)."""
    compute = FakeComputeProvider(node_memory=real_settings.capacity_threshold)
    service = WorkspaceService(compute=compute, db=db, settings=real_settings)

    async def _instant_ttyd(self: WorkspaceService, ip: str) -> None:
        return None

    monkeypatch.setattr(WorkspaceService, "_wait_ttyd", _instant_ttyd)

    ws = await service.createWorkspace(_payload())
    assert ws.status == "running"
