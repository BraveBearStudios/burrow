# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Create-saga compensation tests (WS-03, SC-11).

A forced failure at any post-reservation saga step must:

1. Compensate — idempotent stop+destroy tears down the partial clone, freeing the
   VMID (the Fake holds zero leftover containers afterward; no orphan, T-01-10).
2. Land the row in ``error`` — NEVER stuck ``creating`` (Pitfall 4).
3. Log a redacted ``boot.error`` event — no secret/credential string in ``data``
   (T-01-09 / ASVS V7).
4. Re-raise so the caller (router) sees the failure.

Failures are injected with the Fake's ``FakeFailures(raise_on_nth_call=...)`` hook
at clone / start / getIp, plus a stubbed ``_wait_ttyd`` raise for the ttyd-health
step (step 6 does not call the Fake, so it cannot be injected there).
"""

from dataclasses import dataclass
from pathlib import Path

import pytest

from compute.fakeProvider import FakeComputeProvider, FakeFailures
from db.sqliteProvider import SqliteProvider
from lib.errors import WorkspaceBootError
from models.workspace import WorkspaceCreate
from services.workspaceService import WorkspaceService

from config import settings as real_settings

# A token that must never appear in any logged event data.
_SECRET = "ghp_supersecrettoken1234567890"


@dataclass
class _DbSettings:
    database_path: str


@pytest.fixture
async def db(tmp_path: Path) -> SqliteProvider:
    provider = SqliteProvider(_DbSettings(database_path=str(tmp_path / "comp.db")))
    await provider.migrate()
    return provider


def _payload(name: str = "comp") -> WorkspaceCreate:
    return WorkspaceCreate(
        name=name,
        project_repo="git@example.com:acme/comp.git",
        node="pve1",
    )


async def _assert_compensated(
    service: WorkspaceService,
    compute: FakeComputeProvider,
    db: SqliteProvider,
) -> None:
    """Drive a failing create and assert the row landed in error with no orphan."""
    with pytest.raises(Exception):  # noqa: B017 - any saga failure must propagate
        await service.createWorkspace(_payload())

    rows = await db.listWorkspaces()
    assert len(rows) == 1
    row = rows[0]
    # 2 — row in error, never stuck creating.
    assert row.status == "error"
    # 1 — VMID freed: the Fake holds no leftover container.
    assert await compute.usedVmids() == set()
    # 3 — a redacted boot.error event exists.
    events = await db.getEvents(row.id)
    boot_errors = [e for e in events if e.type == "boot.error"]
    assert boot_errors, "expected a boot.error event after compensation"


def _make_service(compute: FakeComputeProvider, db: SqliteProvider) -> WorkspaceService:
    return WorkspaceService(compute=compute, db=db, settings=real_settings)


async def test_compensation_on_clone_failure(db: SqliteProvider) -> None:
    compute = FakeComputeProvider(failures=FakeFailures({"cloneCt": 1}))
    service = _make_service(compute, db)
    await _assert_compensated(service, compute, db)


async def test_compensation_on_start_failure(db: SqliteProvider) -> None:
    compute = FakeComputeProvider(failures=FakeFailures({"startCt": 1}))
    service = _make_service(compute, db)
    await _assert_compensated(service, compute, db)


async def test_compensation_on_getip_failure(db: SqliteProvider) -> None:
    compute = FakeComputeProvider(failures=FakeFailures({"getIp": 1}))
    service = _make_service(compute, db)
    await _assert_compensated(service, compute, db)


async def test_compensation_on_ttyd_failure(
    db: SqliteProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Step 6 (ttyd health) does not call the Fake; force it to raise directly.
    compute = FakeComputeProvider()
    service = _make_service(compute, db)

    async def _ttyd_fails(self: WorkspaceService, ip: str) -> None:
        raise WorkspaceBootError("ttyd not ready")

    monkeypatch.setattr(WorkspaceService, "_wait_ttyd", _ttyd_fails)
    await _assert_compensated(service, compute, db)


async def test_boot_error_event_carries_no_secret(
    db: SqliteProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T-01-09: the redacted boot.error event must not leak a credential."""
    compute = FakeComputeProvider()
    service = _make_service(compute, db)

    async def _ttyd_fails_with_secret(self: WorkspaceService, ip: str) -> None:
        # An exception whose text embeds a secret-looking token.
        raise WorkspaceBootError(f"boot failed using token {_SECRET}")

    monkeypatch.setattr(WorkspaceService, "_wait_ttyd", _ttyd_fails_with_secret)

    with pytest.raises(WorkspaceBootError):
        await service.createWorkspace(_payload())

    rows = await db.listWorkspaces()
    assert len(rows) == 1
    events = await db.getEvents(rows[0].id)
    boot_errors = [e for e in events if e.type == "boot.error"]
    assert boot_errors
    for event in boot_errors:
        serialized = str(event.data)
        assert _SECRET not in serialized, "secret leaked into boot.error event data"
        assert "ghp_" not in serialized, "credential prefix leaked into event data"


async def test_failed_create_does_not_leave_stuck_creating_row(
    db: SqliteProvider,
) -> None:
    """Pitfall 4: no row may remain in `creating` after a failed saga."""
    compute = FakeComputeProvider(failures=FakeFailures({"startCt": 1}))
    service = _make_service(compute, db)

    with pytest.raises(Exception):  # noqa: B017
        await service.createWorkspace(_payload())

    assert await db.listWorkspaces(status="creating") == []
