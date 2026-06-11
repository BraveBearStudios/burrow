# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Deterministic capacity-under-concurrency regression (CAP-02, Pitfall 5).

Two ``createWorkspace`` coroutines race the node-RAM gate. The Fake's
``getNodeMemory`` is derived from the LIVE DB row count, not from ``_containers``
(the clone runs OUTSIDE the create-lock and may not have happened yet): zero
workspaces report just-under threshold, one-or-more report just-over. So once the
first create reserves its ``creating`` row, a capacity read serialized after that
reservation sees the updated state and loses the gate.

The interleaving is made DETERMINISTIC with a two-party barrier inside
``getNodeMemory`` (an ``asyncio.Event`` pair), so the test is a true regression
guard, not a tautology that leans on the scheduler:

- WITHOUT the Task-1 lock, both creates can be *inside* ``getNodeMemory`` at once.
  The first parks on the barrier until the second arrives; the second arrives,
  reads the still-zero row count, and releases the barrier. Both then read zero,
  both pass the gate, and both reserve — the node overcommit bug.
- WITH the lock, the first create holds ``_create_lock`` across its whole
  read+reserve, so the second create is parked on lock acquisition and can never
  enter ``getNodeMemory`` to satisfy the barrier. The first create's barrier wait
  falls through on a short timeout, it reserves a row and releases the lock; the
  second create then enters, reads ONE row, and is refused with ``CapacityError``.

Hermetic: temp SQLite + the Fake, ``_wait_ttyd`` stubbed to a no-op, no real clock
and no Proxmox.
"""

import asyncio
import contextlib
from dataclasses import dataclass
from pathlib import Path

import pytest

from compute.fakeProvider import FakeComputeProvider
from db.provider import DbProvider
from db.sqliteProvider import SqliteProvider
from lib.errors import CapacityError
from models.workspace import Workspace, WorkspaceCreate
from services.workspaceService import WorkspaceService

from config import settings as real_settings

# Sit one workspace apart from the 0.80 capacity_threshold: zero rows is safely
# under, one-or-more rows is safely over, so the gate flips on the FIRST reserve.
_UNDER_THRESHOLD = 0.25
_OVER_THRESHOLD = 0.95

# How long the first create's barrier waits for a second to enter the capacity
# read before falling through. WITHOUT the lock the second arrives near-instantly;
# WITH the lock it never can (it is parked on the lock), so this bounds the wait.
_BARRIER_TIMEOUT_S = 0.5


@dataclass
class _DbSettings:
    database_path: str


class _BarrieredMemoryFake(FakeComputeProvider):
    """Fake whose node memory steps on the live DB count, with a 2-party barrier.

    ``getNodeMemory`` reports below threshold while the DB has zero workspaces and
    above threshold once any row exists — the count reflects the FIRST create's
    reservation (``_containers`` only updates after the post-lock clone). The
    barrier forces a deterministic interleaving: the first reader parks until a
    second reader arrives, which only happens when the create-lock is ABSENT. With
    the lock the second reader is parked on the lock, the barrier times out, and
    the gate flips on the next (serialized) read — proving the lock is what bites.
    """

    def __init__(self, db: DbProvider) -> None:
        super().__init__(node_memory=_UNDER_THRESHOLD)
        self._db = db
        self._first_entered = asyncio.Event()
        self._second_entered = asyncio.Event()

    async def getNodeMemory(self, node: str) -> float:
        rows = await self._db.listWorkspaces()
        if not self._first_entered.is_set():
            # First reader: announce arrival, then wait (bounded) for a second
            # reader. Only an UNSERIALIZED create path lets a second one in here.
            self._first_entered.set()
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._second_entered.wait(), _BARRIER_TIMEOUT_S)
        else:
            # Second reader: release the first. Reached only without the lock.
            self._second_entered.set()
        return _OVER_THRESHOLD if rows else _UNDER_THRESHOLD


@pytest.fixture
async def db(tmp_path: Path) -> SqliteProvider:
    provider = SqliteProvider(_DbSettings(database_path=str(tmp_path / "race.db")))
    await provider.migrate()
    return provider


@pytest.fixture
async def service(
    db: SqliteProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> WorkspaceService:
    async def _instant_ttyd(self: WorkspaceService, ip: str) -> None:
        return None

    # Keep the saga network-free: the integration tier's ttyd poll is stubbed so
    # the race itself (the capacity gate) is what the test exercises.
    monkeypatch.setattr(WorkspaceService, "_wait_ttyd", _instant_ttyd)
    return WorkspaceService(compute=_BarrieredMemoryFake(db), db=db, settings=real_settings)


def _payload(name: str) -> WorkspaceCreate:
    return WorkspaceCreate(
        name=name,
        project_repo=f"git@example.com:acme/{name}.git",
        node="pve1",
    )


async def test_concurrent_creates_cannot_both_overcommit(
    service: WorkspaceService, db: SqliteProvider
) -> None:
    """Exactly one of two concurrent creates passes the capacity gate (CAP-02)."""
    results = await asyncio.gather(
        service.createWorkspace(_payload("alpha")),
        service.createWorkspace(_payload("beta")),
        return_exceptions=True,
    )

    successes = [r for r in results if isinstance(r, Workspace)]
    capacity_errors = [r for r in results if isinstance(r, CapacityError)]

    # The lock serialized check+reserve: one create won the gate, the other saw the
    # reserved row push memory over threshold and was refused. WITHOUT the lock both
    # would be successes (the overcommit bug); this asserts the fix bites.
    assert len(successes) == 1, f"expected exactly one success, got {len(successes)}"
    assert len(capacity_errors) == 1, (
        f"expected exactly one CapacityError, got {len(capacity_errors)}"
    )

    # No overcommit landed: exactly one live workspace exists, and it is running.
    live = await db.listWorkspaces()
    assert len(live) == 1
    assert live[0].status == "running"
