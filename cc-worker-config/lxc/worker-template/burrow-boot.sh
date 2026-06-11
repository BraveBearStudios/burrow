#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# burrow-boot.sh — WORK-02/04: live pull-at-boot worker orchestration.
#
# Runs on every workspace boot via burrow-worker.service. Self-resolves its VMID,
# bounded-retries the FROZEN control-plane bootconfig endpoint, clones the config
# + project repos with a SHORT-LIVED credential that never touches disk, copies
# the master CLAUDE.md, then execs a PERSISTENT, LAN-bound ttyd the WS proxy
# reaches over the worker's network address.
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
# Credential hygiene (SC-3, T-03-01..04): the minted git credential is fed to
# `git clone` via an in-memory GIT_ASKPASS helper inside a SUBSHELL — never in a
# clone URL (leaks via `ps`/reflog/.git/config), never on disk, never in
# /etc/burrow/worker.env, unset after the clones. There is NO `set -x` anywhere
# (it would echo the token). The ERR trap redacts $BASH_COMMAND as a backstop;
# the real guarantee is structural (the token only ever lives in a subshell-local
# env var). The boot-harness scrub-proof test (api/tests/boot/) proves both.
#
# Source: 03-RESEARCH.md Patterns 1-3 + 03-PATTERNS.md (mirrors host-prime/lib/common.sh).
set -euo pipefail

# Logs go to STDERR so stdout stays clean for data captured via command
# substitution (fetch_bootconfig echoes the .data JSON on stdout). Mirrors
# host-prime/lib/common.sh log().
log() { echo "[burrow-boot] $*" >&2; }

# ERR trap (mirror host-prime/lib/common.sh) + secret redaction backstop. The
# token can never appear in $BASH_COMMAND in the first place (it lives only in a
# subshell-local env var), so this scrub is defense-in-depth (RESEARCH Pattern 3).
# shellcheck disable=SC2154  # BASH_COMMAND/LINENO are bash built-ins.
err_trap() {
  local exit_code=$?
  local cmd="${BASH_COMMAND//ghp_*/[redacted]}"
  printf '[burrow-boot] ERROR (exit %d) at %s:%d: %s\n' \
    "$exit_code" "${BASH_SOURCE[0]:-?}" "${BASH_LINENO[0]:-0}" "$cmd" >&2
  exit "$exit_code"
}
trap err_trap ERR

# Test/override seams (operator/CI config, NEVER client input): BURROW_HOSTNAME
# lets the hermetic harness drive resolve_vmid without a real hostname; BURROW_ETC
# relocates the worker env dir off the real /etc/burrow under a temp root. Both
# default to the real worker values, so production behaviour is unchanged.
BURROW_ETC="${BURROW_ETC:-/etc/burrow}"
WORKER_HOME="${HOME:-/root}"
PROJECT_DIR="${WORKER_HOME}/project"

# --- VMID self-resolution (ADR-0004) -----------------------------------------
# The worker resolves its own VMID from its hostname; the control plane keys the
# bootconfig endpoint off that VMID. The AUTHORITATIVE VMID<->static-IP mapping is
# operator-recorded in cc-worker-config/lxc/host-prime/30-network-notes.md — the
# hostname-suffix parse below is [ASSUMED] (confirm at the dev-homelab smoke,
# Pitfall 4). A non-integer suffix returns non-zero (ERR trap → fast non-zero).
resolve_vmid() {
  local host vmid
  host="${BURROW_HOSTNAME:-$(hostname -s)}"
  vmid="${host##*-}"
  [[ "$vmid" =~ ^[0-9]+$ ]] || { log "cannot resolve VMID from hostname '${host}'"; return 1; }
  printf '%s\n' "$vmid"
}

# --- Bounded-retry bootconfig fetch (RESEARCH Pattern 2) ---------------------
# ~5 attempts with capped backoff, then fail non-zero (a transient CP blip must
# not abort an otherwise-good boot, but a real outage must surface — never hang).
# Echoes the unwrapped .data JSON on stdout. A 404 (out-of-pool / no workspace)
# is caught by curl -f. The credential is in .data.gitCredential — read it from
# the returned JSON, never log it.
fetch_bootconfig() {
  local cp="$1" vmid="$2" attempt=0 max=5 delay=1 body
  while (( attempt < max )); do
    attempt=$((attempt + 1))
    if body="$(curl -fsS --max-time 10 "${cp}/api/v1/internal/bootconfig/${vmid}")" \
       && jq -e '.data' <<<"$body" >/dev/null 2>&1; then
      jq -c '.data' <<<"$body"
      return 0
    fi
    log "bootconfig attempt ${attempt}/${max} failed; retrying in ${delay}s"
    sleep "$delay"
    delay=$(( delay * 2 > 30 ? 30 : delay * 2 ))
  done
  log "bootconfig fetch exhausted ${max} attempts — failing boot"
  return 1
}

# --- Leak-proof clone with an in-memory one-shot credential (RESEARCH Pattern 1)
# clone_with_token <token> <url> <dest> [extra git args...]
# The token is fed to git via GIT_ASKPASS inside a SUBSHELL, so it can never
# escape to the parent env, a command line, the clone URL, or /etc/burrow/worker.env.
# x-access-token is the GitHub App installation-token / fine-grained PAT convention
# ([ASSUMED] per A2/A3 — the operator's mint mechanism is pending; confirm at smoke).
clone_with_token() {
  local token="$1" url="$2" dest="$3"; shift 3
  (
    export GIT_ASKPASS_TOKEN="$token"
    local askpass; askpass="$(mktemp)"
    export GIT_ASKPASS="$askpass"
    cat >"$askpass" <<'ASK'
#!/usr/bin/env bash
case "$1" in
  Username*) printf 'x-access-token\n' ;;
  *)         printf '%s\n' "$GIT_ASKPASS_TOKEN" ;;
esac
ASK
    chmod 700 "$askpass"
    # GIT_TERMINAL_PROMPT=0 → a bad/missing credential fails fast (no TTY hang,
    # Pitfall 3). credential.helper= (empty) disables any inherited store so the
    # token is never persisted. The URL carries NO credential.
    local rc=0
    GIT_TERMINAL_PROMPT=0 git -c credential.helper= clone "$@" "$url" "$dest" || rc=$?
    rm -f "$askpass"
    return "$rc"
  )
}

# --- Live pull-at-boot --------------------------------------------------------
# CONTROL_PLANE is now REQUIRED (the Phase-0 warn-and-skip is gone): the live
# fetch depends on it, so a missing value must fail the boot rather than launch
# an unconfigured ttyd.
: "${CONTROL_PLANE:?CONTROL_PLANE must be set for the pull-at-boot fetch}"

VMID="$(resolve_vmid)"
log "resolved VMID ${VMID}; fetching bootconfig from the control plane"

BOOTCONFIG="$(fetch_bootconfig "$CONTROL_PLANE" "$VMID")"
CONFIG_REPO="$(jq -r '.configRepo' <<<"$BOOTCONFIG")"
CONFIG_BRANCH="$(jq -r '.configBranch' <<<"$BOOTCONFIG")"
PROJECT_REPO="$(jq -r '.projectRepo' <<<"$BOOTCONFIG")"
PROJECT_BRANCH="$(jq -r '.projectBranch' <<<"$BOOTCONFIG")"
# The short-lived credential: held in a shell-local ONLY, never logged, never
# written to BURROW_ETC/worker.env, and unset the instant the clones are done.
GIT_CRED="$(jq -r '.gitCredential' <<<"$BOOTCONFIG")"
unset BOOTCONFIG

# Config repo: master CLAUDE.md + the plugin manifest (manifest processing lands
# in Plan 02). Assume cc-worker-config is operator-reachable (A5/Open-Q-1); if it
# needs separate auth that is an operator-contract question, not a code change here.
log "cloning config repo (branch ${CONFIG_BRANCH})"
rm -rf /tmp/cc-worker-config
clone_with_token "$GIT_CRED" "$CONFIG_REPO" /tmp/cc-worker-config \
  --depth=1 --branch "$CONFIG_BRANCH"
cp /tmp/cc-worker-config/claude/CLAUDE.md "${WORKER_HOME}/CLAUDE.md"

log "cloning project repo (branch ${PROJECT_BRANCH})"
rm -rf "$PROJECT_DIR"
clone_with_token "$GIT_CRED" "$PROJECT_REPO" "$PROJECT_DIR" \
  --branch "$PROJECT_BRANCH"

# Discard the credential: it is gone from this process from here on.
unset GIT_CRED

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
