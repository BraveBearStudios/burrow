# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Integration: auto + manual node selection on create (WSX-01, criterion 5).

Drives the real app over temp SQLite + the Fake compute provider + the respx stub
ttyd (the ``integration_client`` fixture), so a create POST resolves end-to-end
WITHOUT any ``_wait_ttyd`` monkeypatch. The app-level Fake is NOT injectable via
kwargs and there is NO ``dependency_overrides`` hook, so per-node capacity is varied
the way ``test_nodes.py`` does it: a CLASS-LEVEL ``monkeypatch.setattr`` of
``FakeComputeProvider.getNodeMemory`` (a per-node lookup) plus a ``settings``
monkeypatch of ``worker_nodes`` / ``capacity_threshold``.

Proves the full WSX-01 contract end-to-end:

- AUTO (node omitted): the saga picks the least-loaded fitting node; the returned
  row's ``node`` is that node and status is ``running``.
- MANUAL (explicit node string): the saga uses it unchanged — ``selectNode`` is
  never consulted — and the row carries the supplied node.
- AUTO no-fit (every node over threshold): the create is refused with the
  ``capacity_exceeded`` envelope BEFORE reservation, so no workspace row is
  persisted (no orphan).
- Selection inside the lock: the persisted row's ``node`` equals the selected node,
  proving select -> guard -> reserve ran on the same node in one critical section.
"""

import httpx
import pytest

from compute.fakeProvider import FakeComputeProvider

from config import settings

_CREATE_BODY = {
    "name": "auto-ws",
    "projectRepo": "git@example.com:acme/auto.git",
    "projectBranch": "main",
}


def _assert_envelope(payload: dict[str, object]) -> None:
    """Every response carries the data/meta/error envelope (PLAT-01/02)."""
    assert set(payload) == {"data", "meta", "error"}
    assert isinstance(payload["meta"], dict)
    assert "requestId" in payload["meta"] and "timestamp" in payload["meta"]


def _fraction_provider(fractions: dict[str, float]) -> object:
    """A class-level ``getNodeMemory`` replacement returning per-node fractions.

    Mirrors ``test_nodes.py``'s ``boom`` idiom: a plain coroutine taking ``self``
    monkeypatched onto ``FakeComputeProvider`` so EVERY Fake instance the app builds
    reports the configured capacity. Unknown nodes fall back to a low ``0.25`` so an
    incidental probe never trips the threshold.
    """

    async def _getNodeMemory(self: FakeComputeProvider, node: str) -> float:
        return fractions.get(node, 0.25)

    return _getNodeMemory


async def test_auto_picks_least_loaded_fitting_node(
    integration_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Node omitted -> the saga auto-selects the least-loaded fitting node (pve2)."""
    monkeypatch.setattr(settings, "worker_nodes", ["pve1", "pve2"], raising=False)
    monkeypatch.setattr(settings, "capacity_threshold", 0.80, raising=False)
    monkeypatch.setattr(
        FakeComputeProvider,
        "getNodeMemory",
        _fraction_provider({"pve1": 0.6, "pve2": 0.3}),
    )

    response = await integration_client.post(
        "/api/v1/workspaces", json={**_CREATE_BODY, "node": None}
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    _assert_envelope(payload)

    data = payload["data"]
    assert data["status"] == "running"
    # pve2 (0.3) is least-loaded under the 0.80 threshold; pve1 (0.6) is not chosen.
    assert data["node"] == "pve2"


async def test_manual_node_pick_is_unchanged_end_to_end(
    integration_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Explicit node -> the saga uses it verbatim; selectNode is never consulted."""

    # Fail selectNode loudly: if the manual path wrongly called it, the create would
    # error — proving the supplied node skips selection entirely.
    async def _boom_select(self: object) -> str:
        raise AssertionError("selectNode must NOT run on the manual path")

    from services.workspaceService import WorkspaceService

    monkeypatch.setattr(WorkspaceService, "selectNode", _boom_select)
    monkeypatch.setattr(settings, "worker_nodes", ["pve1", "pve2", "pve3"], raising=False)

    response = await integration_client.post(
        "/api/v1/workspaces", json={**_CREATE_BODY, "node": "pve3"}
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "running"
    assert data["node"] == "pve3"


async def test_auto_no_fit_refuses_with_capacity_envelope_and_no_orphan(
    integration_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every node over threshold -> capacity_exceeded envelope + NO persisted row."""
    monkeypatch.setattr(settings, "worker_nodes", ["pve1", "pve2"], raising=False)
    monkeypatch.setattr(settings, "capacity_threshold", 0.80, raising=False)
    monkeypatch.setattr(
        FakeComputeProvider,
        "getNodeMemory",
        _fraction_provider({"pve1": 0.95, "pve2": 0.9}),
    )

    response = await integration_client.post(
        "/api/v1/workspaces", json={**_CREATE_BODY, "node": None}
    )
    assert response.status_code == 409, response.text
    body = response.json()
    _assert_envelope(body)
    assert body["data"] is None
    assert body["error"]["code"] == "capacity_exceeded"
    # WR-01: the curated auto no-fit hint must reach the wire verbatim — the
    # operator is told to pick a node manually, NOT the manual-path "selected node"
    # string (which is wrong here: they chose Auto, no node was selected).
    error_message = body["error"]["message"]
    assert "manually" in error_message.lower()
    assert "selected node" not in error_message.lower()

    # No-fit is refused at selection, BEFORE reservation: no orphan row persisted.
    listed = (await integration_client.get("/api/v1/workspaces")).json()
    assert listed["data"] == []


async def test_persisted_node_matches_selection_inside_lock(
    integration_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reserved row's node == the auto-selected node (select->guard->reserve atomic)."""
    monkeypatch.setattr(settings, "worker_nodes", ["pve1", "pve2"], raising=False)
    monkeypatch.setattr(settings, "capacity_threshold", 0.80, raising=False)
    # pve1 over threshold (skipped); pve2 fits -> selection must land on pve2 and the
    # persisted row must carry pve2, proving select/guard/reserve ran on one node.
    monkeypatch.setattr(
        FakeComputeProvider,
        "getNodeMemory",
        _fraction_provider({"pve1": 0.95, "pve2": 0.4}),
    )

    created = (
        await integration_client.post("/api/v1/workspaces", json={**_CREATE_BODY, "node": None})
    ).json()["data"]
    assert created["node"] == "pve2"

    # Re-read over the list endpoint: the durably persisted row carries the choice.
    fetched = (await integration_client.get(f"/api/v1/workspaces/{created['id']}")).json()["data"]
    assert fetched["node"] == "pve2"
