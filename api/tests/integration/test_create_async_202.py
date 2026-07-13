# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Async-202 create contract (UX-01, ADR-0017).

The create endpoint returns ``202`` + a ``creating`` row IMMEDIATELY and runs the
boot saga in a tracked background task, so a slow real boot never ``504``s. These
tests drive the real app over temp SQLite + the Fake compute provider (the
``integration_client`` fixture) and prove:

- ``POST /workspaces`` returns ``202`` + ``creating`` WITHOUT waiting for the boot:
  the ttyd-health step is gated on a test-controlled ``asyncio.Event`` (a synchronous
  create would hang there), then released so the tracked task drives the row to
  ``running``;
- a failing boot still drives the row to ``error`` on the background path (the saga's
  compensation fires even after the client received the ``202`` and moved on);
- the lifespan cancels + drains an in-flight create task on shutdown (no leak).
"""

import asyncio
from pathlib import Path
from typing import Any

import httpx
import pytest

import main
from lib.errors import WorkspaceBootError
from services.workspaceService import WorkspaceService

from config import settings

from tests.integration.conftest import await_workspace_status

_CREATE_BODY = {
    "name": "async202",
    "projectRepo": "git@example.com:acme/async202.git",
    "projectBranch": "main",
    "node": "pve1",
}


async def test_create_returns_202_creating_without_waiting_for_boot(
    integration_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST returns 202 + creating while the boot is blocked; release then drives running."""
    release = asyncio.Event()

    async def _blocked_ttyd(self: WorkspaceService, ip: str | None) -> None:
        # Park the boot saga at the ttyd-health step until the test releases it. A
        # SYNCHRONOUS create would hang here and the POST below would never return.
        await release.wait()

    monkeypatch.setattr(WorkspaceService, "_wait_ttyd", _blocked_ttyd)

    response = await integration_client.post("/api/v1/workspaces", json=_CREATE_BODY)
    # The 202 arrives even though the boot's ttyd wait is still parked (proves async).
    assert response.status_code == 202, response.text
    creating = response.json()["data"]
    assert creating["status"] == "creating"
    assert creating["vmid"] is not None

    # The boot is still parked, so a re-read shows the row is STILL creating.
    still = (await integration_client.get(f"/api/v1/workspaces/{creating['id']}")).json()["data"]
    assert still["status"] == "creating"

    # Release the gate; the tracked background task now finishes the saga to running.
    release.set()
    running = await await_workspace_status(integration_client, creating["id"], "running")
    assert running["status"] == "running"


async def test_failing_boot_drives_the_row_to_error(
    integration_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing background boot still compensates the row to ``error`` (SC-11, ADR-0017)."""

    async def _ttyd_fails(self: WorkspaceService, ip: str | None) -> None:
        raise WorkspaceBootError("ttyd never came up")

    monkeypatch.setattr(WorkspaceService, "_wait_ttyd", _ttyd_fails)

    response = await integration_client.post("/api/v1/workspaces", json=_CREATE_BODY)
    assert response.status_code == 202, response.text
    creating = response.json()["data"]
    assert creating["status"] == "creating"

    # Even though the client already received the 202, the background saga's
    # compensation lands the row in error — never stuck creating.
    errored = await await_workspace_status(integration_client, creating["id"], "error")
    assert errored["status"] == "error"


async def test_shutdown_cancels_an_in_flight_create_task(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The lifespan cancels + drains an in-flight create boot-saga task on shutdown."""
    # Mirror the lifespan-test fixture: Fake compute, a high reconcile period so that
    # loop parks on sleep, and an isolated temp DB for the ADR-0015 startup store-read.
    monkeypatch.setattr(settings, "compute", "fake", raising=False)
    monkeypatch.setattr(settings, "reconciler_period_s", 3600, raising=False)
    monkeypatch.setattr(
        settings, "database_path", str(tmp_path / "async202-shutdown.db"), raising=False
    )
    main.reset_compute()

    started = asyncio.Event()

    async def _never_completes() -> None:
        # Stand in for a slow boot saga: block until cancelled by shutdown.
        started.set()
        await asyncio.Event().wait()

    before: set[asyncio.Task[Any]] = set(main._create_tasks)
    app = main.create_app()
    async with main.lifespan(app):
        main.schedule_create_task(_never_completes())
        await asyncio.wait_for(started.wait(), timeout=2.0)
        new_tasks = main._create_tasks - before
        assert len(new_tasks) == 1, "the create task should be tracked in the registry"
        (create_task,) = new_tasks
        assert not create_task.done(), "the create task should be in flight"

    # After shutdown the in-flight create task is cancelled and dropped from the
    # registry — no create leaks past shutdown.
    await asyncio.sleep(0)  # let the cancellation settle
    assert create_task.cancelled(), "the in-flight create task must be cancelled"
    assert create_task not in main._create_tasks, "a cancelled create task must not leak"
