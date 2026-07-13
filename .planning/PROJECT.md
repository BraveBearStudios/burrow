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

## Current Milestone: v1.4 Ship & Harden (GUI Secrets + First Signed Release + Hardening + Live Acceptance)

**Goal:** Consolidate and ship everything in flight: unblock the CI/release
pipeline, merge and finish the ADR-0015 GUI-managed credential store, harden the
repo (Dependabot/CodeQL/backlog), fix the create-UX 504, cut the first real
signed + attested GHCR release, and prove the whole system on the real Proxmox
homelab — ending in a live real-infra acceptance capstone. Cut as **v1.4.0**.

**Target features (Phases 15-22, dependency-ordered):**
- **Pipeline unblock + green main (15):** exclude the release-please branch from
  the active `oss` ruleset (it rejects the bot's ref update), lowercase the GHCR
  owner + add SBOM registry auth in `release.yml` (mixed-case `BraveBearStudios`
  makes syft fail so images ship UNSIGNED), green the Trivy HIGH/CRITICAL gate on
  main (PC1), and resolve the manual-tag/semver skew.
- **Land credential backend + reconcile release train (16):** merge PR #3 onto a
  green main, reconcile release-please to v1.4.0, update the secret-at-rest docs
  to reference ADR-0015, prune the merged local branch.
- **Repo security + backlog hygiene (17):** `dependabot.yml` (pip/npm/actions) +
  automated-security-fixes; enable CodeQL SAST on the default branch (today code
  scanning is 100% Trivy image CVEs, zero source SAST); clear the todo backlog
  (file 07r, fix WR-04, boot-credential-leak-test tautology, em-dash sweep).
- **Credential store frontend + onboarding key (18):** the ship blocker — backend
  is done but curl-only. Admin-secret + credentials wizard steps, admin-gated
  Settings/Credentials screen, audit read endpoint + panel, `X-Burrow-Admin`
  client, `BURROW_SECRET_KEY` auto-generation in onboarding, extended leak test.
- **Create-UX async-202 (19):** `POST /workspaces` returns 202 + a `creating` row,
  the saga runs in a tracked background task, the UI's existing 3s poll drives
  state — curing the ~60s create 504.
- **Signed GHCR release + harden-runner block (20):** clean `v1.4.0` tag → green
  signed + attested `release.yml` → cosign/attestation verify (ACC-03) → flip
  harden-runner egress audit→block from the green run's telemetry (ACC-02).
- **Multi-agent workers research spike (21):** research-only ADR for Cursor /
  Copilot CLI / Codex workers; confirm the credential seam is additive. No build.
- **Live homelab acceptance capstone (22):** ACC-01 items 6-11 on real Proxmox
  (item 9 uses a confirmed 2nd live worker node), credential-store live smoke,
  verify the signed release against a homelab-pulled image.

**Out of this milestone (deferred):** building multi-agent workers (v1.4 is
research-only there); host-prime signed-release delivery (its own onboarding
milestone); the Postgres credential-store impl (hosted-path `NotImplementedError`
stub stays — correct for v1 self-host).

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
- ✓ CI/tooling robustness: `reuse lint` pinned to `--with charset-normalizer` (no `NoEncodingModuleError`); planning artifacts licensed via REUSE.toml so PLAN frontmatter stays line-1 for the gsd-sdk parser — v1.1 (Phase 6; CICD-07/CICD-08; reuse 309/309 compliant)
- ✓ Workspace list fast-reconciles on terminal error/close (LeafPanel wires `onTerminalEvent` → invalidate, not just the ~3s poll) — v1.2 (Phase 7; UI-12; vitest 114/114)
- ✓ Stop/start e2e hardened: panel-scoped locators + per-test id-scoped backend isolation — v1.2 (Phase 7; CICD-09; e2e 7/7)
- ✓ Release automation via release-please (single-root `simple`, manifest seeded 1.1.0 so the first PR proposes v1.2.0, push:main → release PR → `v*` tag → existing `release.yml` publish) — v1.2 (Phase 8; RELX-01) ★ first live release PR = on-runner ACC-02
- ✓ Runner hardening: `harden-runner` (egress audit) step 0 on all 5 CI jobs + every `uses:` SHA-pinned (25 refs, PR-title gate repinned off `@v5`) — v1.2 (Phase 8; RELX-02; reuse 331/331) ★ `egress-policy: block` flip + discovered allowlist = on-runner ACC-02
- ✓ Auto node selection: creating a workspace without a node auto-picks the least-loaded node passing the RAM threshold (over `settings.worker_nodes` via the existing `getNodeMemory` seam, selection inside `_create_lock`); manual pick unchanged; no-fit refuses (409, no overcommit); modal defaults to "Auto (least-loaded)" — v1.2 (Phase 9; WSX-01; api 202 + ui 117 green, seam-leakage green) ★ real multi-node cluster = on-runner ACC-01

### Active

<!-- v1.4 active scope lives in REQUIREMENTS.md (pipeline unblock, credential-store merge + frontend, dependabot/codeql, async-202 create, first signed release, live acceptance capstone). -->

- [ ] Milestone v1.4 Ship & Harden — see REQUIREMENTS.md. v1.3 Go Live shipped 2026-06-26 (setup wizard + opt-in persistence + scrollback + ACC-01 H9 core passed 2026-07-12). v1.4 unblocks the release pipeline, ships the ADR-0015 GUI credential store (backend done; frontend + onboarding key remain), hardens the repo (Dependabot/CodeQL), and finishes the real-infra acceptance (ACC-01 items 6-11 + ACC-02/03 first signed release) — proven live on the homelab.

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
*Last updated: 2026-07-13 — v1.4 "Ship & Harden" started. Scope: unblock the CI/release pipeline (oss-ruleset exclusion + GHCR-lowercase/SBOM-auth + Trivy-green main), merge + finish the ADR-0015 GUI credential store (backend done; frontend + onboarding key remain), repo hardening (Dependabot + CodeQL + backlog), async-202 create-UX, the first real signed + attested GHCR release (ACC-02/03), and a live homelab acceptance capstone (ACC-01 items 6-11, 2nd node confirmed). Multi-agent workers = research-only spike this milestone. Cut as v1.4.0. Phase numbering continues from v1.3's last phase (14) → v1.4 resumes at 15. v1.3 "Go Live" shipped 2026-06-26.*
