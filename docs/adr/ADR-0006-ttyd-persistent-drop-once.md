<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# ADR-0006: ttyd runs persistent — drop `--once`

## Status

Accepted

## Context

Each worker runs **ttyd** to expose its interactive Claude Code session over WebSocket,
which the control plane's terminal proxy bridges to the browser. The tech-spec's
boot snippet (and tech-spec Appendix B open question #2) launches ttyd with the
**`--once`** flag, which makes ttyd **exit when the client disconnects** (SC-8).

With `--once`, closing the browser tab — or any transient network drop that disconnects
the WebSocket — terminates ttyd, and with it the live `claude` process and the session's
in-memory state. For Burrow this is a **data-loss-class** behavior: the operator's whole
value proposition is watching and managing *many* long-running sessions, switching
between tabs, and reconnecting later. A tab close is a **detach**, not a request to kill
the agent. Detach must never equal terminate.

The only intended way to end a worker's session is the explicit **destroy** lifecycle
action (which removes the LXC and frees its VMID). Everything short of destroy — tab
close, tab switch, browser refresh, brief disconnect — must leave the Claude session
running so a later reconnect attaches to the **same** session.

## Decision

Run ttyd **persistently**: **drop the `--once` flag** from the worker's ttyd invocation
in `burrow-boot.sh`.

- ttyd stays running across client disconnects. A browser tab close detaches the WS
  bridge but leaves ttyd and the `claude` process alive.
- Reconnecting (reopening the workspace) re-attaches to the **same** running session,
  not a fresh one.
- **Destroy is the only kill path.** The worker lifecycle ends when the operator
  destroys the workspace; the LXC is removed and the VMID is freed. No client-side event
  terminates the session.
- This decision is frozen in Phase 0 (it shapes the golden template's boot script); its
  real-world acceptance (persistent ttyd survives a tab close) is a dev-homelab smoke
  item, deferred.

## Consequences

- Closing a tab, switching workspaces, or a transient disconnect no longer kills the
  agent — the core "manage many concurrent sessions" experience works as intended, and
  stop/start can reconnect to the same session.
- Worker resources (the `claude` process, its memory, the container) are held for the
  worker's whole lifetime, not just while a browser is attached. This is intended:
  destroy is the deliberate reclamation action, and the node-RAM capacity guard bounds
  concurrency.
- The control-plane proxy must tolerate multiple attach/detach cycles against one
  long-lived ttyd (reconnect logic lives in the Phase-1/2 proxy + UI), rather than
  assuming a one-shot connection.
- Because ttyd no longer self-terminates, an orphaned worker (one whose row was lost)
  will keep running until explicitly destroyed — reconciliation/cleanup is a control-
  plane responsibility, not something `--once` papers over.

## Revisit trigger

A future single-use / one-shot worker mode where a session genuinely should end on
disconnect, or a resource model where holding idle sessions is unacceptable and
auto-detach-then-suspend is preferred over persistent ttyd.
