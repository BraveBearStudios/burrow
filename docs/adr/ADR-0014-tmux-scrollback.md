<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# ADR-0014: tmux scrollback in the worker template

## Status

Accepted

## Context

WSX-03 asks that a persistent workspace's terminal scrollback be restored on
reconnect. The relevant mechanism is worker-side: tmux holds per-pane scrollback
in the tmux SERVER's process memory inside the LXC.

The important nuance is what "restored on reconnect" can and cannot mean in v1.3.
Because tmux scrollback lives in the tmux server's memory, it survives only as
long as that server process is alive. A web-client or ttyd reconnect to a worker
whose container is still running reattaches to the live `burrow` session and sees
prior scrollback. A real `pct stop` halts the LXC and kills the tmux server, so
tmux alone does NOT preserve scrollback across a full container halt. That is
cross-reboot scrollback, a distinct and heavier problem (it needs `pipe-pane`
logging to durable storage, or CRIU suspend-to-disk), and it is deferred to v1.4
as WSX-06. ADR-0013 already records that Tier-1 persistence preserves files on
disk, not live-session state; this ADR fills the live-session seam for the
reconnect case only, and is careful not to over-claim the halt case.

The honest contract this ADR records: Phase 11 delivers reattach-on-RECONNECT to
a still-running worker. It does NOT make scrollback survive a real `pct stop`.

The wiring is CI-provable hermetically (the boot harness asserts the tmux
invocation in the recorded ttyd argv and asserts the `burrow` session is stable
across two boots, the `-A` idempotency contract). The real tmux reattach across a
real worker stop and start is the Phase 14 dev-homelab acceptance smoke (ACC-01),
not a CI command, by design.

## Decision

The worker boots its Claude shell inside a single, fixed tmux session so that a
reconnect to a still-running worker resumes the live session and its scrollback.

- **Bake tmux into the golden template.** tmux 3.4 (the Ubuntu 24.04 LTS
  distro package) is installed at provision time alongside ttyd and jq, so it
  survives on every clone. The version is pinned by the reproducible 24.04 base
  plus the documented pin comment, not by a third-party feed (no PyPI, no npm,
  no extra supply-chain ingress beyond the existing apt baseline).
- **Wrap the worker shell in `tmux new-session -A -s burrow`.** The inner
  `bash -lc` command that ttyd execs runs
  `exec tmux new-session -A -s burrow ${CLAUDE_CMD}` instead of
  `exec ${CLAUDE_CMD}` directly. There is exactly one session per worker, named
  `burrow`. The `-A` flag means attach-if-exists, else create: the FIRST boot
  starts the Claude shell as the session's first process; a later reconnect (the
  browser tab reopened, ttyd restarted) reattaches to the existing `burrow`
  session and its scrollback without re-spawning the command. The frozen ttyd
  flags (`--port 7681 --writable --interface 0.0.0.0`, no `--once`; ADR-0006 and
  ADR-0007) are unchanged.
- **Bake a minimal `/etc/tmux.conf`.** Two settings, nothing else:
  `set -g history-limit 50000` (a generous coding-session scrollback buffer at
  roughly a few MB per pane, still bounded, up from the 2000-line default), and
  `set -g window-size latest` (with a single reconnecting web client the default
  `largest` or `smallest` policy would clamp the pane to a historical client
  size; `latest` sizes the window to the most-recently-attached client so the
  reconnecting browser drives the geometry).
- **The control-plane relay stays a dumb, opaque bridge.** No server-side
  scrollback buffering is added: `api/routers/terminal.py` forwards terminal
  frames verbatim and is untouched by this work. All scrollback preservation is
  worker-side, inside the tmux server.

## Consequences

- Scrollback is bounded: roughly a few MB per pane at the 50000-line cap, not
  unlimited growth (this is the WSX DoS mitigation, T-11-03).
- A reconnect to a still-running worker resumes the `burrow` session and its
  scrollback; the operator does not lose context when a browser tab is closed and
  reopened.
- The control plane retains no operator terminal data: the relay stays opaque and
  gains zero lines, so no server-side scrollback buffer is introduced (the named
  anti-pattern stays absent; T-11-01).
- tmux runs inside the existing unprivileged LXC trust boundary on the default
  per-user socket; no new network ingress, no new auth surface, no new secret
  handling. The only network-facing element (ttyd on :7681) is unchanged.
- Cross-reboot scrollback persistence (pipe-pane logging, snapshots, CRIU) and
  per-agent tmux sessions for multi-agent workers stay deferred (WSX-05, WSX-06,
  WSX-07, AGENT-01; v1.4 and later). This ADR does not introduce any of them.

## Revisit trigger

A requirement for scrollback to survive a real container halt (`pct stop` or a
node reboot), which forces durable `pipe-pane` logging or CRIU suspend and the
storage and kernel compatibility work they need, or a requirement for more than
one named tmux session per worker (per-agent sessions for multi-agent workers),
which would change the fixed single-`burrow`-session contract recorded here.
