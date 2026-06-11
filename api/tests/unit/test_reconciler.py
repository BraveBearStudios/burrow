# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Reconciler single-pass tests — reaper + idle auto-stop (CAP-02, CAP-03).

Every reconcile decision is a pure function of (DB state, compute state, an
injected ``now``), so each test drives exactly ONE ``reconcile_once()`` pass over
a clean Fake + a real temp SQLite, with ``now`` set explicitly. No real clock, no
``asyncio.sleep``, no ``freezegun`` (FROZEN guardrail 5 / RESEARCH Don't-Hand-Roll).

Coverage:

- Test 1 (CAP-03): an in-pool orphan CT (no DB row) is destroyed; an out-of-pool
  CT is left untouched (the load-bearing pool-range safety bound, T-04-01A).
- Test 2 (CAP-03): a timed-out ``creating`` row → CT destroyed + status ``error``
  + a ``reaper.timed_out`` event.
- Test 3 (CAP-03, Pitfall 1): a fresh ``creating`` row is NOT swept.
- Test 4 (CAP-02): a running workspace whose last terminal event is a stale
  ``terminal.disconnected`` is stopped via ``stopWorkspace(reason="idle")``; the
  ``workspace.stopped`` event carries ``data.reason == "idle"``.
- Test 5 (CAP-02, Pitfall 2): connect → disconnect → connect within the window
  leaves the last event = connected → NOT stopped.
- Test 6 (security, T-04-01C): a secret-shaped token never appears in any
  ``reaper.*`` event data.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from compute.fakeProvider import FakeComputeProvider, _FakeContainer
from db.sqliteProvider import SqliteProvider
from services.reconciler import Reconciler
from services.workspaceService import WorkspaceService

from config import settings as real_settings

# A token shaped like a GitHub PAT — must never appear in a reaper.* event.
_SECRET = "ghp_supersecrettoken1234567890"


@dataclass
class _DbSettings:
    database_path: str


@pytest.fixture
async def db(tmp_path: Path) -> SqliteProvider:
    provider = SqliteProvider(_DbSettings(database_path=str(tmp_path / "recon.db")))
    await provider.migrate()
    return provider


@pytest.fixture
def compute() -> FakeComputeProvider:
    return FakeComputeProvider(node_memory=0.25)


def _service(compute: FakeComputeProvider, db: SqliteProvider) -> WorkspaceService:
    return WorkspaceService(compute=compute, db=db, settings=real_settings)


def _reconciler(
    compute: FakeComputeProvider,
    db: SqliteProvider,
    now: datetime,
) -> Reconciler:
    return Reconciler(
        compute=compute,
        db=db,
        settings=real_settings,
        service=_service(compute, db),
        now=lambda: now,
    )


def _parse(created_at: str) -> datetime:
    """Parse an ISO-8601 timestamp to a tz-aware UTC datetime (mirrors the reconciler)."""
    dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


async def _creating_row(db: SqliteProvider, name: str, vmid: int) -> str:
    """Insert a `creating` workspace row with the given reserved vmid; return its id."""
    ws = await db.createWorkspace(
        {
            "name": name,
            "node": "pve1",
            "project_repo": "git@example.com:acme/x.git",
            "vmid": vmid,
            "status": "creating",
        }
    )
    return ws.id


async def _running_row(db: SqliteProvider, name: str, vmid: int) -> str:
    """Insert a `running` workspace row with the given vmid; return its id."""
    ws = await db.createWorkspace(
        {
            "name": name,
            "node": "pve1",
            "project_repo": "git@example.com:acme/x.git",
            "vmid": vmid,
            "status": "running",
        }
    )
    return ws.id


# ── Test 1: orphan reap is pool-bounded (CAP-03 / T-04-01A) ───────────────────
async def test_reap_destroys_in_pool_orphan_and_spares_out_of_pool(
    compute: FakeComputeProvider, db: SqliteProvider
) -> None:
    in_pool = real_settings.worker_pool_start + 50  # 250 with the default 200..299
    out_of_pool = real_settings.worker_pool_end + 100  # 399 — outside the pool
    compute._containers[in_pool] = _FakeContainer(vmid=in_pool, name="orphan", node="pve1")
    compute._containers[out_of_pool] = _FakeContainer(
        vmid=out_of_pool, name="not-ours", node="pve1"
    )

    await _reconciler(compute, db, now=datetime.now(timezone.utc)).reconcile_once()

    # In-pool orphan with no DB row → destroyed; out-of-pool CT → untouched.
    assert in_pool not in compute._containers
    assert out_of_pool in compute._containers


async def test_reap_spares_in_pool_ct_with_a_live_row(
    compute: FakeComputeProvider, db: SqliteProvider
) -> None:
    vmid = real_settings.worker_pool_start + 10
    # A running workspace owns this vmid AND the CT exists → not an orphan.
    await _running_row(db, "owned", vmid)
    compute._containers[vmid] = _FakeContainer(vmid=vmid, name="owned", node="pve1", running=True)

    await _reconciler(compute, db, now=datetime.now(timezone.utc)).reconcile_once()

    assert vmid in compute._containers  # a live-owned CT is never reaped


# ── Test 2: timed-out creating row swept to error (CAP-03) ────────────────────
async def test_timed_out_creating_row_is_reaped_to_error(
    compute: FakeComputeProvider, db: SqliteProvider
) -> None:
    vmid = real_settings.worker_pool_start + 51
    ws_id = await _creating_row(db, "stuck", vmid)
    compute._containers[vmid] = _FakeContainer(vmid=vmid, name="stuck", node="pve1")
    row = await db.getWorkspace(ws_id)
    assert row is not None
    # now is well past the creating timeout relative to the row's created_at.
    now = _parse(row.created_at) + timedelta(seconds=real_settings.creating_timeout_s + 60)

    await _reconciler(compute, db, now=now).reconcile_once()

    updated = await db.getWorkspace(ws_id)
    assert updated is not None
    assert updated.status == "error"
    assert vmid not in compute._containers  # the stuck CT was destroyed
    events = await db.getEvents(ws_id)
    assert any(e.type == "reaper.timed_out" for e in events)
    timed_out = next(e for e in events if e.type == "reaper.timed_out")
    assert timed_out.data == {"reason": "creating timeout"}


# ── Test 3: a fresh creating row is NOT swept (Pitfall 1) ─────────────────────
async def test_fresh_creating_row_is_not_swept(
    compute: FakeComputeProvider, db: SqliteProvider
) -> None:
    vmid = real_settings.worker_pool_start + 52
    ws_id = await _creating_row(db, "in-flight", vmid)
    compute._containers[vmid] = _FakeContainer(vmid=vmid, name="in-flight", node="pve1")
    row = await db.getWorkspace(ws_id)
    assert row is not None
    # now is only a few seconds past creation — well within the timeout.
    now = _parse(row.created_at) + timedelta(seconds=5)

    await _reconciler(compute, db, now=now).reconcile_once()

    updated = await db.getWorkspace(ws_id)
    assert updated is not None
    assert updated.status == "creating"  # still in flight, untouched
    assert vmid in compute._containers
    events = await db.getEvents(ws_id)
    assert not any(e.type == "reaper.timed_out" for e in events)


# ── Test 4: idle running workspace is auto-stopped with reason=idle (CAP-02) ──
async def test_idle_running_workspace_is_auto_stopped_with_reason_idle(
    compute: FakeComputeProvider, db: SqliteProvider
) -> None:
    vmid = real_settings.worker_pool_start + 11
    ws_id = await _running_row(db, "idle-ws", vmid)
    compute._containers[vmid] = _FakeContainer(vmid=vmid, name="idle-ws", node="pve1", running=True)
    await db.logEvent(ws_id, "terminal.connected", {})
    await db.logEvent(ws_id, "terminal.disconnected", {})
    events = await db.getEvents(ws_id)
    last_disconnect = next(e for e in reversed(events) if e.type == "terminal.disconnected")
    # now is past the idle window since the last disconnect.
    now = _parse(last_disconnect.created_at) + timedelta(seconds=real_settings.idle_window_s + 60)

    await _reconciler(compute, db, now=now).reconcile_once()

    updated = await db.getWorkspace(ws_id)
    assert updated is not None
    assert updated.status == "stopped"  # the guarded transition ran
    events = await db.getEvents(ws_id)
    stopped = next(e for e in events if e.type == "workspace.stopped")
    assert stopped.data.get("reason") == "idle"


# ── Test 5: connect→disconnect→connect within window is NOT stopped (Pitfall 2) ─
async def test_brief_reconnect_within_window_is_not_auto_stopped(
    compute: FakeComputeProvider, db: SqliteProvider
) -> None:
    vmid = real_settings.worker_pool_start + 12
    ws_id = await _running_row(db, "reconnected", vmid)
    compute._containers[vmid] = _FakeContainer(
        vmid=vmid, name="reconnected", node="pve1", running=True
    )
    # The LAST terminal event is a connect → an active session, not idle.
    await db.logEvent(ws_id, "terminal.connected", {})
    await db.logEvent(ws_id, "terminal.disconnected", {})
    await db.logEvent(ws_id, "terminal.connected", {})
    # now is far past the window, but the last event is `connected`.
    now = datetime.now(timezone.utc) + timedelta(seconds=real_settings.idle_window_s + 99999)

    await _reconciler(compute, db, now=now).reconcile_once()

    updated = await db.getWorkspace(ws_id)
    assert updated is not None
    assert updated.status == "running"  # active session preserved
    events = await db.getEvents(ws_id)
    assert not any(e.type == "workspace.stopped" for e in events)


async def test_never_connected_running_workspace_is_not_auto_stopped(
    compute: FakeComputeProvider, db: SqliteProvider
) -> None:
    vmid = real_settings.worker_pool_start + 13
    ws_id = await _running_row(db, "never-connected", vmid)
    compute._containers[vmid] = _FakeContainer(
        vmid=vmid, name="never-connected", node="pve1", running=True
    )
    # No terminal events at all → never connected → not idle.
    now = datetime.now(timezone.utc) + timedelta(seconds=real_settings.idle_window_s + 99999)

    await _reconciler(compute, db, now=now).reconcile_once()

    updated = await db.getWorkspace(ws_id)
    assert updated is not None
    assert updated.status == "running"


# ── Test 6: reaper.* events never leak a secret (T-04-01C) ────────────────────
async def test_reaper_timed_out_event_carries_no_secret(
    compute: FakeComputeProvider, db: SqliteProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A secret-shaped token never reaches a reaper.* event's data (redaction)."""
    vmid = real_settings.worker_pool_start + 53
    # A workspace whose NAME embeds a secret-looking token — proves no row field
    # bleeds into the reaper event data either.
    ws = await db.createWorkspace(
        {
            "name": f"leak-{_SECRET}",
            "node": "pve1",
            "project_repo": f"https://user:{_SECRET}@example.com/x.git",
            "vmid": vmid,
            "status": "creating",
        }
    )
    compute._containers[vmid] = _FakeContainer(vmid=vmid, name="leak", node="pve1")
    row = await db.getWorkspace(ws.id)
    assert row is not None
    now = _parse(row.created_at) + timedelta(seconds=real_settings.creating_timeout_s + 60)

    await _reconciler(compute, db, now=now).reconcile_once()

    events = await db.getEvents(ws.id)
    reaper_events = [e for e in events if e.type.startswith("reaper.")]
    assert reaper_events
    for event in reaper_events:
        serialized = str(event.data)
        assert _SECRET not in serialized, "secret leaked into a reaper.* event"
        assert "ghp_" not in serialized, "credential prefix leaked into a reaper.* event"
