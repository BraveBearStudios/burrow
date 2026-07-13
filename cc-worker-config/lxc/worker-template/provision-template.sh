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

# The `ttyd` apt package ships an ENABLED ttyd.service daemon that binds :7681 on
# loopback (TTYD_OPTIONS in /etc/default/ttyd: `-i lo -p 7681 ...`). It would win the
# race for :7681 against the real LAN-bound ttyd that burrow-boot.sh execs, so the
# worker ttyd fails with EADDRINUSE on 0.0.0.0:7681 and burrow-worker.service
# restart-loops (the terminal is then loopback-only, unreachable by the proxy). We use
# the /usr/bin/ttyd BINARY only, never the packaged daemon. Disable + mask it
# (offline-safe, mirrors the enable below); mask blocks any re-enable on upgrade.
log "masking the packaged ttyd.service daemon (burrow-worker owns :7681)"
systemctl disable ttyd.service 2>/dev/null || true
systemctl mask ttyd.service

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

# --- Boot-config: bake the (non-secret) CONTROL_PLANE URL --------------------
# LXC has no exec/file-write API over HTTPS (ADR-0002), so the per-clone create
# saga CANNOT populate worker.env at clone time. CONTROL_PLANE is the SAME constant
# for every worker of a given control plane, so it is baked into the template here
# from CONTROL_PLANE_URL (passed by 20-create-template.sh via `pct exec -- env`).
# Only this non-secret URL is baked; burrow-boot.sh still PULLS all config + a
# short-lived, discarded git credential from the bootconfig endpoint at boot.
mkdir -p /etc/burrow
if [[ -n "${CONTROL_PLANE_URL:-}" ]]; then
  log "baking CONTROL_PLANE=${CONTROL_PLANE_URL} into /etc/burrow/worker.env"
  printf 'CONTROL_PLANE=%s\n' "$CONTROL_PLANE_URL" > /etc/burrow/worker.env
else
  log "WARNING: CONTROL_PLANE_URL not provided — worker.env left EMPTY."
  log "Workers will fail to boot (burrow-boot.sh requires CONTROL_PLANE) until the"
  log "template is rebuilt with CONTROL_PLANE_URL set."
  : > /etc/burrow/worker.env
fi
chmod 644 /etc/burrow/worker.env

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
