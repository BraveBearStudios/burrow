# Phase 11: Scrollback Restore - Context

**Gathered:** 2026-06-25
**Status:** Ready for planning

<domain>
## Phase Boundary

A persistent workspace's terminal scrollback survives stop→start: on reconnect the operator
sees prior scrollback by reattaching to a worker-side tmux session. All work is worker-side in
`cc-worker-config/` (part of the burrow repo). Requirement: WSX-03. CI-provable via the hermetic
boot harness (`api/tests/boot/`, stub ttyd records argv); the real tmux reattach across a real
stop/start is the Phase 14 homelab smoke (ACC-01). ADR-0014 (tmux scrollback) is authored in-phase.

Out of scope: any control-plane change (the relay stays a dumb opaque bridge — explicitly NO
server-side scrollback buffering); cross-reboot scrollback / pipe-pane persistence / CRIU
(WSX-05/06/07, deferred to v1.4+); multi-agent per-workspace sessions (AGENT-01, v1.4).
</domain>

<decisions>
## Implementation Decisions

### tmux scrollback config & boot wrapping
- `burrow-boot.sh` (~line 327-331): the ttyd-wrapped shell execs tmux. New exec form:
  `bash -lc "cd '${START_DIR}' && exec tmux new-session -A -s burrow … ${CLAUDE_CMD}"` — tmux
  wraps the worker shell; `-A` makes a second boot reattach to the existing `burrow` session
  instead of starting a fresh one (the idempotency contract). Session name is the fixed string
  `burrow` (one session per worker).
- `provision-template.sh` (~line 34-37): add `tmux` to the existing apt-install line (alongside
  `ttyd`/`jq`, unpinned in the line per existing convention) and record the Ubuntu 24.04 tmux
  version (3.4) in a top-of-file comment next to `CLAUDE_CODE_VERSION` (the project's pinning
  convention). "Pinned" is satisfied via the documented version + the reproducible 24.04 base.
- Bake a new `/etc/tmux.conf` at provision time (drop-file, following the `/etc/burrow/worker.env`
  placeholder precedent ~line 68-74) containing exactly:
  - `set -g history-limit 50000` — generous coding scrollback, ~a few MB/pane, still bounded.
  - `set -g window-size latest` — the single-reconnecting-web-client resize fix (so the pane
    sizes to the newest attached client, not the smallest).
  Keep `/etc/tmux.conf` minimal — only these two settings (no mouse/status/theme — YAGNI).
- The control-plane terminal relay (`api/routers/terminal.py:84-163`) stays a dumb opaque
  passthrough bridge — Phase 11 adds ZERO lines there. All scrollback preservation is tmux-side.

### Validation (hermetic)
- The boot harness (`api/tests/boot/test_burrow_boot.py`, stub ttyd records argv to
  `ttyd-argv.txt`) gains an assertion that the recorded argv contains `tmux new-session`, `-A`,
  and `-s burrow` (criterion 1).
- A second-boot idempotency test (parallel to `test_two_boots_identical_plugin_tree`) proves the
  `burrow` session name is stable across two boots over the same manifest — proving `-A`
  reattach hermetically without real Proxmox (criterion 3).

### Claude's Discretion
- Exact placement/quoting of the tmux exec wrapper within the existing `bash -lc` string, and
  the precise way `/etc/tmux.conf` is written (heredoc vs cat) — implementer's call within the
  conventions above.
- Exact test names and assertion helpers, as long as criteria 1 + 3 are proven hermetically.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `cc-worker-config/lxc/worker-template/burrow-boot.sh:327-331` — current ttyd exec wrapping
  `bash -lc "cd '${START_DIR}' && exec ${CLAUDE_CMD}"` (the tmux wrap point).
- `cc-worker-config/lxc/worker-template/provision-template.sh:34-37` — apt-install block
  (`git curl build-essential ttyd jq`); `:68-74` — the `/etc/burrow/worker.env` drop-file
  precedent for writing `/etc/tmux.conf`.
- `api/tests/boot/test_burrow_boot.py` — boot harness; stub ttyd argv assertion pattern
  (~line 100-103: reads `ttyd-argv.txt`, asserts on substrings); idempotency pattern
  `test_two_boots_identical_plugin_tree` (~line 211-247, `_digest()` helper).
- `api/tests/boot/conftest.py:403-415` — `stub_ttyd_path` fixture prepends the stub ttyd to PATH.
- `api/routers/terminal.py:84-163` — the opaque relay (pump_up/pump_down forward frames verbatim,
  never `.encode()`); Phase 11 confirms it is untouched.
- `docs/adr/ADR-0011`, `docs/adr/ADR-0013` — ADR format (SPDX comment, ## Status/Context/Decision/
  Consequences; no em dashes). Next free number: ADR-0014.

### Established Patterns
- SPDX two-line header on every shell script (`# SPDX-FileCopyrightText … / # SPDX-License-Identifier …`).
- `set -euo pipefail` strict mode at the top of each script.
- Ubuntu 24.04 LTS golden template; provision runs once inside the template CT before `pct template`,
  so the baked tmux + /etc/tmux.conf survive on every clone.
- Version pins documented inline at the top of provision-template.sh (e.g. `CLAUDE_CODE_VERSION`).

### Integration Points
- `burrow-boot.sh` exec line — wrap shell in `tmux new-session -A -s burrow`.
- `provision-template.sh` — add tmux to apt line + write `/etc/tmux.conf`.
- `api/tests/boot/test_burrow_boot.py` — new argv assertion + second-boot reattach test.
- `docs/adr/ADR-0014-tmux-scrollback.md` — new ADR.
</code_context>

<specifics>
## Specific Ideas

- `window-size latest` is the specific fix for the single-reconnecting-web-client resize problem
  (named in success criterion 2) — without it tmux clamps to the smallest historical client size.
- The boot harness's stub-ttyd-records-argv mechanism is the CI-provability substrate; the real
  reattach is the Phase 14 ACC-01 smoke by design.
</specifics>

<deferred>
## Deferred Ideas

- Cross-reboot scrollback via `pipe-pane` logging, snapshots, CRIU suspend (WSX-05/06/07) — v1.4+.
- Per-workspace / per-agent tmux sessions for multi-agent workers (AGENT-01) — v1.4.
- Richer `/etc/tmux.conf` (mouse mode, status bar, themes) — not needed for scrollback survival.
</deferred>
