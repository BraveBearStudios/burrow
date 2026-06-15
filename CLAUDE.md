<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# CLAUDE.md — Burrow

Context for Claude Code (and any agent or human) working in this repo. Read this
first, every session.

## What this is

Burrow is a browser-accessible manager for multiple concurrent Claude Code
sessions. It spins up ephemeral worker containers (Proxmox LXCs) on demand, each
running a Claude Code terminal, and proxies them to a tiling web UI.

**Status: greenfield. No application code exists yet.** This repo is currently a
full specification plus project scaffolding. Your job at kickoff is to implement
the spec — not to invent a different design.

## Read these before writing code (in order)

1. [`docs/tech-spec.md`](docs/tech-spec.md) — architecture, API, data model,
   backend/frontend contracts, the golden-template + worker boot flow.
2. [`docs/ci-cd-and-testing.md`](docs/ci-cd-and-testing.md) — container build,
   test tiers, scanning/signing, GHCR publishing.

## Stack & layout

- **Backend:** FastAPI (Python 3.12), uv, ruff + mypy. Lives in `api/`.
- **Frontend:** Vite + React 19 + TypeScript, xterm.js, react-mosaic, TanStack
  Query, Zustand, biome. Lives in `ui/`.
- **State:** SQLite self-host (`aiosqlite`); Postgres for an optional hosted path.
- **Compute:** Proxmox LXC (`proxmoxer`).

See tech-spec §4 for the full tree.

## Conventions (non-negotiable)

- **API:** all routes under `/api/v1`; every response uses the standard envelope
  (`data` / `meta` / `error`) from tech-spec §5.1.
- **Naming:** snake_case DB columns; map to camelCase JSON in Pydantic models.
- **Provider seams:** keep `DbProvider` (SQLite → Postgres) and `ComputeProvider`
  (Proxmox → other) abstract. A hosted path must be **additive**, never a
  rewrite — don't leak Proxmox or SQLite specifics past these interfaces.
- **Logging:** structured (JSON) on the backend.
- **Security headers** on API responses; see tech-spec security posture.
- **Tests with every change.** Every bug fix lands a failing-first regression
  test. Test tiers and gates are in `docs/ci-cd-and-testing.md`.
- **SPDX header on every source file** — the two-line header from
  `CONTRIBUTING.md`, in the comment syntax for the language.

## Commits, branches, PRs

- **Conventional Commits** (`feat:`, `fix:`, `docs:`, `chore:` …) — they drive
  versioning. The PR title must itself be a valid Conventional Commit (PRs are
  squash-merged).
- Branch naming: `{type}/{short-description}` (e.g. `feat/terminal-reconnect`).
- Contributions require CLA agreement and `Signed-off-by` (DCO) — see
  `CONTRIBUTING.md`.
- Anything that deviates from the baseline architecture needs an ADR in
  `docs/adr/` before merge.

## Security posture (v1)

- v1 is **LAN-only with no authentication, by design.** Do not add auth
  assumptions into v1 code paths; auth/multi-tenancy is the hosted path.
- **Never commit secrets.** `.env` is gitignored; `.env.example` is the only
  template. No real tokens, hostnames, or secrets in code, tests, or fixtures.
- Keep deployment-specific topology (hostnames, node names, IPs, VMIDs) out of
  the repo — the committed values are illustrative placeholders only.

## Definition of done

A change is done when: it implements the relevant spec section, has tests in the
right tier, passes all CI gates (lint, type-check, tests, scans), carries SPDX
headers, and updates the affected docs. If it touches an open-item, that item is
resolved (or explicitly deferred with the user) first.
