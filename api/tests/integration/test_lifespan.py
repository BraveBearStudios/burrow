# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Lifespan ownership of the reconcile task — clean start + cancel (CAP-02/03).

The FastAPI ``lifespan`` spawns the periodic reconcile loop on startup and cancels
it cleanly on shutdown (Pitfall 4). These tests drive the ``lifespan(app)`` async
context manager DIRECTLY — no live server, no new dependency (``asgi_lifespan`` is
not in the stack; FROZEN guardrail 7) — and assert:

- the reconcile task is created and running while the lifespan is entered, and
- it is cancelled (done, not pending) once the lifespan exits, with no leaked task
  and no ``CancelledError`` surfacing out of shutdown.

The decision logic (reaper + idle) is covered hermetically by ``test_reconciler``;
here ``reconcile_once`` is stubbed and the period is held high so the loop parks on
its ``sleep`` — the test asserts the task LIFECYCLE, not timing.
"""

import asyncio
from pathlib import Path

import pytest

import main
from compute.fakeProvider import FakeComputeProvider
from services.reconciler import Reconciler

from config import settings


@pytest.fixture(autouse=True)
def _fake_compute_singleton(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Use the Fake over a high reconcile period so the loop parks on sleep."""
    monkeypatch.setattr(settings, "compute", "fake", raising=False)
    # A long period means the loop runs at most one pass then parks on sleep — the
    # test exercises start+cancel, not the cadence.
    monkeypatch.setattr(settings, "reconciler_period_s", 3600, raising=False)
    # Isolate the DB the ADR-0015 lifespan store-read touches (getCredentialCiphertext)
    # to a temp file, so it does not hit the default /data path or leave a stray file.
    monkeypatch.setattr(settings, "database_path", str(tmp_path / "lifespan.db"), raising=False)
    main.reset_compute()


async def test_lifespan_starts_and_cancels_the_reconcile_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reconcile task runs inside the lifespan and is cancelled on exit."""
    passes = 0
    started = asyncio.Event()

    async def _counting_once(self: Reconciler) -> None:
        nonlocal passes
        passes += 1
        started.set()

    monkeypatch.setattr(Reconciler, "reconcile_once", _counting_once)

    app = main.create_app()
    before = asyncio.all_tasks()

    async with main.lifespan(app):
        # The loop spawned a task and ran at least one pass, then parked on sleep.
        await asyncio.wait_for(started.wait(), timeout=2.0)
        running = asyncio.all_tasks() - before
        assert len(running) == 1, "exactly one reconcile task should be live"
        (task,) = running
        assert not task.done(), "the reconcile task should be running, not done"

    # After the lifespan exits the task is cancelled — done, not pending, no leak.
    await asyncio.sleep(0)  # let the cancellation settle
    assert task.done(), "the reconcile task must be done after shutdown"
    assert task.cancelled(), "the reconcile task must be cancelled, not errored"
    assert asyncio.all_tasks() - before == set(), "no reconcile task may leak past shutdown"
    assert passes >= 1


async def test_lifespan_uses_the_request_path_compute_singleton(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reconciler is built on the SAME compute singleton the request path uses.

    A reconciler that saw a different (empty) Fake would reap the wrong fleet — so
    the lifespan MUST build from ``get_compute()`` (the process-wide singleton).
    """
    captured: dict[str, object] = {}

    async def _capture_once(self: Reconciler) -> None:
        captured["compute"] = self.compute

    monkeypatch.setattr(Reconciler, "reconcile_once", _capture_once)

    app = main.create_app()
    async with main.lifespan(app):
        for _ in range(100):
            if "compute" in captured:
                break
            await asyncio.sleep(0.01)

    assert captured.get("compute") is main.get_compute()
    assert isinstance(captured["compute"], FakeComputeProvider)


async def test_lifespan_loop_survives_a_failing_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One raising reconcile pass is logged and the loop continues (does not die)."""
    calls = 0

    async def _fail_then_pass(self: Reconciler) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("transient reconcile blip")

    # A near-zero period so the second pass follows quickly after the first raises.
    monkeypatch.setattr(settings, "reconciler_period_s", 0.001, raising=False)
    monkeypatch.setattr(Reconciler, "reconcile_once", _fail_then_pass)

    app = main.create_app()
    before = asyncio.all_tasks()

    async with main.lifespan(app):
        for _ in range(200):
            if calls >= 2:
                break
            await asyncio.sleep(0.01)
        (task,) = asyncio.all_tasks() - before
        # The loop survived the first failing pass and ran again — task still alive.
        assert calls >= 2, "the loop must continue past a failing pass"
        assert not task.done()

    await asyncio.sleep(0)
    assert task.cancelled()
