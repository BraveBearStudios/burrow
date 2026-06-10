# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Integration: ``GET /api/v1/nodes`` per-node capacity (UI-04 backend).

Drives the real app over the Fake compute provider. The Fake reports a fixed
used-memory fraction (``0.25`` by default), so the endpoint's real fields
(``memoryUsedFraction``, ``capacityThreshold``, ``overThreshold``) are
deterministic. Proves:

- the standard ``{data, meta, error}`` envelope with camelCase keys (PLAT-02/09),
- ``overThreshold`` is the strict ``fraction > threshold`` flag with the boundary
  (``==`` threshold) NOT over (mirrors the CAP-01 capacity guard), and
- the endpoint degrades (never 500) if ``getNodeMemory`` raises.
"""

import httpx
import pytest

from config import settings


def _assert_envelope(payload: dict[str, object]) -> None:
    assert set(payload) == {"data", "meta", "error"}
    assert isinstance(payload["meta"], dict)
    assert "requestId" in payload["meta"] and "timestamp" in payload["meta"]
    assert payload["error"] is None


async def test_lists_nodes(integration_client: httpx.AsyncClient) -> None:
    """GET /api/v1/nodes returns per-node capacity over the Fake provider."""
    response = await integration_client.get("/api/v1/nodes")
    assert response.status_code == 200, response.text
    payload = response.json()
    _assert_envelope(payload)

    nodes = payload["data"]
    assert isinstance(nodes, list) and len(nodes) >= 1
    node = nodes[0]
    assert node["node"] == settings.default_node
    # Real fields only — the Fake's used-memory fraction + the configured threshold.
    assert node["memoryUsedFraction"] == pytest.approx(0.25)
    assert node["capacityThreshold"] == pytest.approx(settings.capacity_threshold)
    assert "overThreshold" in node


async def test_envelope_camelcase(integration_client: httpx.AsyncClient) -> None:
    """The response is the standard envelope with camelCase keys (PLAT-02/09)."""
    payload = (await integration_client.get("/api/v1/nodes")).json()
    _assert_envelope(payload)
    node = payload["data"][0]
    assert set(node) == {"node", "memoryUsedFraction", "capacityThreshold", "overThreshold"}


async def test_over_threshold_flag(
    integration_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """overThreshold is strict fraction > threshold; the boundary (==) is NOT over (CAP-01)."""
    # The Fake reports 0.25. Above-threshold: drop the threshold below 0.25 → over.
    monkeypatch.setattr(settings, "capacity_threshold", 0.10, raising=False)
    over = (await integration_client.get("/api/v1/nodes")).json()["data"][0]
    assert over["overThreshold"] is True

    # Boundary: threshold exactly equals the fraction → NOT over (mirrors CAP-01).
    monkeypatch.setattr(settings, "capacity_threshold", 0.25, raising=False)
    boundary = (await integration_client.get("/api/v1/nodes")).json()["data"][0]
    assert boundary["overThreshold"] is False

    # Below-threshold: threshold above the fraction → not over.
    monkeypatch.setattr(settings, "capacity_threshold", 0.80, raising=False)
    under = (await integration_client.get("/api/v1/nodes")).json()["data"][0]
    assert under["overThreshold"] is False


async def test_degrades_not_500_on_compute_error(
    integration_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If getNodeMemory raises, the endpoint degrades (200, fraction null) — never 500."""
    from compute.fakeProvider import FakeComputeProvider

    async def boom(self: FakeComputeProvider, node: str) -> float:
        raise RuntimeError("compute backend down")

    monkeypatch.setattr(FakeComputeProvider, "getNodeMemory", boom)
    response = await integration_client.get("/api/v1/nodes")
    assert response.status_code == 200, response.text
    node = response.json()["data"][0]
    assert node["node"] == settings.default_node
    assert node["memoryUsedFraction"] is None
    assert node["overThreshold"] is False
