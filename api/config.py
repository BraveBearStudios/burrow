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

from pydantic import Field, SecretStr, model_validator
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
    # SETUP-07: SecretStr so `__repr__`/`__str__` and any 422/validation error render
    # the mask, never the raw token. The real value is read ONLY at the proxmoxer
    # boundary via `.get_secret_value()` (proxmoxProvider.__init__ / testConnection).
    proxmox_token_value: SecretStr = SecretStr("")
    proxmox_ca_cert_path: str = "/etc/burrow/pve-ca.pem"  # validate TLS via CA, never disable it

    # ── Worker config distribution ────────────────────────────────────────
    config_repo: str = ""
    config_branch: str = "main"

    # ── LXC / worker pool ─────────────────────────────────────────────────
    template_vmid: int = 9000
    worker_pool_start: int = 200
    worker_pool_end: int = 299
    default_node: str = "pve1"
    # Candidate-node topology auto-select (WSX-01) iterates. Declared with an empty
    # default_factory (never a shared mutable literal) and DERIVED from the resolved
    # default_node by the validator below, so a BURROW_DEFAULT_NODE / explicit
    # default_node override propagates into the default. An explicit non-empty
    # worker_nodes is left untouched.
    worker_nodes: list[str] = Field(default_factory=list)

    # ── Worker net0 / static-IP-from-VMID (ADR-0004) ──────────────────────
    # Placeholders only — the real LAN topology lives in the gitignored .env.
    # The static IP is derived from the VMID against these params; never a real LAN.
    worker_subnet: str = "10.99.0.0/24"  # placeholder LAN subnet (CIDR)
    worker_gateway: str = "10.99.0.1"  # placeholder LAN gateway
    worker_bridge: str = "vmbr0"  # Proxmox bridge the net0 attaches to
    worker_prefix: int = 24  # net0 CIDR prefix length

    # ── Capacity guard (CAP-01) ───────────────────────────────────────────
    capacity_threshold: float = 0.80  # refuse create when node RAM fraction exceeds this

    # ── Saga timeouts (seconds) ───────────────────────────────────────────
    ttyd_timeout: float = 60  # saga step 6: total ttyd-health wait
    ttyd_interval: float = 2  # saga step 6: poll interval
    clone_timeout: float = 300  # UPID wait for a --full clone (conservative; tune in homelab)
    task_timeout: float = 120  # UPID wait for start/stop/destroy

    # ── Reconciler (reaper + idle auto-stop, CAP-02/03) ───────────────────
    # Non-secret cadence knobs for the in-process periodic reconciler (ADR-0010).
    # Defaults sit inside the CONTEXT ranges; tune per deployment.
    reconciler_period_s: float = 60  # how often the reconcile loop runs one pass
    creating_timeout_s: float = 300  # a `creating` row older than this is reaped to `error`
    idle_window_s: float = 1800  # auto-stop a running workspace idle longer than this (~30 min)

    # ── Security / CORS (PLAT-05) ─────────────────────────────────────────
    # The LAN UI origin — NEVER "*" (incompatible with credentials + Pitfall 12).
    # A clearly-marked placeholder; the real origin lives in the gitignored .env.
    allowed_origin: str = "http://localhost:5173"  # placeholder LAN UI origin

    # ── Bootconfig (WORK-03 / ADR-0002) ───────────────────────────────────
    # Short-lived, repo-scoped git credential read from the gitignored .env.
    # Empty placeholder default — NEVER commit a real PAT (CLAUDE.md: no secrets).
    git_credential_token: str = ""
    # Defense-in-depth source-IP binding for the bootconfig endpoint; default off
    # so it does not break the no-auth LAN posture unless an operator enables it.
    # IN-03: this check compares request.client.host to the worker's VMID-derived
    # static IP, so it is ONLY valid when the API is reached DIRECTLY by workers.
    # Behind the documented nginx TLS terminator (or any proxy) client.host is the
    # proxy's address, not the worker's, and the check would 404 every legitimate
    # boot. Enable it only on a direct-to-API topology, or extend it to honor a
    # trusted X-Forwarded-For before turning it on behind a proxy.
    bootconfig_source_ip_check: bool = False

    # ── Database ──────────────────────────────────────────────────────────
    database_path: str = "/data/burrow.db"
    # Per-connection SQLite busy timeout (ms): how long a writer blocked by a
    # concurrent writer's held lock waits before failing. Required so the VMID
    # reservation race (SC-3/SC-4) surfaces a retryable VmidTakenError rather
    # than a raw "database is locked" OperationalError (CR-02).
    sqlite_busy_timeout_ms: int = 5000

    @model_validator(mode="after")
    def _normalize_worker_nodes(self) -> "Settings":
        """Normalize ``worker_nodes``, defaulting to ``[default_node]`` (WSX-01, WR-02).

        Strips surrounding whitespace, drops empty entries, and de-duplicates while
        preserving order — so a comma-split env source like ``pve1,,pve1, pve2``
        cannot feed an empty-string or duplicate node into ``selectNode``'s loop
        (where an empty name would be probed and could be persisted as a bogus
        target). If nothing survives normalization (unset or all-empty),
        ``worker_nodes`` falls back to ``[default_node]`` — deriving the default
        from the resolved ``default_node`` so a ``BURROW_DEFAULT_NODE`` / explicit
        override propagates into the candidate list.
        """
        seen: list[str] = []
        for node in self.worker_nodes:
            name = node.strip()
            if name and name not in seen:
                seen.append(name)
        self.worker_nodes = seen if seen else [self.default_node]
        return self


settings = Settings()
