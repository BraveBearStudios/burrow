#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# 40-control-plane.sh — Day-0 STEP 3: provision the persistent control-plane box.
#
# The control plane is its own dedicated, NON-ephemeral Ubuntu 24.04 box (LXC or
# small VM), separate from the worker template. This script creates the burrow
# service account, the /opt/burrow layout and /data state dir, a Python 3.12 uv
# venv (or a containerized image — operator choice), an nginx site validated
# before reload, the systemd unit with optional hardening, and assembles the
# gitignored .env with the STEP-0 token handled under the full secret-hygiene
# contract (never echoed, never a CLI arg, 0600, refuse-unless-gitignored).
#
# Run as root on the control-plane host.
# Source: .planning/research/PROXMOX-PRIMING.md §7.
# All topology is a placeholder; fill your values before running.

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${HERE}/lib/common.sh"

# ---------------------------------------------------------------------------
# Configuration (placeholders).
# ---------------------------------------------------------------------------
APP_USER="burrow"
APP_HOME="/opt/burrow"
DATA_DIR="/data"
VENV_DIR="${APP_HOME}/venv"
ENV_FILE="${APP_HOME}/.env"
PYTHON_VERSION="3.12"

# Deploy mode: "venv" (uv venv from the lockfile) or "container" (run the
# Dockerfile.api image). Both are supported; state your choice here.
DEPLOY_MODE="venv"

# nginx + systemd source artifacts (committed under cc-worker-config; adjust
# paths if your layout differs).
NGINX_SITE_SRC="${HERE}/../../nginx/burrow.conf"
NGINX_SITE_DST="/etc/nginx/sites-available/burrow.conf"
NGINX_SITE_LINK="/etc/nginx/sites-enabled/burrow.conf"
SYSTEMD_UNIT_SRC="${HERE}/../../systemd/burrow.service"
SYSTEMD_UNIT_DST="/etc/systemd/system/burrow.service"

# ---------------------------------------------------------------------------
# Preflight.
# ---------------------------------------------------------------------------
require_root
require_cmd useradd install nginx systemctl git

# ---------------------------------------------------------------------------
# 1. Service account — non-login, owns /opt/burrow and /data and nothing else.
# ---------------------------------------------------------------------------
if id -u "$APP_USER" >/dev/null 2>&1; then
  log "service account '$APP_USER' exists -> leave as-is"
else
  log "creating system service account '$APP_USER'"
  useradd --system --create-home --home-dir "$APP_HOME" \
    --shell /usr/sbin/nologin "$APP_USER"
fi

# ---------------------------------------------------------------------------
# 2. Layout (install -d is idempotent). /data is separate so it survives an app
#    redeploy and is the backup target.
# ---------------------------------------------------------------------------
log "creating /opt/burrow layout + /data"
install -d -o "$APP_USER" -g "$APP_USER" -m 750 "$APP_HOME"
install -d -o "$APP_USER" -g "$APP_USER" -m 750 "${APP_HOME}/api"
install -d -o "$APP_USER" -g "$APP_USER" -m 750 "${APP_HOME}/ui/dist"
install -d -o "$APP_USER" -g "$APP_USER" -m 750 "$DATA_DIR"
chown -R "$APP_USER:$APP_USER" "$APP_HOME"

# ---------------------------------------------------------------------------
# 3. Runtime: uv venv (Python 3.12) OR containerized image.
# ---------------------------------------------------------------------------
case "$DEPLOY_MODE" in
  venv)
    require_cmd uv
    if [[ -d "$VENV_DIR" ]]; then
      log "venv already present at $VENV_DIR -> sync from lockfile"
    else
      log "creating uv venv at $VENV_DIR (Python $PYTHON_VERSION)"
      uv venv "$VENV_DIR" --python "$PYTHON_VERSION"
    fi
    # Install from the committed lockfile (frozen = reproducible). Run as the
    # app user against the api project dir.
    log "installing dependencies from the lockfile (uv sync --frozen)"
    ( cd "${APP_HOME}/api" && uv sync --frozen ) || \
      log "uv sync skipped — populate ${APP_HOME}/api with the project + uv.lock first"
    ;;
  container)
    require_cmd docker
    log "container mode: run the Dockerfile.api image (compose/systemd manages it)."
    log "Skipping venv creation. Ensure the image is built/pulled and the unit"
    log "references it. The .env assembly below still applies (mounted into the container)."
    ;;
  *)
    log "unknown DEPLOY_MODE '$DEPLOY_MODE' (expected venv|container)"
    exit 1
    ;;
esac

# ---------------------------------------------------------------------------
# 4. nginx — install the site, remove the default (confirm first), VALIDATE
#    before reload (a bad config that fails restart leaves nginx down).
# ---------------------------------------------------------------------------
if [[ -f "$NGINX_SITE_SRC" ]]; then
  log "installing nginx site"
  install -m 644 "$NGINX_SITE_SRC" "$NGINX_SITE_DST"
  ln -sf "$NGINX_SITE_DST" "$NGINX_SITE_LINK"

  if [[ -e /etc/nginx/sites-enabled/default ]]; then
    if confirm "Remove the default nginx site (/etc/nginx/sites-enabled/default)?"; then
      rm -f /etc/nginx/sites-enabled/default
    else
      log "keeping default nginx site (may conflict with the burrow site)"
    fi
  fi

  log "validating nginx config before reload"
  if nginx -t; then
    systemctl reload nginx
    log "nginx reloaded"
  else
    log "nginx -t FAILED — NOT reloading (existing config stays live). Fix and re-run."
    exit 1
  fi
else
  log "nginx site source '$NGINX_SITE_SRC' not found — skipping nginx setup"
fi

# ---------------------------------------------------------------------------
# 5. systemd — install the unit, daemon-reload, enable --now.
#    Optional hardening lives in the unit file (committed under cc-worker-config):
#      ProtectSystem=strict, ReadWritePaths=/data, NoNewPrivileges=yes, ProtectHome=yes
# ---------------------------------------------------------------------------
if [[ -f "$SYSTEMD_UNIT_SRC" ]]; then
  log "installing burrow.service systemd unit"
  install -m 644 "$SYSTEMD_UNIT_SRC" "$SYSTEMD_UNIT_DST"
  systemctl daemon-reload
  systemctl enable --now burrow.service
  log "burrow.service enabled and started"
else
  log "systemd unit source '$SYSTEMD_UNIT_SRC' not found — skipping unit install"
fi

# ---------------------------------------------------------------------------
# 6. .env assembly — the secret crux. Same hygiene contract as 00-: umask 077,
#    fill non-secret keys from placeholders, read the token at a SILENT prompt,
#    set +x around the write, printf (never echo), unset, 0600, and refuse to
#    write unless git confirms .env is ignored.
# ---------------------------------------------------------------------------
log "assembling ${ENV_FILE}"
if ! git -C "$APP_HOME" check-ignore .env >/dev/null 2>&1 && \
   ! git check-ignore "$ENV_FILE" >/dev/null 2>&1; then
  log "REFUSING to write ${ENV_FILE}: not confirmed gitignored."
  log "Ensure '.env' is gitignored in this checkout before assembling secrets."
else
  umask 077
  if [[ ! -f "$ENV_FILE" ]] && [[ -f "${APP_HOME}/.env.example" ]]; then
    cp "${APP_HOME}/.env.example" "$ENV_FILE"
  fi

  # Non-secret keys filled from operator placeholders (edit before/after run).
  # Use printf appends; the operator can also edit ${ENV_FILE} by hand.
  {
    printf 'PROXMOX_USER=%s\n'        "burrow@pve"
    printf 'PROXMOX_TOKEN_NAME=%s\n'  "burrow"
    printf 'DATABASE_PATH=%s\n'       "${DATA_DIR}/burrow.db"
    # PROXMOX_HOST, PROXMOX_CA_CERT_PATH, TEMPLATE_VMID, WORKER_POOL_START/END,
    # DEFAULT_NODE, CONFIG_REPO: fill with YOUR values (placeholders in .env.example).
  } >> "$ENV_FILE"

  # The token (from STEP 0). read -rsp = SILENT (no terminal echo). Wrap the
  # write so xtrace can never leak the value.
  read -rsp "Paste PROXMOX_TOKEN_VALUE from STEP 0 (hidden): " TOKEN_VALUE
  printf '\n' >&2
  { set +x; } 2>/dev/null
  if [[ -n "$TOKEN_VALUE" ]]; then
    printf 'PROXMOX_TOKEN_VALUE=%s\n' "$TOKEN_VALUE" >> "$ENV_FILE"
  else
    log "no token entered — leaving PROXMOX_TOKEN_VALUE unset in ${ENV_FILE}"
  fi
  unset TOKEN_VALUE

  chown "$APP_USER:$APP_USER" "$ENV_FILE"
  chmod 0600 "$ENV_FILE"
  log "${ENV_FILE} assembled (0600 ${APP_USER}:${APP_USER}); token never echoed."
fi

log "STEP 3 complete. Verify with:"
log "  curl http://127.0.0.1:8000/api/v1/health  -> expect db: ok, compute: ok"

# ---------------------------------------------------------------------------
# ## Reversal
# Tear down the control plane WHILE PRESERVING /data (the SQLite state + backups):
#   systemctl disable --now burrow.service
#   rm -f /etc/systemd/system/burrow.service && systemctl daemon-reload
#   rm -f /etc/nginx/sites-enabled/burrow.conf /etc/nginx/sites-available/burrow.conf
#   nginx -t && systemctl reload nginx
#   rm -rf /opt/burrow            # PRESERVE /data — do NOT remove it
#   # userdel burrow              # only if fully decommissioning
# /data is intentionally NOT removed so a redeploy keeps the database + backups.
# ---------------------------------------------------------------------------
