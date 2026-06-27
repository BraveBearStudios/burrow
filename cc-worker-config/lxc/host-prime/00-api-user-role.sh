#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# 00-api-user-role.sh — Day-0 STEP 0: identity & least privilege.
#
# Creates the burrow@pve user (token-only, no password), the BurrowProvisioner
# role (exactly the verified 9-privilege set), the burrow-workers resource pool,
# a privsep=1 API token, and the scoped ACLs granting the role to BOTH the user
# AND the token at every path (privsep effective rights = user ∩ token).
#
# Run as root@pam on a Proxmox node. Idempotent (check->act) EXCEPT the token,
# which is the one non-idempotent resource: a second `token add` mints a SECOND
# token and never re-prints the first secret, so on a pre-existing token this
# script PROMPTS the operator to rotate or reuse rather than silently churning.
#
# Source: .planning/research/PROXMOX-PRIMING.md §2 (recipe) + §6 (hygiene).
# All topology is a placeholder; fill your LAN values before running.

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${HERE}/lib/common.sh"

# ---------------------------------------------------------------------------
# Configuration (placeholders — replace <...> with your real values).
# ---------------------------------------------------------------------------
USER="burrow@pve"
TOKEN="burrow"
NODE_NAME="${NODE_NAME:-<node>}"       # node this runs on (env-overridable)
POOL_NAME="burrow-workers"
POOL="/pool/${POOL_NAME}"
STORAGE="/storage/${ROOTFS_STORAGE:-<rootfs-storage>}"   # thin rootfs storage for worker clones
NODE="/nodes/${NODE_NAME}"             # repeat the ACL loop per scheduling node
TMPL="/vms/${TEMPLATE_VMID:-<template-vmid>}"            # the golden template VMID

# The authoritative minimal role: exactly 9 privileges. Do NOT add or remove.
# (Conditional SDN.Use on the <bridge> is handled separately, see below.)
PRIVS="VM.Audit VM.Clone VM.Allocate VM.Config.Network VM.Config.Options VM.PowerMgmt Datastore.AllocateSpace Datastore.Audit Sys.Audit"

# Where the token secret is captured. Lives in the repo-root gitignored .env.
ENV_FILE="${ENV_FILE:-.env}"

# ---------------------------------------------------------------------------
# Preflight: right host, right tools, root.
# ---------------------------------------------------------------------------
require_root
require_cmd pveum pvesh git
require_node "$NODE_NAME"

# ---------------------------------------------------------------------------
# 1. Role — modify keeps privs authoritative on re-run; add on first run.
# ---------------------------------------------------------------------------
if pveum role list --output-format json | grep -q '"BurrowProvisioner"'; then
  log "role BurrowProvisioner exists -> modify (re-assert privs)"
  pveum role modify BurrowProvisioner --privs "$PRIVS"
else
  log "role BurrowProvisioner missing -> add"
  pveum role add BurrowProvisioner --privs "$PRIVS"
fi

# ---------------------------------------------------------------------------
# 2. User — token-only, no password.
# ---------------------------------------------------------------------------
if pveum user list --output-format json | grep -q "\"${USER}\""; then
  log "user ${USER} exists -> leave as-is"
else
  log "user ${USER} missing -> add (token-only, no password)"
  pveum user add "$USER" --comment "Burrow control plane (token-only)"
fi

# ---------------------------------------------------------------------------
# 3. Pool — fences the worker VMID range. `|| true` because add-on-existing
#    returns non-zero, which is benign here.
# ---------------------------------------------------------------------------
pveum pool add "$POOL_NAME" 2>/dev/null || true
log "pool ${POOL_NAME} present"
# Add the template (and optionally the whole worker range) to the pool, e.g.:
#   pvesh set /pools/${POOL_NAME} -vms <template-vmid>

# ---------------------------------------------------------------------------
# 4. Token (privsep=1) — the ONE non-idempotent resource.
#    The secret prints ONCE and is unrecoverable; capture it into .env now.
# ---------------------------------------------------------------------------
TOKEN_EXISTS=0
if pveum user token list "$USER" --output-format json | grep -q "\"${TOKEN}\""; then
  TOKEN_EXISTS=1
fi

if [[ "$TOKEN_EXISTS" -eq 1 ]]; then
  log "token ${USER}!${TOKEN} ALREADY EXISTS."
  log "A second 'token add' mints a SECOND token and will NOT re-print the first secret."
  log "Choose: [reuse] keep the live token and skip re-creation, or"
  log "        [rotate] DELETE the existing token and mint a fresh one (secret reprints)."
  read -rp "token action [reuse/rotate]: " TOKEN_ACTION
  case "$TOKEN_ACTION" in
    rotate)
      if confirm "Delete token ${USER}!${TOKEN} and mint a new secret?"; then
        pveum user token remove "$USER" "$TOKEN"
        TOKEN_EXISTS=0
      else
        log "rotate aborted -> reusing existing token; secret NOT reprinted"
      fi
      ;;
    reuse|*)
      log "reusing existing token; secret NOT reprinted (it lives in your .env)"
      ;;
  esac
fi

if [[ "$TOKEN_EXISTS" -eq 0 ]]; then
  log "minting privsep token ${USER}!${TOKEN} (secret prints once)"
  # Capture the JSON output WITHOUT echoing the value. --privsep 1 makes the
  # token's effective rights the intersection of user and token ACLs.
  TOKEN_JSON="$(pveum user token add "$USER" "$TOKEN" --privsep 1 \
    --comment "Burrow provisioner" --output-format json)"

  # Extract the secret value silently. Never expand it on a logged line or as a
  # CLI arg. Prefer the structured .env writer below; if .env cannot be written
  # the operator still gets the one-time secret on a single guarded line.
  if command -v jq >/dev/null 2>&1; then
    TOKEN_VALUE="$(printf '%s' "$TOKEN_JSON" | jq -r '.value')"
  else
    # Minimal extraction without jq; still never echoes the value.
    TOKEN_VALUE="$(printf '%s' "$TOKEN_JSON" | sed -n 's/.*"value"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
  fi

  # --- Secret write into .env (the hygiene crux) ---------------------------
  # Refuse to write .env unless git confirms it is ignored, so the secret can
  # never be staged. check-ignore exits 0 only when the path is ignored.
  if git -C "$(dirname "$ENV_FILE")" check-ignore "$ENV_FILE" >/dev/null 2>&1; then
    umask 077
    { set +x; } 2>/dev/null            # ensure no xtrace can leak the value
    if [[ ! -f "$ENV_FILE" ]] && [[ -f "$(dirname "$ENV_FILE")/.env.example" ]]; then
      cp "$(dirname "$ENV_FILE")/.env.example" "$ENV_FILE"
    fi
    # printf (never echo) the secret into .env; no value ever on a CLI arg.
    printf 'PROXMOX_TOKEN_VALUE=%s\n' "$TOKEN_VALUE" >> "$ENV_FILE"
    chown burrow:burrow "$ENV_FILE" 2>/dev/null || true
    chmod 0600 "$ENV_FILE"
    log "token secret written to ${ENV_FILE} (0600). It was NOT printed to the terminal."
  else
    # .env is NOT safely gitignored: refuse to auto-write. The machine-minted
    # secret must still leave this script, but it must NEVER be printed. Re-read
    # it from the operator at a SILENT prompt (read -rsp — no terminal echo) so
    # they can route it into their own gitignored secret store by hand.
    { set +x; } 2>/dev/null
    log "REFUSING to write ${ENV_FILE}: 'git check-ignore ${ENV_FILE}' did not pass."
    log "Copy the token value from a secure channel, then paste it at the hidden"
    log "prompt below. It is read SILENTLY (no echo) and only re-emitted to a file"
    log "you confirm is gitignored."
    read -rsp "Paste PROXMOX_TOKEN_VALUE (hidden), or Enter to abort: " PASTED
    printf '\n' >&2
    if [[ -n "$PASTED" ]]; then
      read -rp "Path to a gitignored env file to write: " DEST
      if [[ -n "$DEST" ]] && git -C "$(dirname "$DEST")" check-ignore "$DEST" >/dev/null 2>&1; then
        umask 077
        printf 'PROXMOX_TOKEN_VALUE=%s\n' "$PASTED" >> "$DEST"
        chmod 0600 "$DEST"
        log "secret written to ${DEST} (0600), never echoed."
      else
        log "destination not gitignored -> NOT written. Secret discarded; re-run to retry."
      fi
    fi
    unset PASTED
  fi
  unset TOKEN_VALUE TOKEN_JSON
fi

# ---------------------------------------------------------------------------
# 5. Grant the role to BOTH the user AND the token at every scoped path.
#    Under privsep the token alone has ZERO rights unless the user also holds
#    them at that path -> grant to both, every path. acl modify is idempotent.
# ---------------------------------------------------------------------------
# Grant the role to one principal (a flag + value pair) at every scoped path.
# Passing the principal as separate positional args ("$@") sidesteps IFS
# entirely: common.sh sets IFS=$'\n\t' (no space), so any space-based split —
# an unquoted "$principal" OR `read -a` (which also splits on $IFS) — would hand
# pveum "--users burrow@pve" as ONE argument and the grant would be rejected.
grant_acls() {
  # "$@" = the principal flag and value, e.g. (--users burrow@pve).
  pveum acl modify "$POOL"    "$@" --roles BurrowProvisioner --propagate 1
  pveum acl modify "$TMPL"    "$@" --roles BurrowProvisioner
  pveum acl modify "$STORAGE" "$@" --roles BurrowProvisioner
  pveum acl modify "$NODE"    "$@" --roles BurrowProvisioner
}
grant_acls --users  "${USER}"
grant_acls --tokens "${USER}!${TOKEN}"
log "ACLs granted to user and token at pool/template/storage/node"

# Conditional: grant SDN.Use on the <bridge> ONLY if SDN permission enforcement
# is enabled on this cluster (a plain Linux-bridge homelab usually does not need
# it). Uncomment and scope to the vNet/bridge path if a clone returns 403 on
# 'set network':
#   sdn_grant() { pveum acl modify "/sdn/zones/<zone>/<bridge>" "$@" --roles BurrowProvisioner; }
#   sdn_grant --users  "${USER}"
#   sdn_grant --tokens "${USER}!${TOKEN}"

log "STEP 0 complete. Verify scope with:"
log "  pvesh get /access/permissions --token \"${USER}!${TOKEN}=<secret>\""

# ---------------------------------------------------------------------------
# ## Reversal
# Remove everything this script created (run as root@pam). Order matters:
# revoke ACLs, delete the token, delete the user, delete the role, delete pool.
#
#   revoke_acls() {
#     pveum acl modify /pool/burrow-workers "$@" --roles BurrowProvisioner --delete
#     pveum acl modify /vms/<template-vmid> "$@" --roles BurrowProvisioner --delete
#     pveum acl modify /storage/<rootfs-storage> "$@" --roles BurrowProvisioner --delete
#     pveum acl modify /nodes/<node> "$@" --roles BurrowProvisioner --delete
#   }
#   revoke_acls --users  burrow@pve
#   revoke_acls --tokens burrow@pve!burrow
#   pveum user token remove burrow@pve burrow
#   pveum user delete burrow@pve
#   pveum role delete BurrowProvisioner
#   pveum pool delete burrow-workers
# Also remove the PROXMOX_TOKEN_VALUE line from your gitignored .env.
# ---------------------------------------------------------------------------
