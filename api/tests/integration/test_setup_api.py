# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Integration: the guided-setup API surface (SETUP-01..05).

Drives the real app over temp SQLite + the Fake compute provider (the
``integration_client`` fixture) for the endpoint happy/negative paths, and the
Phase 10 mocked-proxmoxer tier (the REAL ``ProxmoxComputeProvider`` over
``responses``) for the read-only / zero-resource proof and the real-shaped
permission map.

Covers:

- ``POST /api/v1/setup/test-connection`` returns a ``ConnectionResult`` envelope
  (success + missingPrivileges) over the Fake.
- ``POST /api/v1/setup/verify-template`` returns a ``TemplateResult`` envelope.
- The token field is ``SecretStr`` (redacted in 422 bodies / repr).
- The four token-free setup error codes map at the envelope boundary.
- Read-only / zero-resource: the REAL provider issues GET-only calls (no
  POST/PUT/DELETE) over the mocked tier (SETUP-01 "creates zero resources").
- SETUP-03 readiness reuses ``GET /api/v1/health`` (degrade-not-500); no new
  readiness endpoint is added.
- ``GET /api/v1/setup/state`` returns ``{setupCompletedAt: null}`` on a fresh DB
  (SETUP-04); ``POST /api/v1/setup/complete`` stamps it to a timestamp readable
  by a follow-up state GET, and is idempotent across two calls (SETUP-05).
"""

import httpx
import pytest
import responses
from pydantic import SecretStr

from compute.fakeProvider import FakeComputeProvider, FakeFailures
from compute.proxmoxProvider import REQUIRED_PRIVS, ProxmoxComputeProvider
from config import settings

from tests.integration.mock_proxmox import (
    register_permissions,
    register_template_config,
)

# A valid test-connection body; the Fake ignores the values but the router still
# validates the shape (host/user/tokenName/tokenValue) and SecretStr-wraps the token.
_CONNECT_BODY = {
    "host": "pve1.local",
    "user": "burrow@pve",
    "tokenName": "burrow",
    "tokenValue": "operator-typed-token",
}
_TEMPLATE_BODY = {"templateVmid": 9000, "node": "pve1"}


def _assert_envelope(payload: dict[str, object]) -> None:
    """Every response carries the data/meta/error envelope (PLAT-01/02)."""
    assert set(payload) == {"data", "meta", "error"}
    assert isinstance(payload["meta"], dict)
    assert "requestId" in payload["meta"] and "timestamp" in payload["meta"]


@pytest.fixture
def _fake_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Carry the mocked-tier settings the REAL provider reads (no real host/secret)."""
    monkeypatch.setattr(settings, "proxmox_host", "pve1.local", raising=False)
    monkeypatch.setattr(settings, "proxmox_user", "burrow@pve", raising=False)
    monkeypatch.setattr(settings, "proxmox_token_name", "burrow", raising=False)
    monkeypatch.setattr(
        settings, "proxmox_token_value", SecretStr("test-token"), raising=False
    )
    monkeypatch.setattr(
        settings, "proxmox_ca_cert_path", "/etc/burrow/pve-ca.pem", raising=False
    )


# ── endpoint happy paths over the Fake ───────────────────────────────────────
async def test_test_connection_success_envelope(
    integration_client: httpx.AsyncClient,
) -> None:
    """A valid body → 200 ConnectionResult envelope (success, missingPrivileges)."""
    response = await integration_client.post(
        "/api/v1/setup/test-connection", json=_CONNECT_BODY
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    _assert_envelope(payload)
    data = payload["data"]
    assert data == {"success": True, "missingPrivileges": []}


async def test_verify_template_success_envelope(
    integration_client: httpx.AsyncClient,
) -> None:
    """A valid body → 200 TemplateResult envelope (exists, usable, vmid, node)."""
    response = await integration_client.post(
        "/api/v1/setup/verify-template", json=_TEMPLATE_BODY
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    _assert_envelope(payload)
    assert payload["data"] == {
        "exists": True,
        "usable": True,
        "vmid": 9000,
        "node": "pve1",
    }


async def test_test_connection_token_is_secretstr_redacted_on_422(
    integration_client: httpx.AsyncClient,
) -> None:
    """A 422 (missing host) never echoes the token: the SecretStr is redacted (SETUP-07)."""
    bad_body = {**_CONNECT_BODY}
    del bad_body["host"]
    response = await integration_client.post(
        "/api/v1/setup/test-connection", json=bad_body
    )
    assert response.status_code == 422, response.text
    assert "operator-typed-token" not in response.text


# ── setup error codes mapped at the envelope boundary (over the Fake) ─────────
def _inject_compute(
    monkeypatch: pytest.MonkeyPatch, provider: FakeComputeProvider
) -> None:
    """Seed the process-wide compute singleton so ``get_compute()`` returns ``provider``.

    The router resolves ``Depends(get_compute)`` against the cached singleton, so
    seeding it (rather than monkeypatching the function object the Depends already
    captured) is what actually swaps the provider the endpoint uses.
    """
    import main

    monkeypatch.setattr(main, "_compute_singleton", provider, raising=False)
    monkeypatch.setattr(main, "_compute_kind", settings.compute, raising=False)


async def test_auth_failure_maps_to_setup_auth_failed(
    integration_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A SetupAuthError → setup_auth_failed envelope with a token-free message."""
    _inject_compute(monkeypatch, FakeComputeProvider(FakeFailures(setup_auth_fails=True)))

    response = await integration_client.post(
        "/api/v1/setup/test-connection", json=_CONNECT_BODY
    )
    payload = response.json()
    _assert_envelope(payload)
    assert payload["error"]["code"] == "setup_auth_failed"
    # Token-free, fixed message (never str(exc) / the rejected token).
    assert "operator-typed-token" not in response.text
    assert payload["data"] is None


async def test_missing_privileges_surface_in_body(
    integration_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A token missing privileges → success=False + the exact sorted missing names."""
    _inject_compute(
        monkeypatch,
        FakeComputeProvider(FakeFailures(setup_missing_privileges=["VM.Clone", "Sys.Audit"])),
    )

    response = await integration_client.post(
        "/api/v1/setup/test-connection", json=_CONNECT_BODY
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["success"] is False
    assert data["missingPrivileges"] == ["Sys.Audit", "VM.Clone"]


async def test_template_missing_surfaces_in_body(
    integration_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing template → exists=False, usable=False (per the body contract)."""
    _inject_compute(
        monkeypatch, FakeComputeProvider(FakeFailures(setup_template_missing=True))
    )

    response = await integration_client.post(
        "/api/v1/setup/verify-template", json=_TEMPLATE_BODY
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["exists"] is False
    assert data["usable"] is False


# ── SETUP-03 readiness reuses /api/v1/health (no new endpoint) ────────────────
async def test_health_still_serves_readiness(
    integration_client: httpx.AsyncClient,
) -> None:
    """GET /api/v1/health is unchanged degrade-not-500 {status, db, compute} (SETUP-03)."""
    response = await integration_client.get("/api/v1/health")
    assert response.status_code == 200, response.text
    payload = response.json()
    _assert_envelope(payload)
    assert set(payload["data"]) == {"status", "db", "compute"}


def test_no_parallel_readiness_endpoint_added() -> None:
    """SETUP-03 reuses /api/v1/health: no new /setup/readiness-style route exists."""
    from main import create_app

    app = create_app()
    paths = {getattr(route, "path", "") for route in app.routes}
    assert "/api/v1/health" in paths
    assert "/api/v1/setup/test-connection" in paths
    assert "/api/v1/setup/verify-template" in paths
    # No parallel readiness route was introduced under /setup.
    assert not any("readiness" in p for p in paths)


# ── first-run gate: state read + idempotent complete (over the Fake) ──────────
async def test_setup_state_starts_null(
    integration_client: httpx.AsyncClient,
) -> None:
    """A fresh per-test DB seeds NULL (migration 003) → state has setupCompletedAt=None."""
    response = await integration_client.get("/api/v1/setup/state")
    assert response.status_code == 200, response.text
    payload = response.json()
    _assert_envelope(payload)
    assert payload["data"] == {"setupCompletedAt": None}


async def test_complete_then_state_returns_timestamp(
    integration_client: httpx.AsyncClient,
) -> None:
    """POST /complete stamps a non-null timestamp that a follow-up state GET returns."""
    complete = await integration_client.post("/api/v1/setup/complete")
    assert complete.status_code == 200, complete.text
    complete_payload = complete.json()
    _assert_envelope(complete_payload)
    stamped = complete_payload["data"]["setupCompletedAt"]
    assert isinstance(stamped, str) and stamped

    state = await integration_client.get("/api/v1/setup/state")
    assert state.status_code == 200, state.text
    state_payload = state.json()
    _assert_envelope(state_payload)
    # The state read returns exactly the timestamp the complete call wrote.
    assert state_payload["data"] == {"setupCompletedAt": stamped}


async def test_complete_is_idempotent(
    integration_client: httpx.AsyncClient,
) -> None:
    """Two POST /complete calls both 200 with a non-null timestamp; the row stays set."""
    first = await integration_client.post("/api/v1/setup/complete")
    assert first.status_code == 200, first.text
    first_stamp = first.json()["data"]["setupCompletedAt"]
    assert isinstance(first_stamp, str) and first_stamp

    # The second call must not error — re-stamping the singleton is a plain UPDATE.
    second = await integration_client.post("/api/v1/setup/complete")
    assert second.status_code == 200, second.text
    second_stamp = second.json()["data"]["setupCompletedAt"]
    assert isinstance(second_stamp, str) and second_stamp

    # The row stays set after both calls (state still reports a non-null timestamp).
    state = await integration_client.get("/api/v1/setup/state")
    assert state.status_code == 200, state.text
    assert state.json()["data"]["setupCompletedAt"] is not None


def test_setup_state_and_complete_routes_registered() -> None:
    """The two gate routes are live on the app (SETUP-04/05)."""
    from main import create_app

    app = create_app()
    paths = {getattr(route, "path", "") for route in app.routes}
    assert "/api/v1/setup/state" in paths
    assert "/api/v1/setup/complete" in paths


# ── read-only / zero-resource proof over the REAL provider (mocked tier) ──────
@responses.activate
async def test_real_provider_test_connection_is_get_only(
    _fake_settings: None,
) -> None:
    """testConnection over the mocked tier issues ONLY a GET — zero resources (SETUP-01).

    Drives the REAL ``ProxmoxComputeProvider`` (never the Fake) so the actual
    ``GET /access/permissions`` probe runs over ``responses``. Asserts every call
    was a GET (no POST/PUT/DELETE clone/CT) and the only path hit was the
    permissions probe.
    """
    host = "pve1.local"
    register_permissions(host, sorted(REQUIRED_PRIVS))

    provider = ProxmoxComputeProvider(settings)
    result = await provider.testConnection(
        host=host, user="burrow@pve", token_name="burrow", token_value="t"
    )

    assert result.success is True
    assert result.missing_privileges == []
    methods = [c.request.method for c in responses.calls]
    assert methods, "expected at least one HTTP call"
    assert all(m == "GET" for m in methods), f"non-GET issued: {methods}"
    base = f"https://{host}:8006/api2/json"
    urls = [c.request.url for c in responses.calls]
    assert urls == [f"{base}/access/permissions"]


@responses.activate
async def test_real_provider_missing_priv_reports_exact_names(
    _fake_settings: None,
) -> None:
    """A permissions map missing VM.Clone → success=False, missingPrivileges==['VM.Clone']."""
    host = "pve1.local"
    granted = sorted(REQUIRED_PRIVS - {"VM.Clone"})
    register_permissions(host, granted)

    provider = ProxmoxComputeProvider(settings)
    result = await provider.testConnection(
        host=host, user="burrow@pve", token_name="burrow", token_value="t"
    )

    assert result.success is False
    assert result.missing_privileges == ["VM.Clone"]
    assert all(c.request.method == "GET" for c in responses.calls)


@responses.activate
async def test_real_provider_auth_fail_raises_setup_auth_error(
    _fake_settings: None,
) -> None:
    """A 401 permissions GET → a token-free SetupAuthError (→ setup_auth_failed)."""
    from compute.provider import SetupAuthError

    host = "pve1.local"
    register_permissions(host, [], status=401)

    # WR-03/IN-02: a distinctive multi-char sentinel (not a substring of the fixed
    # message) so the leak assertion below can actually fail if the rejected token
    # were ever interpolated. The old 1-char "t" token made the assertion vacuous.
    sentinel = "SENTINEL-TOKEN-DO-NOT-LEAK"
    provider = ProxmoxComputeProvider(settings)
    with pytest.raises(SetupAuthError) as exc_info:
        await provider.testConnection(
            host=host, user="burrow@pve", token_name="burrow", token_value=sentinel
        )
    # Behavioral assertion (WR-03): the typed error carries the FIXED token-free
    # message, AND the rejected token VALUE never reaches it. Both clauses can fail.
    message = str(exc_info.value)
    assert message == "proxmox token was rejected (auth failed)"
    assert sentinel not in message
    assert all(c.request.method == "GET" for c in responses.calls)


@responses.activate
async def test_real_provider_verify_template_usable_is_get_only(
    _fake_settings: None,
) -> None:
    """verifyTemplate over the mocked tier is GET-only and reports usable from the flag."""
    host, node, vmid = "pve1.local", "pve1", 9000
    register_template_config(host, node, vmid, is_template=True)

    provider = ProxmoxComputeProvider(settings)
    result = await provider.verifyTemplate(template_vmid=vmid, node=node)

    assert result.exists is True
    assert result.usable is True
    assert result.vmid == vmid
    assert result.node == node
    assert all(c.request.method == "GET" for c in responses.calls)


@responses.activate
async def test_real_provider_verify_template_not_found_is_get_only(
    _fake_settings: None,
) -> None:
    """A 404 template config → exists=False, usable=False, still GET-only."""
    host, node, vmid = "pve1.local", "pve1", 9999
    register_template_config(host, node, vmid, is_template=False, found=False)

    provider = ProxmoxComputeProvider(settings)
    result = await provider.verifyTemplate(template_vmid=vmid, node=node)

    assert result.exists is False
    assert result.usable is False
    assert all(c.request.method == "GET" for c in responses.calls)
