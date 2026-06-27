<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Burrow Worker — Claude Code session

This is the master CLAUDE.md copied into each ephemeral Burrow worker's `$HOME`
at boot (by `burrow-boot.sh`, from the config repo). It is the standing context
for the Claude Code session running inside this worker container.

## What this environment is

You are running inside an ephemeral Proxmox LXC, provisioned on demand by Burrow.
The container is disposable: when the workspace is destroyed, everything here is
gone. Do your work in the cloned project repository under `$HOME`.

- Node 22, git, tmux, ttyd, and the Claude Code CLI are pre-installed.
- The project repository was cloned at boot into your working directory.
- Scrollback persists across reconnects (a fixed `tmux` session named `burrow`).

## Working agreement

- Treat the cloned project repo as the source of truth; follow any `CLAUDE.md`,
  `CONTRIBUTING.md`, or README it ships.
- Keep changes scoped to what was asked. Run the project's own tests/linters
  before claiming a change is done.
- Don't write secrets to disk. The short-lived git credential used to clone is
  already discarded; request a fresh one if you need to push.

This file is intentionally minimal. Per-project guidance belongs in the project
repo's own `CLAUDE.md`, not here.
