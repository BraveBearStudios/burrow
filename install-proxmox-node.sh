#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# install-proxmox-node.sh — one-shot Burrow host-prime for a Proxmox node.
#
# Orchestrates the numbered host-prime scripts (00 identity/role/ACL -> 10 template
# download -> 20 build golden template) in order, gathering topology either from
# the environment (non-interactive) or interactive prompts with auto-detected
# defaults. The numbered scripts remain the single source of truth; this is a thin
# wrapper that exports their config as env vars.
#
# Run as root@pam ON the Proxmox node you want to prime. Two ways:
#
#   # interactive (recommended): download then run
#   curl -fsSLO https://raw.githubusercontent.com/BraveBearStudios/burrow/main/install-proxmox-node.sh
#   bash install-proxmox-node.sh
#
#   # or pipe (prompts read from /dev/tty so this stays interactive)
#   curl -fsSL https://raw.githubusercontent.com/BraveBearStudios/burrow/main/install-proxmox-node.sh | bash
#
#   # fully non-interactive: set every value + ASSUME_YES=1
#   curl -fsSL .../install-proxmox-node.sh | \
#     NODE_NAME=pve1 ROOTFS_STORAGE=local-lvm TMPL_STORAGE=local \
#     BRIDGE=vmbr0 TEMPLATE_VMID=9000 WORKER_POOL_START=200 WORKER_POOL_END=299 \
#     WORKER_SUBNET=10.99.0.0 WORKER_GATEWAY=10.99.0.1 WORKER_PREFIX=24 \
#     PROXMOX_HOST=pve1.lan ALLOWED_ORIGIN=http://burrow.lan ASSUME_YES=1 bash
#
# The Proxmox token is the one high-value secret: 00 writes it ONCE to a gitignored
# .env and never echoes it. This wrapper never prints it either.

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/BraveBearStudios/burrow.git}"
REPO_BRANCH="${REPO_BRANCH:-main}"
INSTALL_DIR="${INSTALL_DIR:-/opt/burrow-src}"
ASSUME_YES="${ASSUME_YES:-0}"

c_blue=$'\033[1;34m'; c_yellow=$'\033[1;33m'; c_red=$'\033[1;31m'; c_off=$'\033[0m'
log()  { printf '%s==>%s %s\n' "$c_blue"   "$c_off" "$*" >&2; }
warn() { printf '%s!! %s %s\n' "$c_yellow" "$c_off" "$*" >&2; }
die()  { printf '%sXX %s %s\n' "$c_red"    "$c_off" "$*" >&2; exit 1; }

# Read from the terminal even when the script itself arrived on stdin (curl|bash).
TTY=/dev/tty
have_tty() { [[ -r "$TTY" ]]; }

# ask VAR "Prompt" "default" — env value wins; else ASSUME_YES takes the default;
# else prompt on /dev/tty. Never overwrites an already-set non-empty env var.
ask() {
  local var="$1" prompt="$2" def="${3:-}" cur="${!1:-}" ans
  if [[ -n "$cur" ]]; then printf -v "$var" '%s' "$cur"; return; fi
  if [[ "$ASSUME_YES" == "1" ]] || ! have_tty; then
    [[ -n "$def" ]] || die "no value for $var and no tty/ASSUME_YES — set $var in the environment"
    printf -v "$var" '%s' "$def"; return
  fi
  read -r -p "$prompt [$def]: " ans <"$TTY" || true
  printf -v "$var" '%s' "${ans:-$def}"
}

confirm() {
  local prompt="$1" ans
  [[ "$ASSUME_YES" == "1" ]] && return 0
  have_tty || die "cannot confirm without a tty — re-run with ASSUME_YES=1 if you accept"
  read -r -p "$prompt [y/N]: " ans <"$TTY" || true
  [[ "${ans,,}" == "y" || "${ans,,}" == "yes" ]]
}

# ── Preflight ──────────────────────────────────────────────────────────────
[[ "$(id -u)" == "0" ]] || die "run as root (root@pam) on the Proxmox node."
for c in pveum pveam pct pvesh git curl awk; do
  command -v "$c" >/dev/null 2>&1 || die "missing required command: $c (run this ON a Proxmox node)."
done
log "preflight OK — root, PVE tools, git/curl present."

# ── Locate or fetch the repo (for the host-prime scripts + worker payload) ──
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]:-.}")" 2>/dev/null && pwd || echo /nonexistent)"
if [[ -f "${script_dir}/cc-worker-config/lxc/host-prime/00-api-user-role.sh" ]]; then
  REPO_DIR="$script_dir"
  log "using the repo checkout at ${REPO_DIR}"
else
  if [[ -d "${INSTALL_DIR}/.git" ]]; then
    log "updating existing checkout at ${INSTALL_DIR}"
    git -C "$INSTALL_DIR" fetch --depth 1 origin "$REPO_BRANCH" && git -C "$INSTALL_DIR" checkout -q FETCH_HEAD
  else
    log "cloning ${REPO_URL} (${REPO_BRANCH}) to ${INSTALL_DIR}"
    git clone --depth 1 --branch "$REPO_BRANCH" "$REPO_URL" "$INSTALL_DIR"
  fi
  REPO_DIR="$INSTALL_DIR"
fi
HP="${REPO_DIR}/cc-worker-config/lxc/host-prime"
[[ -f "${HP}/00-api-user-role.sh" ]] || die "host-prime scripts not found under ${HP}"

# ── Auto-detect sane defaults ──────────────────────────────────────────────
det_node="$(hostname -s)"
det_thin="$(pvesm status -content rootdir 2>/dev/null | awk 'NR>1 && ($2=="lvmthin"||$2=="zfspool"){print $1; exit}')"
det_vztmpl="$(pvesm status -content vztmpl 2>/dev/null | awk 'NR>1{print $1; exit}')"
det_bridge="$(ip -br link show type bridge 2>/dev/null | awk '{print $1; exit}')"
det_tmpl="$(pveam available --section system 2>/dev/null | awk '/ubuntu-24.04-standard/{print $2}' | sort -V | tail -1)"

# ── Gather config ──────────────────────────────────────────────────────────
log "gather configuration (Enter accepts the [detected default])"
ask NODE_NAME       "Proxmox node to prime"                 "$det_node"
ask ROOTFS_STORAGE  "THIN rootfs storage (lvmthin/zfspool)" "${det_thin:-local-lvm}"
ask TMPL_STORAGE    "vztmpl storage (dir/NFS)"              "${det_vztmpl:-local}"
ask BRIDGE          "LAN bridge"                            "${det_bridge:-vmbr0}"
ask TMPL            "Ubuntu CT build string"                "${det_tmpl:-ubuntu-24.04-standard_24.04-2_amd64.tar.zst}"
ask TEMPLATE_VMID   "Golden template VMID (outside worker range)" "9000"
ask WORKER_POOL_START "Worker VMID range start"             "200"
ask WORKER_POOL_END   "Worker VMID range end"               "299"
ask WORKER_SUBNET   "Worker subnet (network address)"       "10.99.0.0"
ask WORKER_PREFIX   "Worker subnet prefix length"           "24"
ask WORKER_GATEWAY  "Worker gateway IP"                     "10.99.0.1"
ask PROXMOX_HOST    "Proxmox API host for the control plane" "${det_node}.lan"
ask ALLOWED_ORIGIN  "Control-plane UI origin (tool server)" "http://burrow.lan"
ROOTFS_SIZE="${ROOTFS_SIZE:-8}"

# ── Validate ───────────────────────────────────────────────────────────────
[[ "$TEMPLATE_VMID" =~ ^[0-9]+$ ]]     || die "TEMPLATE_VMID must be numeric."
[[ "$WORKER_POOL_START" =~ ^[0-9]+$ && "$WORKER_POOL_END" =~ ^[0-9]+$ ]] || die "worker range must be numeric."
(( WORKER_POOL_START < WORKER_POOL_END )) || die "WORKER_POOL_START must be < WORKER_POOL_END."
if (( TEMPLATE_VMID >= WORKER_POOL_START && TEMPLATE_VMID <= WORKER_POOL_END )); then
  die "TEMPLATE_VMID ${TEMPLATE_VMID} is INSIDE the worker range ${WORKER_POOL_START}-${WORKER_POOL_END} — pick one outside it."
fi
[[ "$TMPL" != *"<ver>"* ]] || die "TMPL still has the <ver> placeholder — set the exact build string."
pvesm status 2>/dev/null | awk 'NR>1{print $1}' | grep -qx "$ROOTFS_STORAGE" || warn "storage '${ROOTFS_STORAGE}' not in pvesm status — double-check the ID."
pvesm status 2>/dev/null | awk 'NR>1{print $1}' | grep -qx "$TMPL_STORAGE"   || warn "storage '${TMPL_STORAGE}' not in pvesm status — double-check the ID."

# ── Summary + go/no-go ─────────────────────────────────────────────────────
cat >&2 <<SUMMARY

${c_blue}Burrow host-prime plan — node ${NODE_NAME}${c_off}
  Golden template VMID : ${TEMPLATE_VMID}   build: ${TMPL}
  Template rootfs (thin): ${ROOTFS_STORAGE}   vztmpl store: ${TMPL_STORAGE}
  LAN bridge           : ${BRIDGE}
  Worker VMID range    : ${WORKER_POOL_START}-${WORKER_POOL_END}
  Worker network       : ${WORKER_SUBNET}/${WORKER_PREFIX}  gw ${WORKER_GATEWAY}
  Control-plane host   : ${PROXMOX_HOST}   UI origin: ${ALLOWED_ORIGIN}

Runs (in order): 00 token/role/ACL -> 10 template download -> 20 build template.
The token is written ONCE to ${REPO_DIR}/.env (0600, gitignored) and never echoed.
SUMMARY

warn "LOAD-BEARING: the worker IP range (${WORKER_SUBNET}/${WORKER_PREFIX}, VMIDs ${WORKER_POOL_START}-${WORKER_POOL_END}) MUST be excluded from your LAN DHCP pool. Proxmox does not enforce this."
confirm "Proceed with host-prime on ${NODE_NAME}?" || die "aborted by operator — nothing changed."

# ── Run the numbered scripts ───────────────────────────────────────────────
export NODE_NAME ROOTFS_STORAGE TMPL_STORAGE TEMPLATE_VMID BRIDGE ROOTFS_SIZE TMPL
export ENV_FILE="${REPO_DIR}/.env"

run_step() {
  local script="$1" label="$2"
  log "STEP ${label}: ${script}"
  if have_tty; then bash "${HP}/${script}" <"$TTY"; else bash "${HP}/${script}"; fi
}
run_step 00-api-user-role.sh   "0 (identity/role/ACL)"
run_step 10-template-download.sh "2a (template download)"
run_step 20-create-template.sh  "2b (build golden template)"

# ── Emit a clean control-plane.env for the tool server ─────────────────────
# No inline comments / quotes: docker compose env_file passes values literally.
CP_ENV="${REPO_DIR}/control-plane.env"
umask 077
cat > "$CP_ENV" <<ENV
PROXMOX_HOST=${PROXMOX_HOST}
PROXMOX_USER=burrow@pve
PROXMOX_TOKEN_NAME=burrow
PROXMOX_TOKEN_VALUE=
PROXMOX_CA_CERT_PATH=/etc/burrow/pve-ca.pem
CONFIG_REPO=${REPO_URL}
CONFIG_BRANCH=${REPO_BRANCH}
TEMPLATE_VMID=${TEMPLATE_VMID}
WORKER_POOL_START=${WORKER_POOL_START}
WORKER_POOL_END=${WORKER_POOL_END}
DEFAULT_NODE=${NODE_NAME}
WORKER_SUBNET=${WORKER_SUBNET}/${WORKER_PREFIX}
WORKER_GATEWAY=${WORKER_GATEWAY}
WORKER_BRIDGE=${BRIDGE}
WORKER_PREFIX=${WORKER_PREFIX}
CAPACITY_THRESHOLD=0.80
TTYD_TIMEOUT=60
TTYD_INTERVAL=2
CLONE_TIMEOUT=300
TASK_TIMEOUT=120
ALLOWED_ORIGIN=${ALLOWED_ORIGIN}
GIT_CREDENTIAL_TOKEN=
BOOTCONFIG_SOURCE_IP_CHECK=false
DATABASE_PATH=/data/burrow.db
ENV

log "host-prime complete on ${NODE_NAME}."
cat >&2 <<NEXT

${c_blue}Next — on the Ubuntu tool server (same LAN):${c_off}
  1. Copy the token (from ${REPO_DIR}/.env, key PROXMOX_TOKEN_VALUE) somewhere safe.
  2. Copy ${CP_ENV} to the tool server as /opt/burrow/.env, then add the
     PROXMOX_TOKEN_VALUE line (the token from step 1).
  3. Place the node CA cert at /etc/burrow/pve-ca.pem on the tool server.
  4. git clone ${REPO_URL} && cd burrow && sudo chown -R 10001:10001 /data
  5. docker compose -f compose.prod.yml up -d --build
  6. Browse http://${PROXMOX_HOST}/ -> the first-run setup wizard.

${c_yellow}Reminder:${c_off} confirm the worker range is excluded from DHCP before the first workspace boots.
NEXT
