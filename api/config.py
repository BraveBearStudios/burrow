# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Application settings (pydantic-settings).

Reads ``.env`` (and the environment) using the key names committed in
``.env.example``. The provider switches ``BURROW_COMPUTE`` / ``BURROW_DB`` select
which concrete provider the app factory wires (Plan 03) — swapping an impl is an
env change, never a service edit.

Security note: never disable TLS verification. The Proxmox client validates the
node CA cert at ``proxmox_ca_cert_path`` instead (see ``.env.example``).
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from ``.env`` / the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Provider selection ────────────────────────────────────────────────
    # validation_alias binds the BURROW_* env names (a bare `compute: str` would
    # bind the lowercase `compute` env var, not BURROW_COMPUTE).
    compute: str = Field(default="fake", validation_alias="BURROW_COMPUTE")  # fake | proxmox
    db_kind: str = Field(default="sqlite", validation_alias="BURROW_DB")  # sqlite

    # ── Proxmox connection (read this phase, used Phase 1) ────────────────
    proxmox_host: str = "pve1.local"
    proxmox_user: str = "burrow@pve"
    proxmox_token_name: str = "burrow"
    proxmox_token_value: str = ""
    proxmox_ca_cert_path: str = "/etc/burrow/pve-ca.pem"  # validate TLS via CA, never disable it

    # ── Worker config distribution ────────────────────────────────────────
    config_repo: str = ""
    config_branch: str = "main"

    # ── LXC / worker pool ─────────────────────────────────────────────────
    template_vmid: int = 9000
    worker_pool_start: int = 200
    worker_pool_end: int = 299
    default_node: str = "pve1"

    # ── Database ──────────────────────────────────────────────────────────
    database_path: str = "/data/burrow.db"


settings = Settings()
