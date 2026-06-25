# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""SETUP-01/02/07: the two new ComputeProvider setup capabilities.

Drives the REAL ``ProxmoxComputeProvider`` over ``responses``-mocked HTTP (proxmoxer
rides ``requests`` -> mocked with ``responses``, NEVER ``respx``; RESEARCH Pitfall 3/5)
through:

- ``testConnection``: all-9-privs success, a subset -> ``success=False`` + the exact
  sorted missing names, and a 401 -> token-free ``SetupAuthError``;
- ``verifyTemplate``: the ``template`` flag -> ``usable``, and not-found ->
  ``exists=False``.

Plus the ``FakeComputeProvider`` parity (default success + injected negatives) and the
SETUP-07 SecretStr redaction proof: a sentinel token placed in ``proxmox_token_value``
never appears in ``str(settings)`` / the field repr, yet ``.get_secret_value()`` returns
it. The ephemeral validation client + token-free errors mean the operator-typed token is
validated in-memory and never echoed.

Uses a ``_Settings`` stub mirroring ``test_proxmox_provider.py`` (placeholder values, no
real host/secret).
"""

from dataclasses import dataclass

import pytest
import responses
from pydantic import SecretStr

from config import Settings
from models.compute import ConnectionResult, TemplateResult

from compute.fakeProvider import FakeComputeProvider, FakeFailures
from compute.provider import SetupAuthError
from compute.proxmoxProvider import REQUIRED_PRIVS, ProxmoxComputeProvider

from tests.integration.mock_proxmox import (
    register_permissions,
    register_template_config,
)

_HOST = "pve1.local"
_USER = "burrow@pve"
_TOKEN_NAME = "burrow"
# A known sentinel: every assertion below proves it never leaks (SETUP-07).
_SENTINEL = "SENTINEL-TOKEN-DO-NOT-LEAK"  # noqa: S105  # test sentinel, not a real secret


@dataclass
class _Settings:
    """Settings stub carrying only the keys ProxmoxComputeProvider reads.

    Mirrors ``test_proxmox_provider.py``'s stub: a CA path (passed straight to
    ``verify_ssl``, never disabled). ``proxmox_token_value`` is a ``SecretStr`` to
    match the real ``Settings`` field, so ``.get_secret_value()`` at the proxmoxer
    boundary resolves. Values are placeholders — no real host/secret.
    """

    proxmox_host: str = _HOST
    proxmox_user: str = _USER
    proxmox_token_name: str = _TOKEN_NAME
    proxmox_token_value: SecretStr = SecretStr("test-token")
    proxmox_ca_cert_path: str = "/etc/burrow/pve-ca.pem"


def _provider() -> ProxmoxComputeProvider:
    return ProxmoxComputeProvider(_Settings())


# ── Proxmox testConnection (ephemeral read-only client) ──────────────────────
@responses.activate
async def test_connection_all_privs_present_succeeds() -> None:
    """All 9 BurrowProvisioner privs present -> success, no missing privileges."""
    register_permissions(_HOST, sorted(REQUIRED_PRIVS))

    result = await _provider().testConnection(_HOST, _USER, _TOKEN_NAME, _SENTINEL)

    assert isinstance(result, ConnectionResult)
    assert result.success is True
    assert result.missing_privileges == []
    # The read-only probe is exactly the permissions GET — no resource was created.
    methods_urls = [(c.request.method, c.request.url) for c in responses.calls]
    assert (
        "GET",
        f"https://{_HOST}:8006/api2/json/access/permissions",
    ) in methods_urls
    assert all(m == "GET" for m, _ in methods_urls)


@responses.activate
async def test_connection_missing_subset_reports_exact_sorted_names() -> None:
    """A token missing some privs -> success=False + the exact sorted missing names."""
    granted = sorted(set(REQUIRED_PRIVS) - {"VM.Clone", "Sys.Audit"})
    register_permissions(_HOST, granted)

    result = await _provider().testConnection(_HOST, _USER, _TOKEN_NAME, _SENTINEL)

    assert result.success is False
    assert result.missing_privileges == ["Sys.Audit", "VM.Clone"]


@responses.activate
async def test_connection_auth_failure_raises_token_free_setup_auth_error() -> None:
    """A 401 -> SetupAuthError with a FIXED token-free message (sentinel absent)."""
    register_permissions(_HOST, [], status=401)

    with pytest.raises(SetupAuthError) as exc_info:
        await _provider().testConnection(_HOST, _USER, _TOKEN_NAME, _SENTINEL)

    # The error message is fixed and token-free: the sentinel never reaches it.
    assert _SENTINEL not in str(exc_info.value)


# ── Proxmox verifyTemplate (read-only GETs) ──────────────────────────────────
@responses.activate
async def test_verify_template_with_template_flag_is_usable() -> None:
    """A config whose ``template`` flag is set -> exists and usable."""
    register_template_config(_HOST, "pve1", 9000, is_template=True)

    result = await _provider().verifyTemplate(9000, "pve1")

    assert isinstance(result, TemplateResult)
    assert result.exists is True
    assert result.usable is True
    assert result.vmid == 9000
    assert result.node == "pve1"


@responses.activate
async def test_verify_template_without_flag_exists_but_not_usable() -> None:
    """A real CT that is NOT a template -> exists but not usable."""
    register_template_config(_HOST, "pve1", 9000, is_template=False)

    result = await _provider().verifyTemplate(9000, "pve1")

    assert result.exists is True
    assert result.usable is False


@responses.activate
async def test_verify_template_not_found_reports_absent() -> None:
    """A 404 -> exists=False, usable=False (the template is not on the node)."""
    register_template_config(_HOST, "pve1", 9000, is_template=False, found=False)

    result = await _provider().verifyTemplate(9000, "pve1")

    assert result.exists is False
    assert result.usable is False


# ── Fake parity ──────────────────────────────────────────────────────────────
async def test_fake_test_connection_default_success() -> None:
    """The Fake's testConnection succeeds deterministically by default."""
    result = await FakeComputeProvider().testConnection(_HOST, _USER, _TOKEN_NAME, _SENTINEL)
    assert result.success is True
    assert result.missing_privileges == []


async def test_fake_test_connection_injected_missing_privileges() -> None:
    """FakeFailures can force a missing-privileges negative result (no raise)."""
    fake = FakeComputeProvider(FakeFailures(setup_missing_privileges=["VM.Clone"]))
    result = await fake.testConnection(_HOST, _USER, _TOKEN_NAME, _SENTINEL)
    assert result.success is False
    assert result.missing_privileges == ["VM.Clone"]


async def test_fake_test_connection_injected_auth_fail_raises() -> None:
    """FakeFailures can force the auth-fail path -> SetupAuthError."""
    fake = FakeComputeProvider(FakeFailures(setup_auth_fails=True))
    with pytest.raises(SetupAuthError):
        await fake.testConnection(_HOST, _USER, _TOKEN_NAME, _SENTINEL)


async def test_fake_verify_template_default_and_injected_missing() -> None:
    """The Fake's verifyTemplate succeeds by default and supports injectable not-found."""
    ok = await FakeComputeProvider().verifyTemplate(9000, "pve1")
    assert ok.exists is True and ok.usable is True

    fake = FakeComputeProvider(FakeFailures(setup_template_missing=True))
    missing = await fake.verifyTemplate(9000, "pve1")
    assert missing.exists is False and missing.usable is False


# ── SecretStr redaction (SETUP-07) ───────────────────────────────────────────
def test_secret_str_masks_token_in_str_and_repr_but_exposes_via_getter() -> None:
    """The token is masked in ``str(settings)`` / the field repr, real via getter."""
    settings = Settings(proxmox_token_value=SecretStr(_SENTINEL))
    assert _SENTINEL not in str(settings)
    assert _SENTINEL not in repr(settings.proxmox_token_value)
    assert settings.proxmox_token_value.get_secret_value() == _SENTINEL
