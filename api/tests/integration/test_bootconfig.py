# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Integration: pull-at-boot bootconfig endpoint (WORK-03, ADR-0002).

Drives the real app over temp SQLite + Fake compute + respx stub ttyd and proves
``GET /api/v1/internal/bootconfig/{vmid}`` end-to-end:

- an in-pool active vmid returns the non-secret payload + a ``gitCredential``;
- an out-of-pool vmid 404s WITHOUT echoing the probed value (enumeration
  resistance, T-01-17);
- an in-pool vmid with no active workspace 404s;
- the minted credential (a known sentinel) appears in ZERO captured log records
  AND zero event ``data`` blobs — the block_on=high no-secrets-in-logs gate
  (T-01-18, ASVS V7).

The sentinel is configured on the shared ``settings`` singleton so
``WorkspaceService.mint_repo_credential`` returns it; the test then asserts that
exact string is absent from logs and events.
"""

import logging

import httpx
import pytest

from config import settings

from tests.integration.conftest import await_workspace_status

# A high-entropy value that cannot occur incidentally; if it shows up in a log
# record or an event blob, the credential leaked (T-01-18, block_on=high).
_SENTINEL_CREDENTIAL = "SENTINEL-bootcred-9f2c4e7a1b6d8054-DO-NOT-LOG"

_CREATE_BODY = {
    "name": "boot-alpha",
    "projectRepo": "git@example.com:acme/boot-alpha.git",
    "projectBranch": "main",
    "node": "pve1",
}


@pytest.fixture
def _sentinel_token(monkeypatch: pytest.MonkeyPatch) -> str:
    """Configure a known short-lived credential the endpoint will mint.

    ``mint_repo_credential`` reads ``settings.git_credential_token`` at request
    time, so overriding the singleton makes the endpoint return the sentinel,
    which the no-leak assertions then hunt for in logs + events.
    """
    monkeypatch.setattr(settings, "git_credential_token", _SENTINEL_CREDENTIAL, raising=False)
    return _SENTINEL_CREDENTIAL


async def _create_workspace(client: httpx.AsyncClient) -> dict[str, object]:
    """Create a workspace and poll it to ``running`` so it holds a resolved IP (ADR-0017).

    The create endpoint returns ``202`` + a ``creating`` row; the boot saga resolves
    the static IP and lands ``running`` in a background task, so poll to ``running``
    before returning (the source-IP gate test needs the resolved ``lxc_ip``).
    """
    response = await client.post("/api/v1/workspaces", json=_CREATE_BODY)
    assert response.status_code == 202, response.text
    creating = response.json()["data"]
    return await await_workspace_status(client, creating["id"], "running")


def _assert_envelope(payload: dict[str, object]) -> None:
    assert set(payload) == {"data", "meta", "error"}


async def test_in_pool_vmid_returns_non_secret_payload_plus_credential(
    integration_client: httpx.AsyncClient, _sentinel_token: str
) -> None:
    """In-pool active vmid → 200 with the non-secret payload + gitCredential (WORK-03)."""
    created = await _create_workspace(integration_client)
    vmid = created["vmid"]
    assert vmid is not None

    response = await integration_client.get(f"/api/v1/internal/bootconfig/{vmid}")
    assert response.status_code == 200, response.text
    body = response.json()
    _assert_envelope(body)

    data = body["data"]
    # Non-secret identifiers (the BootConfig shape) in camelCase.
    assert set(data) == {
        "configRepo",
        "configBranch",
        "projectRepo",
        "projectBranch",
        "gitCredential",
    }
    assert data["projectRepo"] == _CREATE_BODY["projectRepo"]
    assert data["projectBranch"] == _CREATE_BODY["projectBranch"]
    # The minted credential is the configured short-lived token, returned once.
    assert data["gitCredential"] == _sentinel_token


async def test_out_of_pool_vmid_404_without_echoing_probe(
    integration_client: httpx.AsyncClient,
) -> None:
    """Out-of-pool vmid → 404; the body does NOT contain the probed value (T-01-17)."""
    # Below the pool start (default pool is [200, 299]); pick a value well outside.
    probed = settings.worker_pool_start - 73
    response = await integration_client.get(f"/api/v1/internal/bootconfig/{probed}")
    assert response.status_code == 404
    body = response.json()
    _assert_envelope(body)
    assert body["data"] is None
    assert body["error"]["code"] == "illegal_vmid"
    # Enumeration resistance: the probed number must not appear anywhere in the body.
    assert str(probed) not in response.text

    # And a value above the pool end behaves identically.
    high = settings.worker_pool_end + 41
    high_response = await integration_client.get(f"/api/v1/internal/bootconfig/{high}")
    assert high_response.status_code == 404
    assert str(high) not in high_response.text


async def test_in_pool_vmid_with_no_active_workspace_404(
    integration_client: httpx.AsyncClient,
) -> None:
    """An in-pool vmid that owns no active workspace → 404 (WORK-03)."""
    # In range but never created — no live workspace owns it.
    unowned = settings.worker_pool_start
    response = await integration_client.get(f"/api/v1/internal/bootconfig/{unowned}")
    assert response.status_code == 404
    body = response.json()
    _assert_envelope(body)
    assert body["data"] is None


async def test_credential_never_appears_in_logs_or_events(
    integration_client: httpx.AsyncClient,
    _sentinel_token: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The minted credential is in ZERO log records and ZERO event blobs (T-01-18)."""
    created = await _create_workspace(integration_client)
    vmid = created["vmid"]
    workspace_id = created["id"]

    with caplog.at_level(logging.DEBUG):
        response = await integration_client.get(f"/api/v1/internal/bootconfig/{vmid}")
    assert response.status_code == 200
    # The credential IS in the response body (it is returned to the worker once)…
    assert _sentinel_token in response.text

    # …but it must appear in NO captured log record (message, args, or any extra).
    for record in caplog.records:
        rendered = record.getMessage()
        assert _sentinel_token not in rendered, f"credential leaked into log: {rendered!r}"
        for value in record.__dict__.values():
            assert _sentinel_token not in str(value), "credential leaked into a log extra"

    # …and in NO event `data` blob for the workspace (ASVS V7, Pitfall 7).
    events = (await integration_client.get(f"/api/v1/workspaces/{workspace_id}/events")).json()[
        "data"
    ]
    for event in events:
        assert _SENTINEL_CREDENTIAL not in str(event), "credential leaked into an event"


async def test_source_ip_check_gate_blocks_a_mismatch(
    integration_client: httpx.AsyncClient,
    _sentinel_token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Enabling the source-IP check rejects a caller whose IP is not the worker IP.

    Defense-in-depth, NOT auth: the ASGITransport caller host is not the workspace's
    VMID-derived static IP, so a mismatch 404s when the gate is on, while the same
    request 200s when the gate is off (default).
    """
    created = await _create_workspace(integration_client)
    vmid = created["vmid"]

    # Gate OFF (default) → 200.
    off = await integration_client.get(f"/api/v1/internal/bootconfig/{vmid}")
    assert off.status_code == 200

    # Gate ON + caller IP != the worker's resolved lxc_ip → enumeration-resistant 404.
    monkeypatch.setattr(settings, "bootconfig_source_ip_check", True, raising=False)
    on = await integration_client.get(f"/api/v1/internal/bootconfig/{vmid}")
    assert on.status_code == 404
    assert on.json()["error"]["code"] == "illegal_vmid"
