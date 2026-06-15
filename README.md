<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Burrow

**A browser-accessible manager for multiple concurrent Claude Code sessions.**

Burrow spins up ephemeral worker containers on demand, each running a Claude Code
terminal, and proxies them to a tiling web UI — so you can run several agent
sessions side by side without bogging down your local machine or hand-stitching
tmux, SSH, and process managers.

> **Status: pre-release / greenfield.** No application code exists yet. The
> design is fully specified in [`docs/tech-spec.md`](docs/tech-spec.md)
> (Part I — spec, Part II — architecture review). Start there. The build,
> test, and container-publishing pipeline is specified in
> [`docs/ci-cd-and-testing.md`](docs/ci-cd-and-testing.md).

## What it does

- **Browser-first.** Open, split, and arrange terminal panels in a draggable grid
  from any device on your network.
- **Ephemeral workspaces.** Each workspace is cloned from a golden template
  container, lives while active, and is destroyed when you're done. No snowflake
  state.
- **Reproducible tooling.** Every workspace boots from the same plugin manifest +
  `CLAUDE.md` pulled fresh from a config repo, so the toolchain is identical
  everywhere.
- **Ownable.** No closed or commercial dependency in the critical path —
  Proxmox, FastAPI, React, xterm.js, ttyd, SQLite.

## Architecture (in brief)

Two planes, one codebase:

- **Control plane** (FastAPI + SQLite): workspace CRUD, a Proxmox integration that
  clones/starts/stops/destroys worker LXCs, and a WebSocket terminal proxy that
  bridges the browser to ttyd in each worker. nginx fronts the static UI, the API,
  and the WS proxy.
- **Worker LXCs** (ephemeral, cloned from a golden template): on boot they pull
  config + plugins, clone the target repo, and start a Claude Code terminal.

Two clean provider seams (`DbProvider`: SQLite → Postgres; `ComputeProvider`:
Proxmox → cloud) keep the optional hosted/multi-tenant path additive rather than a
rewrite. Full detail in the [tech spec](docs/tech-spec.md).

## Stack

| Layer | Choice |
|---|---|
| Backend | FastAPI (Python 3.12), uv, ruff + mypy |
| Frontend | Vite + React 19 + TypeScript, xterm.js, react-mosaic, TanStack Query, Zustand, biome |
| State | SQLite (self-host) / Postgres (hosted) |
| Compute | Proxmox LXC (self-host) |

## UI

A high-fidelity interactive mockup of the interface lives at
[`docs/design/burrow-ui-mockup.html`](docs/design/burrow-ui-mockup.html) (open it
in a browser). The design brief is in
[`docs/design/burrow-ui-design-prompt.md`](docs/design/burrow-ui-design-prompt.md).

## Security model

v1 is **LAN-only with no authentication, by design.** Do not expose it to the
internet. Auth and multi-tenancy are the v2 path. See
[`SECURITY.md`](SECURITY.md) and the spec's security posture.

## License

Burrow is licensed under the **GNU Affero General Public License v3.0 or later**
([`LICENSE`](LICENSE)). You may use, study, modify, and share it freely. If you
run a **modified** version as a network service, AGPL §13 requires you to offer
its complete corresponding source to that service's users — Burrow surfaces a
"Source" link from the running app to satisfy this.

Contributions are accepted under a Contributor License Agreement; see
[`CONTRIBUTING.md`](CONTRIBUTING.md) and [`CLA/`](CLA/).

`SPDX-License-Identifier: AGPL-3.0-or-later`

Copyright © 2026 Brave Bear Studios.
