#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# burrow-boot.sh — WORK-04: worker boot orchestration.
#
# Runs on every workspace boot via burrow-worker.service. Pulls its non-secret
# boot config (pull-at-boot, SC-4/SC-5) from the control plane, optionally clones
# the config + project repos, then launches a PERSISTENT, LAN-bound ttyd that
# the control-plane WS proxy reaches over the worker's network address.
#
# Frozen decisions (each has an ADR):
#   - ttyd is PERSISTENT — NO `--once` (SC-8 / ADR-0006): closing a browser tab
#     DETACHES; it must never terminate the live Claude session. Destroy is the
#     only kill path.
#   - ttyd binds the worker LAN interface (--interface 0.0.0.0), NOT `lo`
#     (SC-9 / ADR-0007 / WORK-04): the proxy must reach :7681 over the LAN.
#   - boot config is PULLED AT BOOT, not injected by cloud-init / pct push
#     (ADR-0002): no secret is ever written to /etc/burrow/worker.env.
#
# Source: .planning/.../00-RESEARCH.md §Golden Template & Boot (SC-corrected).
set -euo pipefail

log() { echo "[burrow-boot] $*"; }

# --- Pull-at-boot config fetch (STUB — real impl Phase 3) --------------------
# The worker knows its own VMID (derived from its hostname / static IP, SC-6).
# At boot it will:
#   1. GET <CONTROL_PLANE>/api/v1/internal/bootconfig/<vmid>  -> non-secret config
#      (CONFIG_REPO, CONFIG_BRANCH, PROJECT_REPO, PROJECT_BRANCH).
#   2. Request a SHORT-LIVED, repo-scoped git credential, use it for the clone,
#      and DISCARD it — NEVER written to /etc/burrow/worker.env (secrets stay off
#      the worker env, SC-4 / Pitfall 13).
# Phase 0 leaves the fetch + auth a documented stub; the control-plane bootconfig
# endpoint contract lands Phase 1 and the live fetch lands Phase 3.
CONTROL_PLANE="${CONTROL_PLANE:?CONTROL_PLANE must be set (e.g. http://<control-plane>:8000)}"

# TODO(Phase 3): replace the env-var defaults below with the live pull:
#   1. VMID="$(resolve_vmid_from_hostname)"
#   2. curl -fsSL "${CONTROL_PLANE}/api/v1/internal/bootconfig/${VMID}" -> CONFIG_*/PROJECT_*
#   3. obtain + use + discard a short-lived git credential for the clones below.
log "pull-at-boot fetch is a Phase-3 stub; reading boot config from env for now"
log "control plane: ${CONTROL_PLANE}"

CONFIG_REPO="${CONFIG_REPO:-}"
CONFIG_BRANCH="${CONFIG_BRANCH:-main}"
PROJECT_REPO="${PROJECT_REPO:-}"
PROJECT_BRANCH="${PROJECT_BRANCH:-main}"
WORKER_HOME="/root"
PROJECT_DIR="${WORKER_HOME}/project"

# --- Config + project pull (auth filled Phase 3) -----------------------------
if [[ -n "$CONFIG_REPO" ]]; then
  log "cloning config repo (${CONFIG_BRANCH})"
  git clone --depth=1 --branch "$CONFIG_BRANCH" "$CONFIG_REPO" /tmp/cc-worker-config
  cp /tmp/cc-worker-config/claude/CLAUDE.md "${WORKER_HOME}/CLAUDE.md"
  mkdir -p "${WORKER_HOME}/.claude/plugins"
  cp -r /tmp/cc-worker-config/plugins/. "${WORKER_HOME}/.claude/plugins/"
fi

if [[ -n "$PROJECT_REPO" ]]; then
  log "cloning project repo (${PROJECT_BRANCH})"
  git clone --branch "$PROJECT_BRANCH" "$PROJECT_REPO" "$PROJECT_DIR"
fi

# --- Pick the Claude launch command ------------------------------------------
CLAUDE_CMD="claude"
if command -v rtk >/dev/null 2>&1; then
  CLAUDE_CMD="rtk claude"
fi

# --- Working directory for the session ---------------------------------------
# Land in the cloned project if there is one; otherwise the worker home.
START_DIR="$WORKER_HOME"
if [[ -n "$PROJECT_REPO" ]]; then
  START_DIR="$PROJECT_DIR"
fi

# --- ttyd: PERSISTENT (no --once, SC-8) + LAN bind (no `lo`, SC-9 / WORK-04) --
# --interface 0.0.0.0 exposes :7681 on the worker LAN address so the proxy can
# reach it; the LAN boundary + least privilege are the v1 controls (LAN-only,
# no auth — ADR-0007). NO --once: tab close detaches, never terminates.
log "starting persistent LAN-bound ttyd on :7681 (cmd: ${CLAUDE_CMD}, cwd: ${START_DIR})"
exec ttyd \
  --port 7681 \
  --writable \
  --interface 0.0.0.0 \
  bash -lc "cd '${START_DIR}' && exec ${CLAUDE_CMD}"
