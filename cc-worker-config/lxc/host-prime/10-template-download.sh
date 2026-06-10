#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# 10-template-download.sh — Day-0 STEP 2a: fetch the Ubuntu 24.04 CT template.
#
# Refreshes the appliance DB and downloads the Ubuntu 24.04 standard CT template
# into a vztmpl (dir-type) storage. Idempotent and non-destructive: the download
# is skipped if the pinned build is already present, and the build string is
# pinned so a re-run can never silently swap versions.
#
# Run as root@pam on the node that will host the golden template.
# Source: .planning/research/PROXMOX-PRIMING.md §3.1.
# All topology is a placeholder; fill your values before running.

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${HERE}/lib/common.sh"

# ---------------------------------------------------------------------------
# Configuration (placeholders).
# ---------------------------------------------------------------------------
NODE_NAME="<node>"                 # the node this runs on
TMPL_STORAGE="<tmpl-storage>"      # a dir-type storage that carries vztmpl content
# Pin the EXACT build string. Discover the current one with:
#   pveam available --section system | grep ubuntu-24.04-standard
# then paste the full filename here so a re-run is reproducible.
TMPL="ubuntu-24.04-standard_<ver>_amd64.tar.zst"

# ---------------------------------------------------------------------------
# Preflight.
# ---------------------------------------------------------------------------
require_root
require_cmd pveam
require_node "$NODE_NAME"

if [[ "$TMPL" == *"<ver>"* ]]; then
  log "TMPL still has the <ver> placeholder. Discover the exact build with:"
  log "  pveam available --section system | grep ubuntu-24.04-standard"
  log "then pin it in this script. Refusing to download an unpinned template."
  exit 1
fi

# ---------------------------------------------------------------------------
# 1. Refresh the appliance DB (idempotent).
# ---------------------------------------------------------------------------
log "pveam update (refresh appliance database)"
pveam update

# Sanity: confirm the pinned build is actually offered upstream before download.
if ! pveam available --section system | grep -q "$TMPL"; then
  log "pinned template '$TMPL' is not in 'pveam available' output."
  log "Re-pin TMPL to a current build; the pinned version may have rotated out."
  exit 1
fi

# ---------------------------------------------------------------------------
# 2. Download only if absent (check -> act; non-destructive — adds a file).
# ---------------------------------------------------------------------------
if pveam list "$TMPL_STORAGE" | grep -q "$TMPL"; then
  log "template '$TMPL' already present on '$TMPL_STORAGE' -> skip download"
else
  log "downloading '$TMPL' to '$TMPL_STORAGE'"
  pveam download "$TMPL_STORAGE" "$TMPL"
fi

log "STEP 2a complete. Template available on '$TMPL_STORAGE': $TMPL"

# ---------------------------------------------------------------------------
# ## Reversal
# Remove the downloaded template image (frees the vztmpl file, non-destructive
# to any running CT):
#   pveam remove <tmpl-storage>:vztmpl/ubuntu-24.04-standard_<ver>_amd64.tar.zst
# ---------------------------------------------------------------------------
