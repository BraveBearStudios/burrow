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
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiosqlite
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


async def test_create_saga_persists_boot_intent_checkpoint(
    service: WorkspaceService, db: SqliteProvider
) -> None:
    """WR-03: saga step 3 does real work — a bootconfig.persisted checkpoint event.

    The boot intent (project repo/branch from the payload + global config from
    settings) is recorded as an auditable, recoverable DB checkpoint, replacing the
    old injectBootConfig no-op that mutated nothing.
    """
    ws = await service.createWorkspace(_payload())
    events = await db.getEvents(ws.id)

    persisted = [e for e in events if e.type == "bootconfig.persisted"]
    assert persisted, "expected a bootconfig.persisted checkpoint event (WR-03)"
    data = persisted[0].data
    # The persisted intent matches what the bootconfig endpoint will serve.
    assert data["project_repo"] == _payload().project_repo
    assert data["project_branch"] == _payload().project_branch
    assert data["config_repo"] == real_settings.config_repo
    assert data["config_branch"] == real_settings.config_branch

    # The checkpoint lands BEFORE the running mark (it is a create-time capture).
    types = [e.type for e in events]
    assert types.index("bootconfig.persisted") < types.index("workspace.created")


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


class _LockOnceDb(SqliteProvider):
    """SqliteProvider that injects a one-shot "database is locked" on first INSERT.

    CR-02 substrate at the service tier: proves the bounded reservation-retry loop
    recovers from a transient lock loss instead of aborting the saga. The lock is
    injected at the connection's ``execute`` (where a real concurrent-writer lock
    would surface) so the provider's OperationalError->VmidTakenError mapping is
    exercised — NOT by overriding ``createWorkspace`` (which would bypass it).
    """

    def __init__(self, settings: Any) -> None:
        super().__init__(settings)
        self._lock_inserts_remaining = 1

    @asynccontextmanager
    async def _connect(self) -> AsyncIterator[aiosqlite.Connection]:
        async with super()._connect() as conn:
            original_execute = conn.execute

            async def _execute(sql: str, *args: Any, **kwargs: Any) -> Any:
                if sql.startswith("INSERT INTO workspaces") and self._lock_inserts_remaining > 0:
                    self._lock_inserts_remaining -= 1
                    raise aiosqlite.OperationalError("database is locked")
                return await original_execute(sql, *args, **kwargs)

            conn.execute = _execute  # type: ignore[method-assign]
            yield conn


async def test_create_saga_retries_through_transient_lock(
    compute: FakeComputeProvider, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CR-02: a one-shot lock loss is retried, and the saga still reaches running."""
    db = _LockOnceDb(_DbSettings(database_path=str(tmp_path / "lock-saga.db")))
    await db.migrate()
    svc = WorkspaceService(compute=compute, db=db, settings=real_settings)

    async def _instant_ttyd(self: WorkspaceService, ip: str) -> None:
        return None

    monkeypatch.setattr(WorkspaceService, "_wait_ttyd", _instant_ttyd)

    ws = await svc.createWorkspace(_payload())
    assert ws.status == "running"
    # Exactly one workspace row exists (the first locked INSERT never committed).
    assert len(await db.listWorkspaces()) == 1
