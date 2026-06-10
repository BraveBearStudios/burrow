#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# common.sh — shared strict-mode + preflight guards for the host-prime kit.
#
# Source this from every numbered script:  source "$(dirname "$0")/lib/common.sh"
# It sets strict mode, installs an ERR trap that names the failing line, and
# exposes the require_* guards so a wrong-host or missing-tool run aborts having
# changed nothing (PROXMOX-PRIMING.md §6).

set -euo pipefail
IFS=$'\n\t'

# Print the failing command + line number on any non-zero exit (set -e).
# shellcheck disable=SC2154  # BASH_COMMAND/LINENO are bash built-ins.
err_trap() {
  local exit_code=$?
  printf 'ERROR: command failed (exit %d) at %s:%d: %s\n' \
    "$exit_code" "${BASH_SOURCE[1]:-?}" "${BASH_LINENO[0]:-0}" "${BASH_COMMAND}" >&2
  exit "$exit_code"
}
trap err_trap ERR

# log <message...> — structured-ish stderr line so stdout stays clean for data.
log() {
  printf '[host-prime] %s\n' "$*" >&2
}

# require_root — abort unless running as uid 0 (pveum/pct/pveam need root@pam).
require_root() {
  if [[ "$(id -u)" -ne 0 ]]; then
    log "must run as root (root@pam on the Proxmox node)"
    exit 1
  fi
}

# require_cmd <cmd...> — abort if any named command is missing from PATH.
require_cmd() {
  local missing=0 cmd
  for cmd in "$@"; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
      log "missing required command: $cmd"
      missing=1
    fi
  done
  [[ "$missing" -eq 0 ]] || exit 1
}

# require_node <node> — abort unless this host is the expected Proxmox node, so a
# script run on the wrong node aborts before mutating anything.
require_node() {
  local want="$1" have
  if [[ -z "$want" || "$want" == "<node>" ]]; then
    log "require_node: refusing to run with an unfilled <node> placeholder"
    exit 1
  fi
  have="$(hostname -s 2>/dev/null || hostname)"
  if [[ "$have" != "$want" ]]; then
    log "wrong node: this host is '$have', expected '$want'"
    exit 1
  fi
}

# confirm <prompt> — typed-yes gate for destructive steps. Returns non-zero on
# anything other than an exact "yes" so callers can guard with `confirm ... || ...`.
confirm() {
  local prompt="$1" answer
  read -rp "$prompt [type 'yes' to proceed]: " answer
  [[ "$answer" == "yes" ]]
}
