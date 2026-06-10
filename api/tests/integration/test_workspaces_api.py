# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Integration: full ``/api/v1/workspaces`` CRUD lifecycle (WS-01/04/05/06/07/08/11).

Drives the real app over temp SQLite + the Fake compute provider + the respx stub
ttyd. Proves create→running, list (+status filter), get-by-id, stop, start, destroy
(soft-delete → subsequent GET 404), the event log (oldest-first, WS-11), the 404
envelope for an unknown id, and the 409 envelope for an illegal transition.
"""

import httpx

_CREATE_BODY = {
    "name": "alpha",
    "projectRepo": "git@example.com:acme/alpha.git",
    "projectBranch": "main",
    "node": "pve1",
}


def _assert_envelope(payload: dict[str, object]) -> None:
    """Every response carries the data/meta/error envelope (PLAT-01/02)."""
    assert set(payload) == {"data", "meta", "error"}
    assert isinstance(payload["meta"], dict)
    assert "requestId" in payload["meta"] and "timestamp" in payload["meta"]


async def _create(client: httpx.AsyncClient, **overrides: str) -> dict[str, object]:
    body = {**_CREATE_BODY, **overrides}
    response = await client.post("/api/v1/workspaces", json=body)
    assert response.status_code == 200, response.text
    payload = response.json()
    _assert_envelope(payload)
    return payload["data"]  # type: ignore[no-any-return]


async def test_create_reaches_running(integration_client: httpx.AsyncClient) -> None:
    """POST creates a workspace and the saga drives it to ``running`` (WS-01)."""
    data = await _create(integration_client)
    assert data["status"] == "running"
    assert data["name"] == "alpha"
    assert data["vmid"] is not None
    assert data["projectRepo"] == "git@example.com:acme/alpha.git"


async def test_list_and_status_filter(integration_client: httpx.AsyncClient) -> None:
    """GET lists workspaces; ``?status=`` filters (WS-04)."""
    created = await _create(integration_client)

    listed = (await integration_client.get("/api/v1/workspaces")).json()
    _assert_envelope(listed)
    assert any(ws["id"] == created["id"] for ws in listed["data"])

    running = (await integration_client.get("/api/v1/workspaces?status=running")).json()
    assert all(ws["status"] == "running" for ws in running["data"])
    assert any(ws["id"] == created["id"] for ws in running["data"])

    stopped = (await integration_client.get("/api/v1/workspaces?status=stopped")).json()
    assert stopped["data"] == []


async def test_get_by_id_and_unknown_404(integration_client: httpx.AsyncClient) -> None:
    """GET by id returns the workspace (WS-05); an unknown id is a 404 envelope."""
    created = await _create(integration_client)

    response = await integration_client.get(f"/api/v1/workspaces/{created['id']}")
    assert response.status_code == 200
    assert response.json()["data"]["id"] == created["id"]

    missing = await integration_client.get("/api/v1/workspaces/does-not-exist")
    assert missing.status_code == 404
    body = missing.json()
    _assert_envelope(body)
    assert body["data"] is None
    assert body["error"]["code"] == "not_found"


async def test_stop_then_start_round_trip(integration_client: httpx.AsyncClient) -> None:
    """Stop → stopped (WS-06); start → running again (WS-07)."""
    created = await _create(integration_client)
    wid = created["id"]

    stopped = await integration_client.post(f"/api/v1/workspaces/{wid}/stop")
    assert stopped.status_code == 200
    assert stopped.json()["data"]["status"] == "stopped"

    started = await integration_client.post(f"/api/v1/workspaces/{wid}/start")
    assert started.status_code == 200
    assert started.json()["data"]["status"] == "running"


async def test_destroy_soft_deletes(integration_client: httpx.AsyncClient) -> None:
    """DELETE destroys + soft-deletes; a subsequent GET is a 404 (WS-08)."""
    created = await _create(integration_client)
    wid = created["id"]

    destroyed = await integration_client.delete(f"/api/v1/workspaces/{wid}")
    assert destroyed.status_code == 200
    assert destroyed.json()["data"]["status"] == "destroyed"

    after = await integration_client.get(f"/api/v1/workspaces/{wid}")
    assert after.status_code == 404


async def test_event_log_oldest_first(integration_client: httpx.AsyncClient) -> None:
    """The event log is readable and ordered oldest-first (WS-11)."""
    created = await _create(integration_client)
    wid = created["id"]
    await integration_client.post(f"/api/v1/workspaces/{wid}/stop")

    response = await integration_client.get(f"/api/v1/workspaces/{wid}/events")
    assert response.status_code == 200
    events = response.json()["data"]
    types = [event["type"] for event in events]
    assert types == ["workspace.created", "workspace.stopped"]


async def test_illegal_transition_returns_409(integration_client: httpx.AsyncClient) -> None:
    """Starting a running workspace is illegal → 409 envelope (WS-09)."""
    created = await _create(integration_client)
    wid = created["id"]

    # running --start--> is not a legal transition (start requires `stopped`).
    response = await integration_client.post(f"/api/v1/workspaces/{wid}/start")
    assert response.status_code == 409
    body = response.json()
    _assert_envelope(body)
    assert body["error"]["code"] == "illegal_transition"
