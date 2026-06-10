# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Integration: ``/api/v1/health`` degrade-not-500 (PLAT-03).

Healthy path → 200 with ``status``/``db``/``compute`` all reported. A down compute
dependency (its ``healthcheck`` forced to raise) still yields 200 with
``compute == "error"`` and ``status == "degraded"`` — never a 500 (PLAT-03). The
body leaks no exception text (T-01-15).
"""

import httpx
import pytest

from compute.fakeProvider import FakeComputeProvider


async def test_health_ok(integration_client: httpx.AsyncClient) -> None:
    """All dependencies up → 200, status ok, db + compute ok."""
    response = await integration_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "ok"
    assert data["db"] == "ok"
    assert data["compute"] == "ok"


async def test_health_degrades_not_500_when_compute_down(
    integration_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A raising compute healthcheck → 200 with compute=error, status=degraded (PLAT-03)."""

    async def _boom(self: FakeComputeProvider) -> bool:
        raise RuntimeError("compute backend unreachable")

    monkeypatch.setattr(FakeComputeProvider, "healthcheck", _boom, raising=True)

    response = await integration_client.get("/api/v1/health")
    assert response.status_code == 200  # degrade, never 500
    data = response.json()["data"]
    assert data["status"] == "degraded"
    assert data["compute"] == "error"
    assert data["db"] == "ok"
    # No internal exception text leaked into the body (T-01-15).
    assert "unreachable" not in response.text
