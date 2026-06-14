<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Burrow

## What This Is

Burrow is a self-hosted, browser-accessible manager for multiple concurrent Claude
Code sessions. It spins up ephemeral worker containers (Proxmox LXCs) on demand,
each running a Claude Code terminal, and proxies them into a tiling web UI so the
operator can run, watch, and switch between many agent sessions from any device on
their LAN without bogging down the workstation they browse from. It exists to take
advantage of owned homelab hardware instead of hand-stitching tmux, SSH, and
process managers.

It is built for a single self-hosting operator (initially the author) on a Proxmox
homelab. v1 is LAN-only with no authentication, by design.

## Core Value

One operator can create, watch, and manage many concurrent Claude Code sessions
from a browser, with each session running in an ephemeral, reproducible container
that is gone when destroyed. If everything else fails, *creating a workspace and
getting a live, interactive Claude Code terminal in the browser* must work.

## Current Milestone: v1.1 UI Polish + Stop/Start Controls

**Goal:** Surface the backend-ready stop/start controls in the UI and close the
carried v1.0 drawer + CI tech-debt — all dev-box-buildable and CI-provable over
the Fake provider.

**Target features:**
- Explicit stop/start controls in the workspace UI (WS-06/WS-07), enable/disable
  driven by the state machine (running→stop, stopped→start).
- Activity-drawer polish: phone full-width responsive sheet (V2), `--accent-line`
  focus ring (V3), custom scrollbar (V4) — 04-UI-REVIEW scored 22/24.
- CI robustness: pin the reuse-lint encoding dep (`uvx --with charset-normalizer`);
  reconcile the SPDX-comment-before-frontmatter convention with the gsd-sdk
  `phase-plan-index` parser.

**Out of this milestone (tracked, not v1.1 build):** the dev-homelab smoke + first
CI run + real GHCR release (the v1.0 ★ acceptance items) — they need real
Proxmox / Docker / GHCR, off the dev box, and remain v1.0 acceptance debt.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. CI-provable contracts proven green over the Fake
provider; real-infra acceptance (★) is the dev-homelab smoke, not CI, by design. -->

- ✓ Browser UI lists all workspaces with live status (creating / running / stopped / error) — v1.0
- ✓ Operator creates a workspace from a git repo + branch (clone golden LXC, boot, wait for health) — v1.0 ★ real boot = homelab smoke
- ✓ Tiling multi-panel terminal UI (xterm.js + react-mosaic): open, split, drag, resize — v1.0
- ✓ Live terminal streaming via WebSocket proxy bridging the browser to ttyd — v1.0 ★ real ttyd = homelab smoke
- ✓ Terminal auto-reconnects on transient disconnect, with a reconnecting overlay — v1.0
- ✓ Operator can stop, start, and destroy a workspace; state machine enforced — v1.0 (destroy wired to the terminate action during the v1.0 audit; explicit stop/start UI is backend-ready but unsurfaced — see Active)
- ✓ Per-workspace event log + a slide-in activity drawer surfacing it — v1.0
- ✓ Capacity guard refuses creation over the node-RAM threshold; atomic check+reserve closes the concurrency overcommit race — v1.0 ★ under-real-load = homelab smoke
- ✓ Workers are reproducible: CLAUDE.md + a ref-pinned plugin manifest pulled fresh at boot, no credentials left behind — v1.0 ★ real boot = homelab smoke
- ✓ Golden template LXC + worker boot pipeline (`provision-template.sh`, `burrow-boot.sh`) — v1.0 ★ real provision/boot = homelab smoke
- ✓ `DbProvider` / `ComputeProvider` seams kept abstract (hosted path additive) — v1.0 (seam-leakage test enforced)
- ✓ Standard `data`/`meta`/`error` envelope on every `/api/v1` route; structured JSON logging; security headers — v1.0
- ✓ CI/CD: static gates → tiered tests → build → image scan → SBOM → sign → SLSA provenance → GHCR — v1.0 ★ real GHCR publish + cosign/attestation verify = CD
- ✓ Auto-stop idle workspaces (in-process reconciler) + restore/reconnect terminal after refresh — v1.0 ★ real idle window = homelab smoke
- ✓ Orphan reaper reconciles desired vs actual (destroys row-less pool CTs on their actual node, frees leaked VMIDs, fails timed-out `creating` rows) — v1.0 ★ real orphan = homelab smoke
- ✓ Explicit stop/start controls in the workspace UI (WS-06/WS-07), state-machine-gated, with a `stopped` placeholder + Start CTA — v1.1 (Phase 5; UI-07/UI-08, vitest + Playwright green over Fake)
- ✓ Activity-drawer polish: phone full-width responsive sheet ≤375px, global `--accent-line` focus ring, custom Burrow scrollbar — v1.1 (Phase 5; UI-09/UI-10/UI-11; UI audit 23/24)

### Active

<!-- v1.1 candidates — the tech-debt carried out of the v1.0 close-out audit. -->

- [ ] CI robustness (Phase 6, next): pin the reuse-lint encoding dep (`uvx --with charset-normalizer`); reconcile the SPDX-comment-before-frontmatter convention with the gsd-sdk `phase-plan-index` parser
- [ ] Run and record the dev-homelab smoke + first CI release (flip the ★ items above + the per-phase `*-HUMAN-UAT.md` checklists to passed)

### Out of Scope

<!-- Explicit boundaries. Reasoning included to prevent re-adding. -->

- Authentication and multi-tenancy — v1 is LAN-only single-user by design; auth/JWT/RLS belong to the additive hosted path (tech-spec §13), not v1 code paths.
- Postgres as the primary database — SQLite via `aiosqlite` is the v1 store (ADR-0001); `postgresProvider.py` is a stub behind the seam only.
- Cloud / container compute backend — v1 targets Proxmox LXC only; the `ComputeProvider` seam exists but a non-Proxmox impl is out of scope.
- Real-Proxmox exercise in CI — CI proves clean builds + inter-app behavior against a `FakeComputeProvider` and mocked Proxmox; real-infra validation happens in the dev environment, not CI (ci-cd §4.4).
- Native mobile app — browser-first; responsive web only.
- Secrets manager — v1 uses a gitignored `.env`; a secrets manager is hosted-path scope.

## Context

- **Repo state (post-v1.0):** the spec is implemented. `api/` is a FastAPI control plane
  (create saga, state machine, both providers behind the seams, bootconfig endpoint, the
  in-process reconciler/reaper, capacity lock) with a hermetic pytest pyramid (173 tests over
  the Fake provider). `ui/` is a Vite + React 19 + xterm + react-mosaic app (tiling terminals,
  reconnect/restore, activity drawer) with vitest (97) + Playwright e2e. `cc-worker-config/`
  carries the host-prime kit + the worker template (`provision-template.sh`, `burrow-boot.sh`,
  plugin manifest + schema). `Dockerfile.api`/`Dockerfile.ui` + `ci.yml` (build/scan) + a
  `release.yml` supply-chain path complete the release surface. REUSE-compliant (275/275).
  **Real-Proxmox / real-GHCR acceptance remains the dev-homelab smoke + first CI run** — see
  the per-phase `*-HUMAN-UAT.md` and `milestones/v1.0-MILESTONE-AUDIT.md`.
- **Two repos:** `burrow` (this repo — control plane API + UI + CI) and a separate
  `cc-worker-config` (worker golden-template spec, plugin manifest, master CLAUDE.md,
  systemd/nginx). Worker reproducibility depends on the second repo.
- **Design handoff exists:** `design/Burrow-handoff/` + `docs/design/` carry a UI
  mockup, design-system tokens (colors/type CSS), and a design prompt — frontend
  phases should honor these.
- **Open questions to resolve before the relevant phase (surface, do not silently
  implement around — per project convention):**
  - LXC IP assignment: **RESOLVED → static IP computed from VMID**, worker range excluded from DHCP (DHCP discovery is unreliable for unprivileged LXC; ADR pending in Phase 0).
  - Boot-config injection mechanism: `pct exec`/`pct push` are **not** in the Proxmox HTTPS API, so the spec's push approach is impossible — pull-at-boot (worker fetches config from an internal endpoint) is recommended vs SSH-push to the node; ADR in Phase 0. See `research/PROXMOX-PRIMING.md`.
  - Proxmox ACL scoping for the `burrow@pve` token: `/pool/burrow-workers` (tight) vs `/vms` (simpler, broader) — resolve before Phase 1.
  - ttyd `--once`: closing the browser tab terminates the Claude session — decide detach-vs-terminate UX.
  - Worker node selection: manual pick in the create modal first, auto-select later.
  - Plugin update cadence: pull `cc-worker-config` at boot (latest) vs snapshot at create (reproducible).
  - `burrow-api` runtime base: `python:3.12-slim` vs distroless (spec: start slim).
  - Release automation: release-please vs semantic-release.
  - Coverage thresholds + ratchet policy (start ~80%).
  - Vuln waiver allowlist format + expiry/owner policy.
  - harden-runner egress allowlist: adopt now or defer post-MVP.

## Constraints

- **Tech stack (fixed by spec):** FastAPI / Python 3.12 / uv / ruff / mypy (`api/`); Vite + React 19 + TypeScript / biome, xterm.js, react-mosaic, TanStack Query, Zustand (`ui/`); SQLite via `aiosqlite`; Proxmox via `proxmoxer`; ttyd in workers.
- **API contract:** every route under `/api/v1`; every response uses the standard envelope (`data`/`meta`/`error`). (Resolves the tech-spec §5.2 examples that omit `/v1` — CLAUDE.md + ci-cd doc are authoritative.)
- **Naming:** snake_case DB columns mapped to camelCase JSON in Pydantic models.
- **Security posture (v1):** LAN-only, no auth — do not bake auth assumptions into v1 paths; security headers on API responses; never commit secrets (`.env` gitignored, `.env.example` only template); keep deployment topology (hostnames, node names, IPs, VMIDs) out of the repo as placeholders.
- **Provider seams:** `DbProvider` (SQLite→Postgres) and `ComputeProvider` (Proxmox→other) stay abstract; Proxmox/SQLite specifics must not leak past these interfaces.
- **Infrastructure dependency:** golden-template and control-plane phases require a real Proxmox host + LAN; they cannot be created/booted or end-to-end verified from a dev workstation. CI deliberately never touches real Proxmox.
- **Testing (non-negotiable):** every change lands tests in the right tier; every bug fix lands a failing-first regression test; tiers = static gates → unit → integration (real SQLite, mocked Proxmox, stub ttyd) → e2e (FakeComputeProvider + Playwright) → container smoke; coverage gate (~80%, ratcheting).
- **Supply chain:** multi-stage Dockerfiles, base images pinned by digest, deterministic installs from lockfiles; image scan fails on HIGH/CRITICAL; SBOM (syft), cosign keyless signing, SLSA provenance; third-party actions pinned to commit SHA; least-privilege tokens.
- **Licensing/governance:** AGPL-3.0-or-later; SPDX two-line header on every source file; OCI source/revision labels (AGPL §13); Conventional Commits drive versioning; PRs squash-merged with a Conventional-Commit title; contributions require CLA + DCO `Signed-off-by`; deviations from baseline architecture need an ADR in `docs/adr/`.

## Key Decisions

<!-- Decisions that constrain future work. Outcome: ✓ Good / ⚠️ Revisit / — Pending -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| SQLite-first behind `DbProvider` (ADR-0001) | Single-user self-host warrants no external DB dependency; Postgres is a drop-in for the hosted path | — Pending |
| All routes under `/api/v1` with `data`/`meta`/`error` envelope | Consistency + versioning; resolves the spec's un-versioned examples | — Pending |
| Provider seams (`DbProvider`, `ComputeProvider`) kept abstract | Hosted/multi-tenant path is additive, never a rewrite | — Pending |
| Ephemeral workers cloned from a golden template LXC | No snowflake state; reproducible workspaces; plugin drift impossible | — Pending |
| v1 LAN-only, no auth | Self-host single-user target; auth is hosted-path scope | — Pending |
| CI proves builds + inter-app behavior, not live infra (FakeComputeProvider) | Hermetic, deterministic CI; real Proxmox validated in dev | — Pending |
| Proxmox priming is a Phase-0 operator kit (`cc-worker-config/lxc/host-prime/` + `PRIMING.md`), not runtime | The one-time bootstrap (least-priv user/role/privsep token, CT template, control-plane box) must exist before any create; idempotent, operator-run | — Pending |
| Boot config delivered pull-at-boot (recommended), not `pct`-over-API or cloud-init | `pct exec`/`pct push` are absent from the HTTPS API; pull-at-boot keeps the `ComputeProvider` seam HTTPS-only and secrets off worker env; final lock via Phase 0 ADR | — Pending |
| Planning profile = Quality (Opus), standard granularity, parallel plans | Real greenfield build warrants depth; matches spec's ~5-phase shape | — Pending |
| Setup pauses at ROADMAP (no autonomous build this session) | Operator reviews the phase plan before any code is built | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-14 — Phase 5 complete (stop/start UI + drawer polish shipped, verified 5/5, UI audit 23/24). Next: Phase 6 (CI/tooling robustness).*
