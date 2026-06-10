#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# 20-create-template.sh — Day-0 STEP 2b: build the golden worker template.
#
# Creates an unprivileged, nesting-enabled CT from the downloaded Ubuntu 24.04
# template on a thin rootfs storage, copies the worker-template payload into it,
# runs the in-CT provisioner (Node 22 + claude-code + ttyd + boot unit), then
# converts the CT to a template with `pct template`.
#
# Clones from a CT *template* default to LINKED; Burrow clones --full at runtime,
# so the template MUST live on thin storage (lvmthin/zfspool) to keep --full
# clones cheap. unprivileged=1 + nesting=1 lets systemd + Node sandboxing work
# inside the worker; clones inherit `features`, so set it once here.
#
# The worker-template payload (provision-template.sh, burrow-boot.sh,
# /tmp/plugins) is authored in Plan 07 under cc-worker-config/lxc/worker-template/;
# the burrow-worker.service unit lives under cc-worker-config/systemd/. This
# script references both by path.
#
# Run as root@pam on the template's node.
# Source: .planning/research/PROXMOX-PRIMING.md §3.2, §3.3.
# All topology is a placeholder; fill your values before running.

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${HERE}/lib/common.sh"

# ---------------------------------------------------------------------------
# Configuration (placeholders).
# ---------------------------------------------------------------------------
NODE_NAME="<node>"
TEMPLATE_VMID="<template-vmid>"           # OUTSIDE the worker VMID range (see 30-network-notes.md)
TMPL_STORAGE="<tmpl-storage>"             # dir storage holding the vztmpl from step 10
ROOTFS_STORAGE="<rootfs-storage>"         # THIN storage (lvmthin/zfspool) — NOT thick LVM
ROOTFS_SIZE="8"                           # GiB; thin so unwritten blocks cost nothing
BRIDGE="<bridge>"                         # the LAN bridge
TMPL="ubuntu-24.04-standard_<ver>_amd64.tar.zst"   # match step 10's pin

# Worker-template payload authored in Plan 07. Adjust if your layout differs.
WT_DIR="${HERE}/../worker-template"
PROVISIONER="${WT_DIR}/provision-template.sh"
BOOT_SCRIPT="${WT_DIR}/burrow-boot.sh"
WORKER_UNIT="${HERE}/../../systemd/burrow-worker.service"
PLUGINS_DIR="${WT_DIR}/plugins"

# ---------------------------------------------------------------------------
# Preflight.
# ---------------------------------------------------------------------------
require_root
require_cmd pct pveam
require_node "$NODE_NAME"

for placeholder in "$TEMPLATE_VMID" "$ROOTFS_STORAGE" "$TMPL_STORAGE" "$BRIDGE"; do
  if [[ "$placeholder" == "<"*">" ]]; then
    log "unfilled placeholder '$placeholder' — fill the config block before running"
    exit 1
  fi
done

# ---------------------------------------------------------------------------
# 1. Create the CT (check -> act). On a pre-existing VMID, confirm before
#    destroying so a re-run cannot silently nuke a template in use.
# ---------------------------------------------------------------------------
if pct status "$TEMPLATE_VMID" >/dev/null 2>&1; then
  log "VMID $TEMPLATE_VMID already exists."
  if confirm "Destroy existing CT/template $TEMPLATE_VMID and rebuild it?"; then
    pct stop "$TEMPLATE_VMID" 2>/dev/null || true
    pct destroy "$TEMPLATE_VMID"
  else
    log "keeping existing $TEMPLATE_VMID -> nothing to do"
    exit 0
  fi
fi

log "creating unprivileged + nesting CT $TEMPLATE_VMID on thin storage '$ROOTFS_STORAGE'"
pct create "$TEMPLATE_VMID" "${TMPL_STORAGE}:vztmpl/${TMPL}" \
  --hostname burrow-template \
  --unprivileged 1 \
  --features nesting=1 \
  --rootfs "${ROOTFS_STORAGE}:${ROOTFS_SIZE}" \
  --net0 "name=eth0,bridge=${BRIDGE},ip=dhcp" \
  --cores 2 \
  --memory 2048 \
  --onboot 0

# ---------------------------------------------------------------------------
# 2. Copy the worker-template payload into the CT, then provision in-place.
#    pct push/exec are node-local CLI (no API) — fine here on the host.
# ---------------------------------------------------------------------------
if [[ ! -f "$PROVISIONER" ]]; then
  log "provisioner not found at '$PROVISIONER' (authored in Plan 07)."
  log "CT $TEMPLATE_VMID was created but NOT provisioned. Add the worker-template"
  log "payload, then re-run this script (it will prompt to rebuild)."
  exit 1
fi

log "starting CT to run the in-CT provisioner"
pct start "$TEMPLATE_VMID"
# Brief settle for networking before apt; the provisioner itself retries.
sleep 5

log "pushing worker-template payload into the CT"
pct push "$TEMPLATE_VMID" "$PROVISIONER" /tmp/provision-template.sh --perms 755
[[ -f "$BOOT_SCRIPT" ]]  && pct push "$TEMPLATE_VMID" "$BOOT_SCRIPT"  /tmp/burrow-boot.sh --perms 755
[[ -f "$WORKER_UNIT" ]]  && pct push "$TEMPLATE_VMID" "$WORKER_UNIT"  /tmp/burrow-worker.service --perms 644
if [[ -d "$PLUGINS_DIR" ]]; then
  pct exec "$TEMPLATE_VMID" -- mkdir -p /tmp/plugins
  # Copy each plugin file in; pct push is per-file.
  find "$PLUGINS_DIR" -type f -print0 | while IFS= read -r -d '' f; do
    rel="${f#"$PLUGINS_DIR"/}"
    pct exec "$TEMPLATE_VMID" -- mkdir -p "/tmp/plugins/$(dirname "$rel")"
    pct push "$TEMPLATE_VMID" "$f" "/tmp/plugins/$rel"
  done
fi

log "running provisioner inside CT $TEMPLATE_VMID"
pct exec "$TEMPLATE_VMID" -- bash /tmp/provision-template.sh

# ---------------------------------------------------------------------------
# 3. Stop, then convert to a template (the linked-clone-default applies only to
#    template-marked CTs; this is what makes runtime clones cheap).
# ---------------------------------------------------------------------------
log "stopping CT before template conversion"
pct stop "$TEMPLATE_VMID"

log "converting CT $TEMPLATE_VMID to a template"
pct template "$TEMPLATE_VMID"

log "STEP 2b complete. Golden template ready at VMID $TEMPLATE_VMID."
log "Phase-0 manual gate: clone once by hand --full, start, confirm ttyd on the"
log "LAN interface + 'claude' launches, then destroy the test clone."

# ---------------------------------------------------------------------------
# ## Reversal
# Destroy the golden template (does NOT touch running worker clones):
#   pct destroy <template-vmid>
# The downloaded vztmpl image is reversed separately by 10-template-download.sh.
# ---------------------------------------------------------------------------
