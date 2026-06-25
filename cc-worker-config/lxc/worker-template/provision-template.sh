#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# provision-template.sh — WORK-01: reproducible golden-template provisioner.
#
# Runs ONCE inside the template CT as root, before `pct template`. Bakes the
# worker software baseline (Ubuntu 24.04 + Node 22 + a pinned claude-code + ttyd
# + the template-baked plugins), installs the boot script + systemd unit, and
# enables the boot unit so every full clone boots straight into a persistent,
# LAN-bound ttyd session.
#
# Pinned (refresh on reprovision; bump the pin + record the new NodeSource ref):
#   - NodeSource setup ref: setup_22.x  (Node 22 LTS "Jod")
#   - @anthropic-ai/claude-code@2.1.170
#   - tmux 3.4 (Ubuntu 24.04 apt; unpinned in the install line, version recorded here)
#
# Plugins baked here = binary + npm-global types ONLY (rtk, gsd). claude-plugin
# types are PULLED AT BOOT (Phase 3) and must NOT be baked into the template.
#
# The /tmp payload (this script, burrow-boot.sh, burrow-worker.service, plugins/)
# is pushed into the CT by host-prime/20-create-template.sh before this runs.
#
# Source: .planning/.../00-RESEARCH.md §Golden Template & Boot (SC-corrected).
set -euo pipefail

log() { echo "[provision-template] $*"; }

CLAUDE_CODE_VERSION="2.1.170"

# --- Base OS + build toolchain + ttyd + jq -----------------------------------
# jq is the live burrow-boot.sh's JSON dependency (it parses the camelCase
# bootconfig envelope and, from Plan 02, iterates the plugin manifest). It is
# baked here so the boot script's runtime dependency exists in the golden image.
log "apt update/upgrade + base packages (git curl build-essential ttyd jq tmux)"
export DEBIAN_FRONTEND=noninteractive
apt-get update && apt-get upgrade -y
apt-get install -y git curl build-essential ttyd jq tmux

# --- Node 22 (NodeSource setup_22.x) + pinned Claude Code ---------------------
# The `curl | bash` runs inside the worker (not CI); it is the operator's
# documented trust decision. The Node major is pinned via the setup ref and the
# agent CLI is pinned exactly so the template is reproducible.
log "installing Node 22 via NodeSource setup_22.x"
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt-get install -y nodejs

log "installing pinned @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}"
npm install -g "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}"

# --- Baked plugins: binary + npm-global types only ---------------------------
# claude-plugin types are pulled at boot (Phase 3); do NOT bake them here.
if [[ -x /tmp/plugins/rtk/install.sh ]]; then
  log "baking rtk plugin (binary install)"
  bash /tmp/plugins/rtk/install.sh
else
  log "rtk plugin payload absent (/tmp/plugins/rtk/install.sh) — skipping"
fi
log "baking gsd plugin (npm-global)"
npm install -g get-shit-done-cc

# --- Boot script + systemd unit ----------------------------------------------
# burrow-boot.sh launches the persistent, LAN-bound ttyd (see that script).
log "installing /opt/burrow-boot.sh + burrow-worker.service, enabling the unit"
install -m 755 /tmp/burrow-boot.sh /opt/burrow-boot.sh
install -m 644 /tmp/burrow-worker.service /etc/systemd/system/burrow-worker.service
systemctl enable burrow-worker.service

# --- Boot-config placeholder -------------------------------------------------
# Populated at boot via PULL-AT-BOOT from the control-plane bootconfig endpoint
# (SC-4 / SC-5) — fetched by burrow-boot.sh, never injected at clone time.
# Secrets are never persisted here; burrow-boot.sh fetches non-secret config plus
# a short-lived, discarded git credential at boot.
log "creating /etc/burrow/worker.env placeholder (populated at boot)"
mkdir -p /etc/burrow && touch /etc/burrow/worker.env

# --- Baked /etc/tmux.conf -----------------------------------------------------
# Minimal scrollback config read by tmux on every worker boot (WSX-03 criterion 2).
# history-limit 50000 caps per-pane scrollback (~a few MB/pane, vs the tmux
# default 2000); window-size latest sizes the pane to the newest attached client
# (the single-reconnecting-web-client resize fix). No mouse/status/theme (YAGNI).
log "baking /etc/tmux.conf (history-limit 50000 + window-size latest)"
cat > /etc/tmux.conf <<'TMUXCONF'
set -g history-limit 50000
set -g window-size latest
TMUXCONF
chmod 644 /etc/tmux.conf

# --- Shrink the image --------------------------------------------------------
log "cleaning apt caches"
apt-get clean && rm -rf /var/lib/apt/lists/*

log "Template provisioned OK (claude-code ${CLAUDE_CODE_VERSION}, Node 22, ttyd, boot unit enabled)"
