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
#
# redact_secrets <text> — strip credential-shaped substrings, format-aware + exact.
# Pure (no globals beyond GIT_CRED), so it is unit-testable in isolation. Layer 1
# redacts the LIVE credential value exactly when $GIT_CRED is in scope (format-
# agnostic, the real backstop). Layer 2 is a format-aware net for the credential
# shapes this design mints (x-access-token / ghs_ / github_pat_) plus the legacy
# gh*_ prefixes, in case a future refactor puts a token on a command line before
# $GIT_CRED is set. Each Layer-2 pattern is BOUNDED to the token's own characters
# (extglob `+(...)`) so it stops at a token boundary rather than swallowing the rest
# of the line — the over-greedy `ghp_*` glob bug this replaces.
redact_secrets() {
  local cmd="$1"
  shopt -s extglob
  if [[ -n "${GIT_CRED:-}" ]]; then
    cmd="${cmd//${GIT_CRED}/[redacted]}"
  fi
  cmd="${cmd//github_pat_+([A-Za-z0-9_])/[redacted]}"
  cmd="${cmd//ghs_+([A-Za-z0-9])/[redacted]}"
  cmd="${cmd//gho_+([A-Za-z0-9])/[redacted]}"
  cmd="${cmd//ghp_+([A-Za-z0-9])/[redacted]}"
  cmd="${cmd//x-access-token:+([^[:space:]])/x-access-token:[redacted]}"
  printf '%s' "$cmd"
}

# shellcheck disable=SC2154  # BASH_COMMAND/LINENO are bash built-ins.
err_trap() {
  local exit_code=$?
  local cmd; cmd="$(redact_secrets "${BASH_COMMAND}")"
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

# --- claude-plugin install: pinned clone + settings enable (RESEARCH Pattern 4)
# install_claude_plugin <name> <source> <ref>
# Idempotent by construction: rm -rf the dest then `git clone --depth=1 --branch
# <ref>` of the IMMUTABLE ref, so two boots of the same manifest produce a
# byte-identical plugin tree (SC-2, Pitfall 1). `source` may already carry a
# scheme (e.g. a file:// hermetic test remote); a bare host/path gets https://
# (the production github.com/<org>/<repo> form). The plugin is then enabled in
# the user settings.
#
# [ASSUMED] (A1 / Open-Q-2): the enabledPlugins[<name>]=true shape in
# ~/.claude/settings.json is the directory-install enablement key for
# claude-code@2.1.170 — CONFIRM at the dev-homelab smoke (`claude plugin list` /
# `--debug`). The master CLAUDE.md copy is independent and works regardless.
install_claude_plugin() {
  local name="$1" source="$2" ref="$3"
  local dest="${WORKER_HOME}/.claude/plugins/${name}"
  local url="$source"
  [[ "$source" == *://* ]] || url="https://${source}"

  log "installing claude-plugin '${name}' @ ${ref} (pinned, idempotent)"
  rm -rf "$dest"
  mkdir -p "${WORKER_HOME}/.claude/plugins"
  # Same hardening as clone_with_token: GIT_TERMINAL_PROMPT=0 → a private repo /
  # transient 401 fails FAST instead of hanging on a (nonexistent) TTY under
  # systemd, and credential.helper= (empty) disables any inherited store. This
  # makes the plugin clone fail-fast independent of the ambient environment
  # rather than relying on the test harness exporting GIT_TERMINAL_PROMPT.
  GIT_TERMINAL_PROMPT=0 git -c credential.helper= \
    clone --depth=1 --branch "$ref" "$url" "$dest"

  # Enable in the user settings.json (create {} if absent). enabledPlugins is
  # keyed by plugin name; see the [ASSUMED] note above.
  local settings="${WORKER_HOME}/.claude/settings.json"
  [[ -f "$settings" ]] || echo '{}' >"$settings"
  local tmp; tmp="$(mktemp)"
  jq --arg n "$name" '.enabledPlugins[$n] = true' "$settings" >"$tmp" && mv "$tmp" "$settings"
}

# --- Manifest processing: fail-closed jq gate + claude-plugin-only install ----
# process_manifest <manifest.json>
# A structural jq gate that MUST enforce the SAME required-keys + type enum as
# cc-worker-config/plugins/manifest.schema.json (the single source of truth) so
# CI and boot never diverge: every entry needs string source/ref/type and
# type ∈ {claude-plugin,binary,npm-global}. An unknown/unsupported type or a
# missing key fails the gate → `return 1` → the ERR trap fires → non-zero boot
# (fail-closed, the locked decision — never skip-and-continue).
#
# Only `type=="claude-plugin"` entries are pulled fresh at boot; `binary` and
# `npm-global` are baked into the golden template at provision time and SKIPPED.
process_manifest() {
  local manifest="$1"
  if [[ ! -f "$manifest" ]]; then
    log "manifest not found at ${manifest} — failing boot"
    return 1
  fi
  # Structural gate at PARITY with manifest.schema.json (the single source of
  # truth) so CI and boot never diverge. Mirrors, in jq:
  #   - required top-level: schemaVersion (string) + plugins (object)
  #   - additionalProperties:false at top level (only schemaVersion + plugins)
  #   - per-entry additionalProperties:false (only source/ref/type/description)
  #   - per-entry required: source/ref/type, all strings; source/ref minLength:1
  #   - type enum ∈ {claude-plugin,binary,npm-global} (the fail-closed check)
  # Any drift (a stray key, an empty ref, a missing schemaVersion, an unknown
  # type) fails the gate → return 1 → ERR trap → non-zero boot (fail-closed).
  jq -e '
    def is_nonempty_string: (type == "string") and (length > 0);
    (type == "object")
    and (has("schemaVersion")) and (.schemaVersion | type == "string")
    and (has("plugins")) and (.plugins | type == "object")
    and (keys - ["plugins", "schemaVersion"] | length == 0)
    and (.plugins | to_entries | all(.value
          | (type == "object")
          and (has("source") and has("ref") and has("type"))
          and (keys - ["description", "ref", "source", "type"] | length == 0)
          and (.source | is_nonempty_string)
          and (.ref | is_nonempty_string)
          and (.type | IN("claude-plugin", "binary", "npm-global"))
          and ((has("description") | not) or (.description | type == "string"))))
  ' "$manifest" >/dev/null || { log "manifest failed structural validation"; return 1; }

  # Iterate only claude-plugin entries; binary/npm-global are baked (skip).
  # Capture the jq output into a variable FIRST (not a `< <(...)` process
  # substitution): with process substitution the jq exit status is not part of
  # any pipeline, so `set -o pipefail`/`set -e` cannot see a mid-stream jq
  # failure and the loop would silently see EOF and install a partial set. The
  # command substitution below makes the jq failure visible to `set -e`, so a
  # broken extraction aborts the boot fail-closed.
  local rows
  rows="$(jq -r '.plugins | to_entries[]
                 | select(.value.type == "claude-plugin")
                 | [.key, .value.source, .value.ref] | @tsv' "$manifest")"

  # IFS includes \r so a CRLF-terminated jq line (e.g. jq on a non-Unix host, or a
  # CRLF-saved manifest) does not leave a trailing carriage return on the last field.
  while IFS=$'\t\r' read -r name source ref; do
    [[ -n "$name" ]] || continue
    install_claude_plugin "$name" "$source" "$ref"
  done <<<"$rows"
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

# Validate every required bootconfig field BEFORE any git/cp runs. jq -r emits the
# literal string "null" for an absent/null field, so a missing projectRepo would
# otherwise be handed to `git clone null ...` (which ERR-traps confusingly) or be
# treated as a real repo by the START_DIR guard below. Treat "null"/empty as a
# hard "missing field" failure so a malformed envelope fails closed with a clear
# message. GIT_CRED is intentionally NOT named in the log line (never echo a token
# or its absence pattern beyond the var name). (WR-05)
for _field in CONFIG_REPO CONFIG_BRANCH PROJECT_REPO PROJECT_BRANCH GIT_CRED; do
  _val="${!_field}"
  if [[ -z "$_val" || "$_val" == "null" ]]; then
    log "bootconfig missing required field: ${_field}"
    exit 1
  fi
done
unset _field _val

# Config repo: master CLAUDE.md + the plugin manifest (manifest processing lands
# in Plan 02). Assume cc-worker-config is operator-reachable (A5/Open-Q-1); if it
# needs separate auth that is an operator-contract question, not a code change here.
log "cloning config repo (branch ${CONFIG_BRANCH})"
rm -rf /tmp/cc-worker-config
clone_with_token "$GIT_CRED" "$CONFIG_REPO" /tmp/cc-worker-config \
  --depth=1 --branch "$CONFIG_BRANCH"
cp /tmp/cc-worker-config/claude/CLAUDE.md "${WORKER_HOME}/CLAUDE.md"

# Process the versioned plugin manifest from the just-cloned config repo BEFORE
# the project clone. The fail-closed jq gate rejects an unknown type / malformed
# manifest (non-zero → ERR trap); only claude-plugin types are pulled fresh
# (binary/npm-global are baked at provision time).
log "processing plugin manifest"
process_manifest /tmp/cc-worker-config/plugins/manifest.json

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
#
# The inner shell wraps the worker command in `tmux new-session -A -s burrow`
# (one fixed session per worker; WSX-03 / ADR-0014). `-A` reattaches to the
# existing `burrow` session if it is already running, so a ttyd/web-client
# reconnect to a still-running worker resumes the live session and its
# scrollback instead of starting fresh. The ttyd flags stay FROZEN
# (SC-8 / SC-9 / ADR-0006 / ADR-0007).
log "starting persistent LAN-bound ttyd on :7681 (tmux session 'burrow', cmd: ${CLAUDE_CMD}, cwd: ${START_DIR})"
exec ttyd \
  --port 7681 \
  --writable \
  --interface 0.0.0.0 \
  bash -lc "cd '${START_DIR}' && exec tmux new-session -A -s burrow ${CLAUDE_CMD}"
