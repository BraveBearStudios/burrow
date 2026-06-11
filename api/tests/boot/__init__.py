# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Boot-harness test package (Phase 3 — the worker-side pull-at-boot gate).

Drives ``cc-worker-config/lxc/worker-template/burrow-boot.sh`` as a subprocess
against a HERMETIC substrate — a loopback fake control plane, ``file://`` bare git
remotes, and a stub ``ttyd`` on ``PATH`` — with zero real Proxmox. This is the
worker-side analogue of the server-side ``tests/integration/test_bootconfig.py``
gate: the integration tier proves the endpoint never logs the credential; this
tier proves the worker never leaks it post-fetch (SC-3, T-03-01..04).

Real worker boot stays the dev-homelab smoke (human-verify), NOT a CI command.
"""
