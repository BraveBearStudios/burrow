# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""SqliteProvider contract tests (PLAT-06).

``001_init.sql`` applies to a temp DB (the ``sqlite_db`` fixture migrates it);
create -> get round-trips, ``listWorkspaces`` filters by status, ``softDelete``
hides the row, ``logEvent`` appends, and ``healthcheck`` is True. No aiosqlite
type or raw row crosses the seam — every method returns a Pydantic model.
"""

from db.sqliteProvider import SqliteProvider
from models.workspace import Workspace


def _ws_data(name: str, node: str = "pve1") -> dict[str, object]:
    return {
        "name": name,
        "node": node,
        "project_repo": f"git@example.com:acme/{name}.git",
    }


async def test_create_and_get_round_trips(sqlite_db: SqliteProvider) -> None:
    created = await sqlite_db.createWorkspace(_ws_data("alpha"))
    assert isinstance(created, Workspace)
    assert created.name == "alpha"
    assert created.status == "creating"  # default
    assert created.project_repo == "git@example.com:acme/alpha.git"
    assert created.project_branch == "main"  # default
    assert created.id

    fetched = await sqlite_db.getWorkspace(created.id)
    assert fetched is not None
    assert fetched == created


async def test_get_missing_returns_none(sqlite_db: SqliteProvider) -> None:
    assert await sqlite_db.getWorkspace("does-not-exist") is None


async def test_list_filters_by_status(sqlite_db: SqliteProvider) -> None:
    a = await sqlite_db.createWorkspace(_ws_data("a"))
    b = await sqlite_db.createWorkspace(_ws_data("b"))
    await sqlite_db.updateWorkspace(b.id, {"status": "running"})

    creating = await sqlite_db.listWorkspaces(status="creating")
    running = await sqlite_db.listWorkspaces(status="running")
    assert [w.id for w in creating] == [a.id]
    assert [w.id for w in running] == [b.id]
    assert {w.id for w in await sqlite_db.listWorkspaces()} == {a.id, b.id}


async def test_soft_delete_hides_the_row(sqlite_db: SqliteProvider) -> None:
    ws = await sqlite_db.createWorkspace(_ws_data("gone"))
    await sqlite_db.softDeleteWorkspace(ws.id)
    assert await sqlite_db.getWorkspace(ws.id) is None
    assert ws.id not in {w.id for w in await sqlite_db.listWorkspaces()}


async def test_update_persists_fields(sqlite_db: SqliteProvider) -> None:
    ws = await sqlite_db.createWorkspace(_ws_data("upd"))
    updated = await sqlite_db.updateWorkspace(
        ws.id, {"status": "running", "lxc_ip": "10.99.0.201", "vmid": 201}
    )
    assert updated.status == "running"
    assert updated.lxc_ip == "10.99.0.201"
    assert updated.vmid == 201


async def test_log_event_appends(sqlite_db: SqliteProvider) -> None:
    ws = await sqlite_db.createWorkspace(_ws_data("evt"))
    # logEvent is fire-and-forget (returns None); two appends must not raise and
    # must leave the workspace itself untouched.
    await sqlite_db.logEvent(ws.id, "workspace.created", {"by": "test"})
    await sqlite_db.logEvent(ws.id, "workspace.started", {})
    assert await sqlite_db.getWorkspace(ws.id) == ws


async def test_healthcheck_true(sqlite_db: SqliteProvider) -> None:
    assert await sqlite_db.healthcheck() is True
