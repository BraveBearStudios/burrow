# Phase 11: Scrollback Restore - Research

**Researched:** 2026-06-25
**Confidence:** HIGH — codebase claims verified by scout against live files; tmux semantics are stable, well-documented behavior.

## What must be true (WSX-03)

A persistent workspace's terminal scrollback survives stop→start: on reconnect the operator sees
prior scrollback by reattaching to a worker-side tmux session. The control-plane relay stays a
dumb opaque bridge (no server-side buffering). CI-provable via the hermetic boot harness; real
reattach is the Phase 14 (ACC-01) homelab smoke.

## CRITICAL nuance — what "survives stop→start" means in v1.3

tmux scrollback lives in the **tmux server's process memory**. A real `pct stop` halts the LXC and
kills the tmux server, so scrollback does NOT survive a full container halt by tmux alone. That is
**cross-reboot scrollback**, which is explicitly deferred to v1.4+ (WSX-06, via `pipe-pane` logging
or CRIU suspend).

What Phase 11 delivers in v1.3 is the **tmux `-A` reattach mechanism**: while the worker container
keeps running, a web-client / ttyd reconnect (browser tab closed and reopened, ttyd restarted)
reattaches to the still-alive `burrow` tmux session and sees prior scrollback. This is the
foundation; it is what the success criteria are carefully scoped to prove:

- Criterion 1 (argv assertion) and Criterion 3 (`-A` idempotent reattach) are **hermetic** — they
  prove the mechanism is wired, NOT that scrollback survives a real CT halt.
- The plan and ADR-0014 MUST NOT over-claim "scrollback survives a real `pct stop`." State the
  honest contract: reattach-on-reconnect now; cross-reboot persistence is v1.4.

This framing matches the deferred-items ledger (WSX-05/06/07 → v1.4+) and keeps the Phase 14 smoke
honest about what it validates.

## How `tmux new-session -A -s burrow` behaves

- `-A`: attach to the named session if it exists, otherwise create it. Idempotent.
- `-s burrow`: the fixed session name (one session per worker).
- With a shell-command argument: on **create**, tmux runs the command as the session's first
  process; on **attach**, the trailing command is **ignored** (tmux attaches to the existing
  session). This is exactly the desired contract — first boot starts the Claude shell inside tmux;
  a reattach resumes the existing session (and its scrollback) without re-spawning.
- `set -g window-size latest` (the resize fix): with a single reconnecting web client, the default
  `window-size largest`/`smallest` clamps the pane to a historical client size; `latest` sizes the
  window to the most-recently-attached client so the reconnecting browser drives the geometry.
- `set -g history-limit 50000`: per-pane scrollback line cap (default 2000). 50000 lines is a
  generous coding-session buffer at ~a few MB/pane, still bounded.

## Implementation map (verified analogs)

### 1. burrow-boot.sh — wrap the shell in tmux
`cc-worker-config/lxc/worker-template/burrow-boot.sh:327-331` currently:
```
exec ttyd --port 7681 --writable --interface 0.0.0.0 \
  bash -lc "cd '${START_DIR}' && exec ${CLAUDE_CMD}"
```
Change: the inner `exec` runs tmux, e.g.
`bash -lc "cd '${START_DIR}' && exec tmux new-session -A -s burrow ${CLAUDE_CMD}"`.
Keep the ttyd flags unchanged. tmux becomes PID-1-of-the-shell so its lifetime tracks the worker.

### 2. provision-template.sh — bake tmux + /etc/tmux.conf
- Apt block `:34-37` (`git curl build-essential ttyd jq`): add `tmux` (unpinned in the line, like
  ttyd/jq); record the Ubuntu 24.04 tmux version (3.4) in the top-of-file comment beside
  `CLAUDE_CODE_VERSION` (the project's pin-by-comment convention).
- Drop-file `/etc/tmux.conf` (follow the `/etc/burrow/worker.env` placeholder precedent `:68-74`),
  containing exactly: `set -g history-limit 50000` and `set -g window-size latest`. Nothing else.
- Provision runs once inside the template CT before `pct template`, so both survive on every clone.

### 3. Hermetic boot harness — assert the wiring + reattach
- `api/tests/boot/test_burrow_boot.py` (stub ttyd records argv to `ttyd-argv.txt`, asserted on
  substrings ~`:100-103`): add assertions that the recorded argv contains `tmux new-session`,
  `-A`, and `-s burrow` (criterion 1).
- `conftest.py:403-415` `stub_ttyd_path` prepends the stub ttyd to PATH.
- Idempotency (criterion 3): parallel to `test_two_boots_identical_plugin_tree` (`:211-247`,
  `_digest()`), add a test proving two boots over the same manifest both invoke
  `tmux new-session -A -s burrow` with the stable `burrow` session name — proving the `-A` contract
  hermetically (the stub records argv; the assertion is on the invocation, not a live tmux server).

### 4. Relay stays untouched
`api/routers/terminal.py:84-163` is an opaque pump_up/pump_down passthrough (forwards frames
verbatim, never `.encode()`). Phase 11 adds ZERO lines here (criterion 4). A test/assertion that the
relay is unchanged is optional; the seam discipline is the point.

### 5. ADR-0014
`docs/adr/ADR-0014-tmux-scrollback.md` (next free number; 0012 reserved). Match ADR-0011/0013 format
(SPDX comment header; ## Status/Context/Decision/Consequences; no em dashes). Decision: Tier-1
scrollback = worker-side tmux `new-session -A` reattach on reconnect; cross-reboot persistence
(pipe-pane/CRIU) deferred to v1.4.

## Pitfalls

- Do NOT add server-side scrollback buffering to the relay (the named anti-pattern; criterion 4).
- Do NOT claim scrollback survives a real `pct stop` — tmux server dies with the CT (v1.4 scope).
- `tmux new-session -A <cmd>` ignores `<cmd>` on attach — correct here; do not "fix" it by forcing
  a respawn (that would discard scrollback).
- SQLite-style "DEFAULT on ADD" pitfalls are N/A (no DB change this phase).
- Quote `${START_DIR}` / `${CLAUDE_CMD}` carefully inside the existing `bash -lc "..."` so the tmux
  wrap doesn't break word-splitting of the Claude command.

## Validation Architecture

**Framework:** pytest (boot harness, `api/tests/boot/`), hermetic — stub ttyd on PATH records argv;
no real Proxmox, no real tmux server needed for the CI-provable criteria.

**Wave 0 / new tests:**
- argv assertion in `test_burrow_boot.py`: recorded ttyd argv contains `tmux new-session`, `-A`,
  `-s burrow` (criterion 1).
- second-boot reattach test: two boots over the same manifest both carry the stable
  `tmux new-session -A -s burrow` invocation (criterion 3), mirroring `_digest()` idempotency.

**Manual-only / deferred:** real tmux reattach across a real worker stop/start on Proxmox →
Phase 14 ACC-01 dev-homelab smoke (by design; not CI-provable).

**Sampling:** run `cd api && uv run pytest tests/boot -q` after each boot-script/test change;
full `cd api && uv run pytest -q` before verification.

**Security (ASVS L1):** no new ingress, no auth surface, no secret handling. tmux runs inside the
unprivileged LXC boundary on the default per-user socket; no new attack surface. The one discipline
to hold is criterion 4 (relay stays opaque — no new server-side data retention).

## RESEARCH COMPLETE
