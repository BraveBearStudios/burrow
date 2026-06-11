# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""State-machine + lifecycle guard tests (WS-06/07/08/09).

Two layers:

- *Table* level — the server-side transition table is the policy authority for
  which lifecycle mutations are legal. Pins the five legal transitions and the
  illegal ones (stop-on-creating, start-on-destroyed, double-destroy,
  running->start).
- *Service* level — ``stop/start/destroy`` enforce ``assert_transition`` at the
  service boundary over the Fake: legal mutations succeed, set the right
  timestamp, and log a lifecycle event; illegal ones raise
  ``IllegalTransitionError`` before touching a provider.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from compute.fakeProvider import FakeComputeProvider
from db.sqliteProvider import SqliteProvider
from lib.errors import IllegalTransitionError, WorkspaceNotFoundError
from lib.statemachine import TRANSITIONS, assert_transition
from models.workspace import Workspace, WorkspaceCreate
from services.workspaceService import WorkspaceService

from config import settings as real_settings


@pytest.mark.parametrize(
    ("state", "action", "expected"),
    [
        ("running", "stop", "stopped"),
        ("stopped", "start", "running"),
        ("running", "destroy", "destroyed"),
        ("stopped", "destroy", "destroyed"),
        ("error", "destroy", "destroyed"),  # error's only legal exit (A4)
    ],
)
def test_legal_transitions_resolve(state: str, action: str, expected: str) -> None:
    assert assert_transition(state, action) == expected


@pytest.mark.parametrize(
    ("state", "action"),
    [
        ("creating", "stop"),  # WS-09: stop while still booting
        ("destroyed", "start"),  # WS-09: start a destroyed workspace
        ("destroyed", "destroy"),  # WS-09: double-destroy
        ("running", "start"),  # already running
        ("creating", "start"),  # creating is internal-only, never an action target
        ("error", "start"),  # error's only exit is destroy, not retry
        ("error", "stop"),  # ditto
    ],
)
def test_illegal_transitions_raise(state: str, action: str) -> None:
    with pytest.raises(IllegalTransitionError) as exc_info:
        assert_transition(state, action)
    # The raised error carries the offending pair and a stable envelope code.
    assert exc_info.value.code == "illegal_transition"
    assert state in str(exc_info.value)
    assert action in str(exc_info.value)


def test_transitions_table_is_exactly_the_five_legal_pairs() -> None:
    """`creating` is internal-only and `error` exits only via destroy (A4)."""
    assert set(TRANSITIONS) == {
        ("running", "stop"),
        ("stopped", "start"),
        ("running", "destroy"),
        ("stopped", "destroy"),
        ("error", "destroy"),
    }


# ── service-level lifecycle guards (WS-06/07/08/09) ───────────────────────────


@dataclass
class _DbSettings:
    database_path: str


@pytest.fixture
async def db(tmp_path: Path) -> SqliteProvider:
    provider = SqliteProvider(_DbSettings(database_path=str(tmp_path / "lifecycle.db")))
    await provider.migrate()
    return provider


@pytest.fixture
def compute() -> FakeComputeProvider:
    return FakeComputeProvider(node_memory=0.25)


@pytest.fixture
async def service(
    compute: FakeComputeProvider,
    db: SqliteProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[WorkspaceService]:
    async def _instant_ttyd(self: WorkspaceService, ip: str) -> None:
        return None

    monkeypatch.setattr(WorkspaceService, "_wait_ttyd", _instant_ttyd)
    yield WorkspaceService(compute=compute, db=db, settings=real_settings)


async def _running_workspace(service: WorkspaceService) -> Workspace:
    return await service.createWorkspace(
        WorkspaceCreate(name="lc", project_repo="git@example.com:acme/lc.git", node="pve1")
    )


async def test_stop_running_to_stopped(service: WorkspaceService, db: SqliteProvider) -> None:
    ws = await _running_workspace(service)
    stopped = await service.stopWorkspace(ws.id)
    assert stopped.status == "stopped"
    assert stopped.stopped_at is not None
    events = await db.getEvents(ws.id)
    assert any(e.type == "workspace.stopped" for e in events)


async def test_operator_stop_carries_no_reason(
    service: WorkspaceService, db: SqliteProvider
) -> None:
    """An operator-initiated stop emits ``workspace.stopped`` with empty data (Open Q2)."""
    ws = await _running_workspace(service)
    await service.stopWorkspace(ws.id)
    events = await db.getEvents(ws.id)
    stopped = [e for e in events if e.type == "workspace.stopped"]
    assert stopped, "expected a workspace.stopped event"
    # No reason key when the operator stops (the UI badge falls back to "Stopped").
    assert stopped[0].data == {}


async def test_idle_stop_carries_reason_idle(service: WorkspaceService, db: SqliteProvider) -> None:
    """An auto-stop threads ``reason: idle`` into the event data for the UI badge (FROZEN 3)."""
    ws = await _running_workspace(service)
    await service.stopWorkspace(ws.id, reason="idle")
    events = await db.getEvents(ws.id)
    stopped = [e for e in events if e.type == "workspace.stopped"]
    assert stopped, "expected a workspace.stopped event"
    assert stopped[0].data == {"reason": "idle"}


async def test_start_stopped_to_running(service: WorkspaceService, db: SqliteProvider) -> None:
    ws = await _running_workspace(service)
    await service.stopWorkspace(ws.id)
    started = await service.startWorkspace(ws.id)
    assert started.status == "running"
    assert started.lxc_ip is not None
    events = await db.getEvents(ws.id)
    assert any(e.type == "workspace.started" for e in events)


async def test_destroy_running_soft_deletes(
    service: WorkspaceService, db: SqliteProvider, compute: FakeComputeProvider
) -> None:
    ws = await _running_workspace(service)
    assert ws.vmid is not None
    await service.destroyWorkspace(ws.id)
    # Soft-deleted: hidden from active queries, and the CT is gone (vmid freed).
    assert await db.getWorkspace(ws.id) is None
    assert ws.vmid not in await compute.usedVmids()
    # The event row is retained for audit (FK to a soft-deleted row is fine).
    events = await db.getEvents(ws.id)
    assert any(e.type == "workspace.destroyed" for e in events)


async def test_destroy_stopped_workspace(service: WorkspaceService) -> None:
    ws = await _running_workspace(service)
    await service.stopWorkspace(ws.id)
    await service.destroyWorkspace(ws.id)  # legal from stopped
    assert await service.db.getWorkspace(ws.id) is None


async def test_stop_on_creating_raises(service: WorkspaceService, db: SqliteProvider) -> None:
    """WS-09: a still-booting (creating) workspace cannot be stopped."""
    row = await db.createWorkspace(
        {
            "name": "boot",
            "node": "pve1",
            "project_repo": "git@example.com:acme/boot.git",
            "vmid": 250,
            "status": "creating",
        }
    )
    with pytest.raises(IllegalTransitionError):
        await service.stopWorkspace(row.id)


async def test_start_on_destroyed_raises(service: WorkspaceService) -> None:
    """WS-09: a destroyed workspace cannot be started."""
    ws = await _running_workspace(service)
    await service.destroyWorkspace(ws.id)
    with pytest.raises((IllegalTransitionError, WorkspaceNotFoundError)):
        await service.startWorkspace(ws.id)


async def test_double_destroy_raises(service: WorkspaceService) -> None:
    """WS-09: destroying an already-destroyed workspace is illegal."""
    ws = await _running_workspace(service)
    await service.destroyWorkspace(ws.id)
    with pytest.raises((IllegalTransitionError, WorkspaceNotFoundError)):
        await service.destroyWorkspace(ws.id)


async def test_mutating_unknown_workspace_raises_not_found(
    service: WorkspaceService,
) -> None:
    with pytest.raises(WorkspaceNotFoundError):
        await service.stopWorkspace("does-not-exist")


async def test_destroy_reclaims_the_in_flight_lock(service: WorkspaceService) -> None:
    """WR-02: a workspace's lock entry is reclaimed on destroy (bounded _locks).

    Without reclamation, _locks grows monotonically for the process lifetime as
    random-UUID workspaces churn. A stop creates the lock; destroy must pop it so
    the dict does not leak the entry for a now-terminal workspace.
    """
    ws = await _running_workspace(service)
    await service.stopWorkspace(ws.id)
    # The stop created (and now retains) the per-workspace lock.
    assert ws.id in service._locks

    await service.destroyWorkspace(ws.id)
    # Destroy reclaimed it — the terminal workspace's lock is gone.
    assert ws.id not in service._locks


async def test_in_flight_lock_serializes_concurrent_stops(
    service: WorkspaceService,
) -> None:
    """A per-workspace lock means two concurrent stops do not both mutate.

    The first stop wins (running->stopped); the second sees the post-mutation
    state and raises IllegalTransitionError rather than double-firing the provider.
    """
    import asyncio

    ws = await _running_workspace(service)
    results = await asyncio.gather(
        service.stopWorkspace(ws.id),
        service.stopWorkspace(ws.id),
        return_exceptions=True,
    )
    successes = [r for r in results if isinstance(r, Workspace)]
    failures = [r for r in results if isinstance(r, IllegalTransitionError)]
    assert len(successes) == 1
    assert len(failures) == 1
