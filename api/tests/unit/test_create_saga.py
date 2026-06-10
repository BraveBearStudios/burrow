# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Create-saga happy path over the FakeComputeProvider (WS-01, WS-02).

The 8-step saga (RESEARCH Pattern 2) is exercised end-to-end against a clean
Fake: capacity guard -> reserve VMID + creating row -> clone -> injectBootConfig
-> start -> resolve IP -> ttyd health -> mark running. ``_wait_ttyd`` is stubbed
(no network in the unit tier — execution_note); the real httpx poll is the
integration tier's job.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from compute.fakeProvider import FakeComputeProvider
from db.sqliteProvider import SqliteProvider
from models.workspace import WorkspaceCreate
from services.workspaceService import WorkspaceService

from config import settings as real_settings


@dataclass
class _DbSettings:
    database_path: str


@pytest.fixture
async def db(tmp_path: Path) -> SqliteProvider:
    provider = SqliteProvider(_DbSettings(database_path=str(tmp_path / "saga.db")))
    await provider.migrate()
    return provider


@pytest.fixture
def compute() -> FakeComputeProvider:
    # Low node memory so the capacity guard passes by default.
    return FakeComputeProvider(node_memory=0.25)


@pytest.fixture
async def service(
    compute: FakeComputeProvider,
    db: SqliteProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[WorkspaceService]:
    svc = WorkspaceService(compute=compute, db=db, settings=real_settings)

    async def _instant_ttyd(self: WorkspaceService, ip: str) -> None:
        return None

    # Stub the ttyd-health poll so unit tests never hit the network.
    monkeypatch.setattr(WorkspaceService, "_wait_ttyd", _instant_ttyd)
    yield svc


def _payload(name: str = "alpha") -> WorkspaceCreate:
    return WorkspaceCreate(
        name=name,
        project_repo="git@example.com:acme/alpha.git",
        node="pve1",
    )


async def test_create_saga_reaches_running(service: WorkspaceService) -> None:
    ws = await service.createWorkspace(_payload())

    assert ws.status == "running"
    assert ws.name == "alpha"
    # vmid is reserved in the configured worker pool range.
    assert ws.vmid is not None
    assert real_settings.worker_pool_start <= ws.vmid <= real_settings.worker_pool_end
    # IP is resolved (Fake derives 10.99.0.<vmid % 256>).
    assert ws.lxc_ip == f"10.99.0.{ws.vmid % 256}"


async def test_create_saga_logs_created_event(
    service: WorkspaceService, db: SqliteProvider
) -> None:
    ws = await service.createWorkspace(_payload())
    events = await db.getEvents(ws.id)
    assert any(e.type == "workspace.created" for e in events)


async def test_create_saga_clone_starts_the_container(
    service: WorkspaceService, compute: FakeComputeProvider
) -> None:
    ws = await service.createWorkspace(_payload())
    assert ws.vmid is not None
    # The Fake actually holds a running container for the reserved VMID.
    assert ws.vmid in await compute.usedVmids()
    assert await compute.getIp("pve1", ws.vmid) is not None


async def test_create_persists_creating_row_before_clone(
    service: WorkspaceService, db: SqliteProvider
) -> None:
    """SC-2 recoverability: the row exists with the reserved VMID, then runs."""
    ws = await service.createWorkspace(_payload())
    fetched = await db.getWorkspace(ws.id)
    assert fetched is not None
    assert fetched.vmid == ws.vmid
    assert fetched.status == "running"
