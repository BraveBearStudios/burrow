# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Integration: multi-node ``GET /api/v1/nodes`` enumeration (WSX-01, Wave 0).

The route iterates ``settings.worker_nodes`` (not just ``[default_node]``) and reports
each node's ``overThreshold`` via the shared ``_fits`` helper, so the UI shows every
candidate node and the displayed capacity matches the auto-select decision.

App-level Fake capacity is varied with the in-tree idiom (there is NO Fake-injection
kwarg seam): a CLASS-LEVEL ``monkeypatch.setattr(FakeComputeProvider, "getNodeMemory", ...)``
returning a per-node fraction, plus a ``settings`` monkeypatch of ``worker_nodes`` —
mirroring ``test_nodes.py``.
"""

import httpx
import pytest

from config import settings


async def test_lists_all_worker_nodes_with_per_node_over_threshold(
    integration_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """/nodes enumerates worker_nodes; per-node overThreshold comes from shared _fits."""
    from compute.fakeProvider import FakeComputeProvider

    fractions = {"pve1": 0.42, "pve2": 0.95}

    async def per_node(self: FakeComputeProvider, node: str) -> float:
        return fractions[node]

    monkeypatch.setattr(FakeComputeProvider, "getNodeMemory", per_node)
    monkeypatch.setattr(settings, "worker_nodes", ["pve1", "pve2"], raising=False)
    monkeypatch.setattr(settings, "capacity_threshold", 0.80, raising=False)

    response = await integration_client.get("/api/v1/nodes")
    assert response.status_code == 200, response.text

    nodes = response.json()["data"]
    assert isinstance(nodes, list) and len(nodes) == 2
    by_name = {n["node"]: n for n in nodes}
    assert set(by_name) == {"pve1", "pve2"}

    # pve1 at 0.42 <= 0.80 -> not over; pve2 at 0.95 > 0.80 -> over (shared _fits).
    assert by_name["pve1"]["memoryUsedFraction"] == pytest.approx(0.42)
    assert by_name["pve1"]["overThreshold"] is False
    assert by_name["pve2"]["memoryUsedFraction"] == pytest.approx(0.95)
    assert by_name["pve2"]["overThreshold"] is True


async def test_multi_node_degrades_not_500_on_one_failing_node(
    integration_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A node whose getNodeMemory raises -> null fraction + overThreshold false at 200."""
    from compute.fakeProvider import FakeComputeProvider

    async def maybe_boom(self: FakeComputeProvider, node: str) -> float:
        if node == "pve2":
            raise RuntimeError("compute backend down for pve2")
        return 0.42

    monkeypatch.setattr(FakeComputeProvider, "getNodeMemory", maybe_boom)
    monkeypatch.setattr(settings, "worker_nodes", ["pve1", "pve2"], raising=False)

    response = await integration_client.get("/api/v1/nodes")
    assert response.status_code == 200, response.text

    by_name = {n["node"]: n for n in response.json()["data"]}
    assert by_name["pve1"]["memoryUsedFraction"] == pytest.approx(0.42)
    assert by_name["pve2"]["memoryUsedFraction"] is None
    assert by_name["pve2"]["overThreshold"] is False
