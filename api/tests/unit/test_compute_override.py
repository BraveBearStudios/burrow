# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Proxmox-token runtime override + no-restart rebuild (ADR-0015).

Locks that a GUI-set Proxmox token applies without a process restart:

- ``ProxmoxComputeProvider`` binds the ``token_override`` over the ``.env`` value, and
  falls back to the ``.env`` value when no override is given;
- ``get_compute`` rebuilds the provider bound to the CURRENT override after
  ``set_proxmox_token_override`` + ``reset_compute`` (the credential-write sequence).

``proxmoxer.ProxmoxAPI`` is monkeypatched to a capturing stub so no real connection
is attempted and the bound token can be observed.
"""

from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import SecretStr

import main
from compute.proxmoxProvider import ProxmoxComputeProvider


@dataclass
class _Settings:
    """Settings stub carrying only the proxmox_* fields the provider reads."""

    proxmox_host: str = "10.0.0.6"
    proxmox_user: str = "burrow@pve"
    proxmox_token_name: str = "burrow"
    proxmox_token_value: SecretStr = SecretStr("env-token")
    proxmox_ca_cert_path: str = "/etc/burrow/pve-ca.pem"


class _CaptureApi:
    """Capturing stand-in for ``proxmoxer.ProxmoxAPI``: records token_value, connects to nothing."""

    last_token: str | None = None

    def __init__(
        self, host: str, *, user: str, token_name: str, token_value: str, verify_ssl: Any
    ) -> None:
        _CaptureApi.last_token = token_value


@pytest.fixture
def capture_proxmox(monkeypatch: pytest.MonkeyPatch) -> type[_CaptureApi]:
    """Replace ``proxmoxer.ProxmoxAPI`` with the capturing stub (no real connection)."""
    monkeypatch.setattr("compute.proxmoxProvider.proxmoxer.ProxmoxAPI", _CaptureApi)
    _CaptureApi.last_token = None
    return _CaptureApi


def test_override_token_used_when_provided(capture_proxmox: type[_CaptureApi]) -> None:
    ProxmoxComputeProvider(_Settings(), token_override="gui-set-token")
    assert capture_proxmox.last_token == "gui-set-token"


def test_env_token_used_when_no_override(capture_proxmox: type[_CaptureApi]) -> None:
    ProxmoxComputeProvider(_Settings())
    assert capture_proxmox.last_token == "env-token"


def test_get_compute_rebuilds_with_new_override(
    capture_proxmox: type[_CaptureApi], monkeypatch: pytest.MonkeyPatch
) -> None:
    from config import settings as real_settings

    monkeypatch.setattr(real_settings, "compute", "proxmox", raising=False)
    main.reset_compute()
    main.set_proxmox_token_override(None)
    try:
        # No override -> the provider binds the .env token.
        main.get_compute()
        assert capture_proxmox.last_token == real_settings.proxmox_token_value.get_secret_value()

        # A "GUI write": set the override + reset -> the next build rebinds the new token.
        main.set_proxmox_token_override("rotated-gui-token")
        main.reset_compute()
        main.get_compute()
        assert capture_proxmox.last_token == "rotated-gui-token"
    finally:
        main.reset_compute()
        main.set_proxmox_token_override(None)
