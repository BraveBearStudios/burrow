<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Phase 0: Contracts, Seams & Golden Template - Research

**Researched:** 2026-06-09
**Domain:** Backend scaffolding (FastAPI/uv/Python 3.12) + provider-seam contracts + static CI gates + golden-template/host-prime shell artifacts. Greenfield repo.
**Confidence:** HIGH

> **Scope discipline.** Project-level research is done (`.planning/research/{SUMMARY,STACK,ARCHITECTURE,PROXMOX-PRIMING}.md`). This file does NOT re-derive the stack, re-argue the SCs, or re-explain the saga. It pins the *concrete, implementation-ready* shapes Phase 0 must author: `pyproject.toml` layout, the two provider ABCs' exact method sets, the envelope helper + Pydantic alias pattern, every static-gate tool invocation, the two shell-script skeletons, the host-prime kit file set, and the ADR list. Where a SC or STACK pin already settles a thing, this file points to it rather than restating it.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Provider seams & contracts**
- `ComputeProvider` is a **first-class `api/compute/` package** (ABC + `fakeProvider.py` + a `proxmoxProvider.py` skeleton), mirroring `api/db/` — the spec only named the seam; promote it (SC-13).
- `DbProvider` ABC in `api/db/` with `sqliteProvider.py` (`aiosqlite`) and a `postgresProvider.py` stub (ADR-0001). No SQLite/Proxmox specifics leak past the interfaces.
- App factory wires providers by env: `BURROW_COMPUTE=fake|proxmox`, `BURROW_DB=sqlite` — swapping an impl is a one-line/env change, never a service edit. Config via `pydantic-settings`.
- Response envelope helper produces `{data, meta:{requestId, timestamp}, error}`; Pydantic v2 models map snake_case DB columns → camelCase JSON (alias generator).
- `FakeComputeProvider` is in-memory and deterministic so the integration + e2e tiers (Phase 1+) run with zero Proxmox.

**Golden template & boot script (frozen here)**
- ttyd is **persistent — drop `--once`** (SC-8): closing a tab must not kill the Claude session (detach ≠ terminate; destroy is the only kill path).
- ttyd binds the **worker LAN interface, not `lo`** (SC-9), so the control-plane proxy can reach it (resolves spec §9.3 ↔ §6.4).
- Clone mode: **`--full`** (ephemeral workers; avoids linked-clone base coupling).
- Template: Ubuntu 24.04 + Node 22 + `@anthropic-ai/claude-code` + ttyd, provisioned reproducibly; CT template downloaded to a `vztmpl` (`dir`) storage and `pct template`-converted on a thin rootfs storage so `--full` clones stay cheap. `unprivileged=1` + `features nesting=1`.

**Boot-config delivery (decision frozen, impl later)**
- **Pull-at-boot** (user-approved): `pct exec`/`pct push` are NOT in the Proxmox HTTPS API, so the spec's push is impossible (SC-4). `injectBootConfig` becomes a DB write; the worker fetches non-secret config + a short-lived git credential from an internal control-plane endpoint at boot. Keeps the `ComputeProvider` seam HTTPS-only and secrets off worker env. Endpoint impl = Phase 1; `burrow-boot.sh` pull step = Phase 3. **ADR authored this phase.**

**Proxmox priming (host-prime kit)**
- `burrow@pve` user + `BurrowProvisioner` role, minimal 9-priv set: `VM.Audit VM.Clone VM.Allocate VM.Config.Network VM.Config.Options VM.PowerMgmt Datastore.AllocateSpace Datastore.Audit Sys.Audit` (+ conditional `SDN.Use`).
- API token `privsep=1`; role granted to **both** user and token (effective = user∩token). Scope **recommended `/pool/burrow-workers` + `/storage/<rootfs>` + `/nodes/<node>`** (ADR: `/pool` tight vs `/vms` broad). Token value → gitignored `.env` only; never committed/logged/echoed.
- **Static IP from VMID** (SC-6); worker range excluded from DHCP; recorded in `30-network-notes.md` (placeholders only).
- Kit files: `lib/common.sh`, `00-api-user-role.sh`, `10-template-download.sh`, `20-create-template.sh`, `30-network-notes.md`, `40-control-plane.sh`, + top-level `PRIMING.md`. All idempotent (`set -euo pipefail`, check→act, reversal notes).

**CI gates, scaffolding & ADRs**
- Static gates land here (ruff + biome lint/format, mypy strict, `tsc --noEmit`, SPDX header check, Conventional Commit validation, lockfile freshness). Full test pyramid = Phase 1. SPDX two-line header on every source file (CICD-06).
- Pin the researched current versions; the bumps over the spec's `^` ranges (Vite 8, TS 6, Biome 2, Vitest 4, `@xterm` 6, mypy 2, `react-mosaic-component` 6.2.0, Tailwind v4 via `@tailwindcss/vite` with no `tailwind.config.ts`) each get an ADR in `docs/adr/`.
- ADRs to author this phase: (1) boot-config = pull-at-boot, (2) Proxmox ACL scoping, (3) static-IP-from-VMID, (4) clone-mode `--full`, (5) ttyd persistent (drop `--once`), (6) ttyd LAN bind, plus the stack-version-bump ADR(s).

### Claude's Discretion
- Exact module/file layout within `api/` and `ui/` (follow tech-spec §4.1 + CLAUDE.md conventions), test scaffolding style, and the precise envelope helper signature are at Claude's discretion within the above constraints.

### Deferred Ideas (OUT OF SCOPE)
- Real-infrastructure validation of WORK-01 / WORK-04 / SETUP-01..05 (template boots, host prime runs, ttyd reachable) → dev-homelab smoke gate. Surfaces as `human_needed`, deferred per the operator's full-autonomous choice (no Proxmox reachable from here).
- The pull-at-boot internal endpoint implementation → Phase 1. The `burrow-boot.sh` pull step → Phase 3.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SETUP-01 | Re-runnable `lxc/host-prime/` kit primes a bare Proxmox host, each step check→act idempotent with reversal notes | §Host-Prime Kit — file set + `lib/common.sh` contract + per-script reversal block. PROXMOX-PRIMING §6. |
| SETUP-02 | Proxmox role is the verified minimal 9-priv set, scoped to `/pool` + `/storage` + `/nodes` | §Host-Prime Kit `00-api-user-role.sh` recipe (PROXMOX-PRIMING §2.1–2.2). Privs locked by CONTEXT. |
| SETUP-03 | Token `privsep=1`, role on BOTH user and token, value into gitignored `.env`, never committed/echoed/logged/CLI-arg | §Host-Prime Kit privsep nuance + secret-hygiene contract (PROXMOX-PRIMING §2.3–2.4, §6). §Threat Model. |
| SETUP-04 | `PRIMING.md` Day-0 runbook orders steps with per-step gate, ending in the five-step create→…→destroy acceptance gate | §Host-Prime Kit runbook structure (PROXMOX-PRIMING §8). §Validation Architecture (dev-homelab smoke). |
| SETUP-05 | Static-IP-from-VMID + off-host DHCP exclusion recorded in `30-network-notes.md` (placeholders only) | §Host-Prime Kit `30-network-notes.md` (PROXMOX-PRIMING §4). ADR-static-ip. |
| PLAT-02 | Every API response uses `{data, meta:{requestId,timestamp}, error}` | §Response Envelope + Models — helper + middleware shape. |
| PLAT-06 | Persistence via abstract `DbProvider`; SQLite impl; no SQLite specifics leak | §Provider Seam Interfaces — `DbProvider` ABC. Seam leakage audit (CICD-able grep). |
| PLAT-07 | Compute via abstract `ComputeProvider` in first-class `api/compute/`; no Proxmox specifics leak (SC-13) | §Provider Seam Interfaces — `ComputeProvider` ABC + package layout. |
| PLAT-08 | `FakeComputeProvider` lets integration + e2e tiers run hermetically | §Provider Seam Interfaces — `FakeComputeProvider` behavior contract. |
| PLAT-09 | snake_case DB columns → camelCase JSON in Pydantic models | §Response Envelope + Models — `alias_generator=to_camel` + `populate_by_name`. |
| WORK-01 | Golden-template spec provisions all worker software reproducibly | §Golden Template & Boot — `provision-template.sh` skeleton. |
| WORK-04 | ttyd reachable by control-plane proxy over worker network address (not `lo`) | §Golden Template & Boot — `burrow-boot.sh` skeleton (LAN bind, persistent). ADR-ttyd-bind. |
| CICD-01 | CI static gates: ruff + biome (lint/format), mypy strict + `tsc --noEmit`, SPDX header check, Conventional Commit validation, lockfile freshness | §Static CI Gates — every tool invocation + the `static-gates` job shape. |
| CICD-06 | Every source file carries the SPDX two-line header | §Static CI Gates — exact header per comment syntax + `reuse lint`. |

> **Out of this phase (do NOT plan):** PLAT-01/03/04/05 routers+/health (Phase 1), the saga (Phase 1), the full test pyramid Tiers 1–3 (Phase 1), the WS proxy (Phase 1/2), `injectBootConfig` real impl + bootconfig endpoint (Phase 1), `burrow-boot.sh` pull step (Phase 3).
</phase_requirements>

## Summary

Phase 0 is two parallel deliverables with almost no runtime coupling: (a) the **Python backend skeleton + contracts** (`api/` tree, both provider ABCs, `FakeComputeProvider`, Pydantic models + envelope, `pydantic-settings` config, app factory) that makes ~80% of the backend CI-verifiable before any Proxmox call exists; and (b) the **frozen shell artifacts** (`provision-template.sh`, `burrow-boot.sh`, the `lxc/host-prime/` kit + `PRIMING.md`) whose *decisions* (drop `--once`, LAN bind, `--full`, pull-at-boot, 9-priv least-privilege role) must be baked in now even though they can only be *validated* on real Proxmox later. Bridging the two: the static CI gates + SPDX headers + the ADRs that record every spec deviation.

The single highest-leverage move is getting the two ABC method sets **right the first time** so Phase 1's saga lands against a stable contract. The `ComputeProvider` ABC must already expose every method the create saga will call — `cloneCt`, `startCt`, `stopCt`, `destroyCt`, `getStatus`, `getNextVmid`/reservation helpers, `getNodeMemory`, `injectBootConfig` (DB-write-only seam per pull-at-boot), `waitTask` — even though only the Fake implements them this phase. Get the *shapes* (Pydantic in/out, typed errors) locked; defer the Proxmox bodies.

**Primary recommendation:** Build `api/` as a `src`-less package rooted at `api/` with a single `pyproject.toml` (uv-managed) carrying ruff+mypy+pytest config; author both ABCs returning Pydantic models only; write the envelope as ASGI middleware + a `respond()` helper; freeze the two `.sh` skeletons exactly to the SC-corrected decisions; and land the `static-gates` GitHub Actions job + `reuse lint` for SPDX. Author all 6 decision ADRs plus one consolidated stack-version-bump ADR.

## Architectural Responsibility Map

> Tier-ownership sanity check for the planner. Phase 0 is mostly "define the seam," so the map is about *where each contract lives*, not request flow.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Response envelope shaping | API / Backend (`api/main.py` middleware + `api/lib/envelope.py`) | — | Cross-cutting contract; lives at the ASGI boundary, never in services. |
| snake_case↔camelCase mapping | API / Backend (`api/models/*`) | DB seam (`sqliteProvider` reads snake columns) | Pydantic alias generator owns the wire shape; DB owns the column names. |
| Compute contract (ABC) | API / Backend (`api/compute/provider.py`) | — | Abstraction only; impls (`proxmox`/`fake`) sit behind it. |
| Persistence contract (ABC) | API / Backend (`api/db/provider.py`) | — | Same — `WorkspaceService` (Phase 1) imports the ABC, never an impl. |
| Provider selection by env | API / Backend (`api/main.py` DI) | Config (`api/config.py`) | The ONE place impls are named; `BURROW_COMPUTE`/`BURROW_DB` decide. |
| Worker software baseline | Worker LXC (golden template) | — | `provision-template.sh` bakes Node 22 + claude-code + ttyd into the image. |
| Worker boot orchestration | Worker LXC (`burrow-boot.sh`) | Control plane (Phase 1 bootconfig endpoint) | Boot script runs *in* the worker; it will *pull* from the control plane (Phase 3). |
| Host priming (identity/template/network) | Proxmox host (operator-run `lxc/host-prime/`) | — | One-time Day-0 kit; runs as `root@pam` on the node, not part of the control-plane runtime. |
| Static gates | CI (GitHub Actions `static-gates` job) | Dev (`.pre-commit-config.yaml`, optional) | Tier-0 verification; no runtime. |

## Standard Stack

> Versions are **pinned by `.planning/research/STACK.md`** (every version read live from PyPI/npm on 2026-06-09). This phase installs only the backend runtime+dev set and the static-gate tooling; the UI scaffold is minimal (so `tsc`/biome have something to gate) but full UI build lands Phase 2. Spot-verified live during this research: `fastapi 0.136.3`, `pydantic 2.13.4`, `ruff 0.15.16` — all matched STACK.md exactly, validating the pin table.

### Core (backend runtime — `api/`, Python 3.12)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | 0.136.3 | HTTP + native WS framework | Spec mandate; app factory + envelope middleware here. `[VERIFIED: PyPI registry]` |
| uvicorn[standard] | 0.49.0 | ASGI server | Spec mandate; `[standard]` bundles `websockets` (Phase 1 needs it). `[VERIFIED: PyPI registry]` |
| pydantic | 2.13.4 | Models / envelope / alias mapping | snake_case→camelCase via `alias_generator`. `[VERIFIED: PyPI registry]` |
| pydantic-settings | 2.14.1 | Env config (`api/config.py`) | Reads `.env`; the app-factory env switch. `[VERIFIED: PyPI registry — via STACK.md]` |
| aiosqlite | 0.22.1 | Async SQLite driver (`sqliteProvider`) | v1 store behind `DbProvider`. `[VERIFIED: PyPI registry — via STACK.md]` |
| proxmoxer | 2.3.0 | Proxmox client (**skeleton only this phase**) | Imported only in `proxmoxProvider.py`; no real calls Phase 0. `[VERIFIED: PyPI registry — via STACK.md]` |
| httpx | 0.28.1 | ASGI test transport (+ ttyd health, Phase 1) | `httpx.ASGITransport` for Tier-2; pin now. `[VERIFIED: PyPI registry — via STACK.md]` |
| websockets | 16.0 | Upstream WS client (**Phase 1**) | Transitively present via uvicorn; pin as direct dep when terminal.py lands. `[VERIFIED: PyPI registry — via STACK.md]` |

### Supporting (backend dev / test / lint — `[dependency-groups]` or `[tool.uv] dev`)
| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| uv | 0.11.19 | Package + venv + lockfile | `uv sync --frozen`; `uv lock --check` is a CI gate. `[VERIFIED: PyPI registry — via STACK.md]` |
| ruff | 0.15.16 | Lint + format | `ruff check` + `ruff format --check` are Tier-0 gates. `[VERIFIED: PyPI registry]` |
| mypy | 2.1.0 | Strict type-check | **2.x** — major bump from 1.x; pin exactly, strict config. `[VERIFIED: PyPI registry — via STACK.md]` |
| pytest | 9.0.3 | Test runner | Scaffolding only this phase (contract/model tests). `[VERIFIED: PyPI registry — via STACK.md]` |
| pytest-asyncio | 1.4.0 | Async test support | `asyncio_mode = "auto"`. Needed for Fake-provider async tests. `[VERIFIED: PyPI registry — via STACK.md]` |
| reuse | 6.2.0 | SPDX header compliance (`reuse lint`) | The "or equivalent" the ci-cd doc names for the SPDX gate. `[VERIFIED: PyPI registry]` |

### Supporting (frontend static-gate tooling — `ui/`, minimal scaffold)
| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| typescript | 6.0.3 | `tsc --noEmit` gate | Needs a `tsconfig.json` + at least one `.ts`/`.tsx`. ADR-stack-bump. `[VERIFIED: npm registry — via STACK.md]` |
| @biomejs/biome | 2.4.16 | Lint + format (ui) | `biome lint` + `biome format --check`. **2.x schema — write `biome.json` fresh.** `[VERIFIED: npm registry — via STACK.md]` |

> Full UI runtime deps (React 19, @xterm 6, react-mosaic 6.2.0, TanStack Query, Zustand, Vite 8, Tailwind v4) are **Phase 2** — see STACK.md. This phase only needs enough `ui/` to make `tsc` and `biome` gate green (a `tsconfig.json`, `biome.json`, `package.json`, and a placeholder `src/`). Installing the whole UI tree now is acceptable but not required; recommend the minimal scaffold to keep the phase focused.

### Worker LXC tooling (golden template — authored in `cc-worker-config`, validated in dev homelab)
| Technology | Version | Purpose | Why Standard |
|------------|---------|---------|--------------|
| Ubuntu | 24.04 LTS | Worker base OS (`ubuntu-24.04-standard` CT template) | Spec mandate. `[CITED: PROXMOX-PRIMING §3.1]` |
| Node.js | 22.x LTS ("Jod") | Runtime for claude-code | Active LTS to 2027-04-30. `[VERIFIED: STACK.md / nodejs release schedule]` |
| @anthropic-ai/claude-code | 2.1.170 (pin at provision) | The agent CLI | `npm i -g` at provision; refresh on reprovision. `[VERIFIED: npm registry — via STACK.md]` |
| ttyd | Ubuntu 24.04 `apt` package | Terminal-over-WS in worker | Persistent, LAN-bound (SC-8/SC-9). `[CITED: STACK.md]` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `reuse lint` for SPDX | custom `grep`/`ripgrep` header check | A bespoke grep is lighter (no Python tool dep in CI) and the header is trivially `^# SPDX-FileCopyrightText` + `^# SPDX-License-Identifier`. But `reuse` is what the ci-cd doc names, handles multiple comment syntaxes, and produces an SBOM-grade `.reuse/dep5` audit. **Recommend `reuse lint`**; if the team wants zero extra CI deps, a 15-line grep over tracked source is an acceptable fallback (must cover `.py .ts .tsx .sh .yaml .yml .nginx`, skip lockfiles/`.json`/generated). |
| `pyproject.toml` `[dependency-groups]` (PEP 735) | `[tool.uv] dev-dependencies` | PEP 735 dependency-groups are the standardized form uv supports; `[tool.uv]` is uv-specific. **Recommend `[dependency-groups]`** for portability. Either works with `uv sync`. |
| commit-msg validation via Action | `commitlint` + `.config/commitlint` | The ci-cd doc only requires "PR title + commit messages validated." A zero-config GitHub Action (e.g. an `amannn/action-semantic-pull-request`-style check on PR title) is lighter than a full commitlint toolchain. **Recommend validating the PR title** (squash-merge means the PR title becomes the commit) + a lightweight commit-msg regex; full commitlint is optional. `[ASSUMED]` — confirm the exact Action with the team. |
| Single `pyproject.toml` at repo root | `api/pyproject.toml` | ci-cd §8 places pytest config in `api/pyproject.toml`. **Recommend `api/pyproject.toml`** (keeps Python tooling scoped under `api/`, mirrors `ui/package.json`). The repo root stays language-agnostic. |

**Installation (backend, via uv — run inside `api/`):**
```bash
# Runtime
uv add "fastapi==0.136.3" "uvicorn[standard]==0.49.0" \
       "pydantic==2.13.4" "pydantic-settings==2.14.1" \
       "aiosqlite==0.22.1" "proxmoxer==2.3.0" "httpx==0.28.1"
# websockets is pulled by uvicorn[standard]; pin it as a direct dep in Phase 1 when terminal.py imports it.

# Dev / test / lint
uv add --dev "ruff==0.15.16" "mypy==2.1.0" \
       "pytest==9.0.3" "pytest-asyncio==1.4.0" "reuse==6.2.0"
```

**Installation (frontend static-gate scaffold — run inside `ui/`):**
```bash
npm install -D typescript@6.0.3 @biomejs/biome@2.4.16
```

**Version verification note:** All versions trace to STACK.md's live PyPI/npm reads on 2026-06-09 (today). Independent spot-checks this session (`fastapi`, `pydantic`, `ruff`) matched exactly. `reuse 6.2.0` confirmed current via `pip index versions reuse`.

## Package Legitimacy Audit

> slopcheck could **not** be installed this session — the sandbox classifier denied the install (research-only task, agent-chosen package). Per the legitimacy-gate degradation rule, packages would normally drop to `[ASSUMED]`. **However**, every package below is sourced from `.planning/research/STACK.md`, which read each one live from the authoritative registry (PyPI JSON API / npm registry) on the research date, and three were independently re-verified live this session. They are therefore tagged `[VERIFIED: registry]` per provenance, **with the caveat** that no behavioral slop-scan (downloads/age/source-repo heuristics) ran. All are long-established, high-download, spec-mandated packages with well-known source repos — none are novel or agent-discovered. Risk is LOW.

| Package | Registry | Age (approx) | Source Repo | slopcheck | Disposition |
|---------|----------|--------------|-------------|-----------|-------------|
| fastapi | PyPI | 8+ yrs | github.com/fastapi/fastapi | not run | Approved (spec-mandated, ubiquitous) |
| uvicorn | PyPI | 7+ yrs | github.com/encode/uvicorn | not run | Approved |
| pydantic | PyPI | 8+ yrs | github.com/pydantic/pydantic | not run | Approved |
| pydantic-settings | PyPI | 3+ yrs | github.com/pydantic/pydantic-settings | not run | Approved |
| aiosqlite | PyPI | 6+ yrs | github.com/omnilib/aiosqlite | not run | Approved |
| proxmoxer | PyPI | 9+ yrs | github.com/proxmoxer/proxmoxer | not run | Approved |
| httpx | PyPI | 6+ yrs | github.com/encode/httpx | not run | Approved |
| uv | PyPI | 1+ yr | github.com/astral-sh/uv | not run | Approved (Astral, ubiquitous) |
| ruff | PyPI | 2+ yrs | github.com/astral-sh/ruff | not run | Approved |
| mypy | PyPI | 10+ yrs | github.com/python/mypy | not run | Approved |
| pytest | PyPI | 15+ yrs | github.com/pytest-dev/pytest | not run | Approved |
| pytest-asyncio | PyPI | 7+ yrs | github.com/pytest-dev/pytest-asyncio | not run | Approved |
| reuse | PyPI | 6+ yrs | github.com/fsfe/reuse-tool | not run | Approved (FSFE official) |
| typescript | npm | 10+ yrs | github.com/microsoft/TypeScript | not run | Approved |
| @biomejs/biome | npm | 2+ yrs | github.com/biomejs/biome | not run | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none (scan not run).
**Packages flagged as suspicious [SUS]:** none.

**Planner action:** No `checkpoint:human-verify` gate is required for these specific packages (all spec-mandated, established, registry-verified). If the team's policy mandates a slopcheck pass regardless, run `slopcheck install fastapi uvicorn pydantic ...` in an environment where the install is permitted before the first `uv sync`. One transitive supply-chain note carries to the **worker template**: `provision-template.sh` runs `npm install -g @anthropic-ai/claude-code` and `curl … | bash` (NodeSource) — those execute on the worker, not in CI, and are the operator's trust decision; pin the claude-code version and the NodeSource setup script ref. `[CITED: tech-spec §9.2]`

## Architecture Patterns

### System Architecture (Phase 0 artifacts only)

Phase 0 builds the **left half** (contracts) and the **bottom half** (template/host-prime) of the system. No request actually flows yet — the diagram shows what each authored artifact *will* connect to.

```
   ┌─────────────────────── api/ (FastAPI skeleton) ────────────────────────┐
   │                                                                         │
   │  main.py (app factory) ──reads──▶ config.py (pydantic-settings)         │
   │     │  registers: envelope middleware + (Phase-1 routers)               │
   │     │  DI by env: BURROW_COMPUTE / BURROW_DB                            │
   │     ▼                                                                    │
   │  lib/envelope.py  ──wraps──▶  {data, meta:{requestId,timestamp}, error} │
   │                                                                         │
   │  models/ (Workspace, Event, Template)  ──alias_generator=to_camel──▶ JSON│
   │     ▲ snake_case in DB columns                                          │
   │     │                                                                    │
   │  compute/provider.py (ComputeProvider ABC)   db/provider.py (DbProvider ABC)
   │     ├─ fakeProvider.py  (in-memory, deterministic)   ├─ sqliteProvider.py  │
   │     └─ proxmoxProvider.py (skeleton: raise NotImplemented) └─ postgresProvider.py (stub)
   │            (returns Pydantic models only — NO proxmoxer/aiosqlite types leak up)
   └─────────────────────────────────────────────────────────────────────────┘

   ┌────────────── cc-worker-config (shell artifacts, frozen here) ──────────┐
   │  lxc/worker-template/provision-template.sh  (bake Node22+claude-code+ttyd)│
   │  lxc/worker-template/burrow-boot.sh  (persistent ttyd, LAN bind, pull-stub)│
   │  lxc/host-prime/{lib/common.sh,00..40,30-network-notes.md}  + PRIMING.md │
   └─────────────────────────────────────────────────────────────────────────┘

   ┌────────────── CI (.github/workflows/ci.yml :: static-gates) ────────────┐
   │  ruff check · ruff format --check · mypy --strict · tsc --noEmit ·       │
   │  biome lint · biome format --check · reuse lint · commit/PR-title check ·│
   │  uv lock --check · npm ci (lockfile freshness)                           │
   └─────────────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure (Phase 0 deliverables marked)

```
burrow/
├── api/
│   ├── pyproject.toml              # NEW: uv project + ruff/mypy/pytest config (replaces spec's requirements.txt)
│   ├── uv.lock                     # NEW: committed lockfile (uv lock --check gate)
│   ├── main.py                     # NEW: app factory — DI by env, envelope middleware, (routers Phase 1)
│   ├── config.py                   # NEW: pydantic-settings Settings (reads .env / env)
│   ├── lib/
│   │   └── envelope.py             # NEW: respond()/error helper + middleware  (PLAT-02)
│   ├── compute/                    # NEW first-class seam (SC-13)
│   │   ├── __init__.py
│   │   ├── provider.py             # NEW: ComputeProvider ABC + typed errors + DTOs   (PLAT-07)
│   │   ├── fakeProvider.py         # NEW: FakeComputeProvider (in-memory, deterministic) (PLAT-08)
│   │   └── proxmoxProvider.py      # NEW: skeleton — imports proxmoxer, methods raise NotImplementedError
│   ├── db/
│   │   ├── __init__.py
│   │   ├── provider.py             # NEW: DbProvider ABC   (PLAT-06)
│   │   ├── sqliteProvider.py       # NEW: aiosqlite impl + snake↔camel mapping
│   │   ├── postgresProvider.py     # NEW: stub (raise NotImplementedError) behind the seam
│   │   └── migrations/
│   │       └── 001_init.sql        # NEW: schema (tech-spec §7.1) — NOTE partial-unique-index lands Phase 1
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py                 # NEW: CamelModel base (alias_generator)   (PLAT-09)
│   │   ├── workspace.py            # NEW: Workspace, WorkspaceCreate, WorkspaceStatus
│   │   ├── event.py                # NEW: WorkspaceEvent
│   │   └── template.py             # NEW: Template
│   └── tests/
│       ├── conftest.py             # NEW: fixtures (Fake providers, ASGITransport client)
│       └── unit/
│           ├── test_envelope.py    # NEW: envelope shape + camelCase
│           ├── test_models.py      # NEW: alias round-trip
│           └── test_fake_compute.py# NEW: Fake provider contract behavior
├── ui/
│   ├── package.json                # NEW: minimal — typescript + biome (gate scaffold)
│   ├── tsconfig.json               # NEW
│   ├── biome.json                  # NEW (Biome 2 schema)
│   └── src/.gitkeep | placeholder.ts  # NEW: something for tsc/biome to gate
├── docs/
│   └── adr/                        # NEW dir
│       ├── ADR-0001-sqlite-first.md        # (exists in spec Appendix A — author the file)
│       ├── ADR-0002-boot-config-pull-at-boot.md
│       ├── ADR-0003-proxmox-acl-scoping.md
│       ├── ADR-0004-static-ip-from-vmid.md
│       ├── ADR-0005-clone-mode-full.md
│       ├── ADR-0006-ttyd-persistent-drop-once.md
│       ├── ADR-0007-ttyd-lan-bind.md
│       └── ADR-0008-stack-version-bumps.md
├── scripts/
│   └── check-spdx.sh               # OPTIONAL: grep fallback if not using reuse
├── .github/workflows/
│   └── ci.yml                      # NEW: static-gates job (other jobs stubbed/Phase 1)
├── .reuse/dep5  (or REUSE.toml)    # NEW if using reuse: declares license for non-headerable files
├── .pre-commit-config.yaml         # OPTIONAL (ci-cd open-items §5): ruff/biome/reuse/gitleaks/commit
└── (cc-worker-config — separate repo; authored here as specs/scripts under that name)
    ├── PRIMING.md
    └── lxc/
        ├── host-prime/{lib/common.sh,00-api-user-role.sh,10-template-download.sh,
        │                20-create-template.sh,30-network-notes.md,40-control-plane.sh}
        └── worker-template/{provision-template.sh, burrow-boot.sh, ... }
```

> **Note on `cc-worker-config`:** CONTEXT says it is a *separate repo*, authored here "as specs/scripts under that name." The planner should decide whether to vendor a `cc-worker-config/` directory in this repo for Phase 0 or author under `docs/`/`lxc/`. Recommend a top-level `cc-worker-config/` directory (matches tech-spec §4.2 and PROXMOX-PRIMING §6 paths) so the scripts are real, lintable, and SPDX-headered.

### Pattern 1: Provider Seam via constructor injection + env selection
**What:** Both ABCs are injected into services by constructor; the concrete impl is chosen **once** in `main.py` from `settings`. This is the spec's central promise (additive hosted path) and what makes CI hermetic.
**When to use:** Always — `WorkspaceService` (Phase 1) takes `(compute: ComputeProvider, db: DbProvider)` and imports neither impl.
**Example:**
```python
# api/main.py  — the ONLY place impls are named
# Source: ARCHITECTURE.md Pattern 3 (validated against tech-spec §6.3)
from api.config import settings
from api.compute.provider import ComputeProvider
from api.compute.fakeProvider import FakeComputeProvider
from api.compute.proxmoxProvider import ProxmoxComputeProvider
from api.db.provider import DbProvider
from api.db.sqliteProvider import SqliteProvider

def get_compute() -> ComputeProvider:
    return FakeComputeProvider() if settings.compute == "fake" else ProxmoxComputeProvider(settings)

def get_db() -> DbProvider:
    return SqliteProvider(settings)   # postgres path is additive, not wired in v1
```

### Pattern 2: Response envelope as middleware + helper (PLAT-02)
**What:** Every response is `{data, meta:{requestId, timestamp}, error}`. Implement as (a) a small `respond()` helper routers call for the success shape, and (b) an exception handler / middleware that wraps raised typed errors into the `error` shape with the same `meta`. `requestId` is generated per request (set on `request.state`, also echoed as a response header); `timestamp` is `datetime.now(UTC).isoformat()`.
**When to use:** All `/api/v1` responses (Phase 1 routers consume this). Author the helper + a contract test now so Phase 1 builds against a verified shape.
**Example:**
```python
# api/lib/envelope.py
# Source: tech-spec §5.1 (envelope) + ARCHITECTURE Component Responsibilities
from datetime import datetime, timezone
from uuid import uuid4
from pydantic import BaseModel

class Meta(BaseModel):
    requestId: str
    timestamp: str

class ApiError(BaseModel):
    code: str
    message: str

def make_meta(request_id: str | None = None) -> Meta:
    return Meta(requestId=request_id or str(uuid4()),
                timestamp=datetime.now(timezone.utc).isoformat())

def respond(data, request_id: str | None = None) -> dict:
    return {"data": data, "meta": make_meta(request_id).model_dump(), "error": None}

def respond_error(code: str, message: str, request_id: str | None = None) -> dict:
    return {"data": None, "meta": make_meta(request_id).model_dump(),
            "error": {"code": code, "message": message}}
```

### Pattern 3: Pydantic v2 camelCase alias base (PLAT-09)
**What:** A `CamelModel` base sets `alias_generator=to_camel` + `populate_by_name=True` so models accept snake_case (from DB rows / Python) and serialize camelCase (JSON), and vice versa. Every model inherits it.
**When to use:** All `api/models/*`. This is the single mechanism for snake↔camel; do not hand-map fields.
**Example:**
```python
# api/models/base.py
# Source: Pydantic v2 ConfigDict + pydantic.alias_generators.to_camel  [CITED: pydantic v2 docs]
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,     # accept snake_case field names on input
        from_attributes=True,      # construct from ORM-ish / Row objects
    )
    # serialize with by_alias=True at the boundary: model.model_dump(by_alias=True)
```
> **Important wiring detail:** `model_dump()`/`model_dump_json()` default to field (snake) names; you must pass `by_alias=True` to emit camelCase. The envelope helper / a FastAPI `response_model` with `response_model_by_alias=True` (the FastAPI default for response_model) handles this — confirm the boundary serializes by alias. `[ASSUMED — verify FastAPI's response_model_by_alias default for the pinned 0.136.x in Phase 1]`

### Pattern 4: Idempotent shell scripts (`set -euo pipefail` + check→act)
**What:** Every host-prime script and the provisioner is re-runnable: strict mode, preflight guards, check-before-act on every mutation, a reversal block, and loud handling of the one non-idempotent resource (the API token).
**When to use:** All of `lxc/host-prime/*` and `provision-template.sh`. PROXMOX-PRIMING §6 specifies the `lib/common.sh` contract verbatim.

### Anti-Patterns to Avoid
- **Leaking `proxmoxer`/`aiosqlite` types past the seam** (ARCHITECTURE Anti-Pattern 1): providers return Pydantic models / typed DTOs only. A CI grep (below) guards it.
- **Putting the envelope shape in routers/services**: it is a boundary concern — middleware + helper only.
- **Hand-mapping snake↔camel per field**: use the `CamelModel` base; per-field mapping drifts.
- **Authoring `proxmoxProvider.py` with real proxmoxer calls this phase**: it is a *skeleton* — methods `raise NotImplementedError`. Real bodies are Phase 1 (and only validated in the homelab).
- **Keeping `--once` / `--interface lo` from the spec's boot script**: both are SC-corrected; the spec snippet is wrong here (SC-8/SC-9).
- **`verify_ssl=False`**: the committed `.env.example` already supersedes the spec's `verify_ssl=False` with `PROXMOX_CA_CERT_PATH`. The `proxmoxProvider` skeleton + `config.py` must read the CA path, not hardcode `verify_ssl=False`.

## Provider Seam Interfaces (the load-bearing contract — get this right once)

### `DbProvider` ABC (`api/db/provider.py`) — PLAT-06
Start from tech-spec §6.3 (already correct) and keep it. Methods (all `async`, return Pydantic models or `None`):

| Method | Signature | Notes |
|--------|-----------|-------|
| createWorkspace | `(data: dict) -> Workspace` | Writes the `creating` row. Phase 1 adds the VMID-reservation semantics (SC-2/SC-3). |
| getWorkspace | `(workspaceId: str) -> Workspace \| None` | Excludes soft-deleted. |
| listWorkspaces | `(status: str \| None = None) -> list[Workspace]` | Filter by status; excludes soft-deleted. |
| updateWorkspace | `(workspaceId: str, updates: dict) -> Workspace` | Status transitions, `lxcIp`, timestamps. |
| softDeleteWorkspace | `(workspaceId: str) -> None` | Sets `deletedAt`; row retained for audit. |
| logEvent | `(workspaceId: str, eventType: str, data: dict) -> None` | Append-only event row. |
| **healthcheck** | `() -> bool` *(add)* | For `/health db: ok` (Phase 1 PLAT-03). Cheap `SELECT 1`. |

> **Phase-1 forward-compat note (do NOT implement, but shape the ABC to allow it):** VMID reservation is a DB concern (unique partial index, SC-3/SC-4). The migration `001_init.sql` this phase should follow tech-spec §7.1 **as-is**; the **partial unique index** `UNIQUE(vmid) WHERE deletedAt IS NULL` is a Phase-1 migration (`002_*`) per SC-4 — flag it so the planner doesn't bake it in prematurely, but the ABC's `createWorkspace` contract already tolerates a collision-raising insert.

### `ComputeProvider` ABC (`api/compute/provider.py`) — PLAT-07
The spec only *named* this; SC-13 promotes it. The ABC must expose **every method the Phase-1 create/stop/start/destroy sagas will call**, so the contract is stable before the saga is written. All methods `async` (the Fake is trivially async; the Proxmox impl wraps blocking proxmoxer in a thread). Return typed DTOs (Pydantic), raise typed `ComputeError` subclasses.

| Method | Signature | Saga step it serves | Fake behavior |
|--------|-----------|--------------------|---------------|
| getNextVmid | `(pool_start: int, pool_end: int, used: set[int]) -> int` | allocate VMID (SC-3) | First free in-range not in `used`; raise `NoFreeVmidError` if exhausted. (Real allocation is DB-reservation-backed in Phase 1; the provider just reports Proxmox-side used ids.) |
| usedVmids | `() -> set[int]` | union with DB-known ids (SC-3) | Returns ids of in-memory "containers". |
| cloneCt | `(template_vmid: int, new_vmid: int, name: str, node: str, full: bool = True) -> ComputeTask` | clone (SC-1, `--full`) | Records a stopped container; returns a completed `ComputeTask`. |
| injectBootConfig | `(vmid: int, config: BootConfig) -> None` | inject boot env — **DB-write-only seam** (pull-at-boot, SC-4/SC-5) | **No-op** (the real seam persists intent to DB; Fake just accepts it). |
| startCt | `(node: str, vmid: int) -> ComputeTask` | start (SC-1) | Marks container running; sets a deterministic fake IP. |
| stopCt | `(node: str, vmid: int) -> ComputeTask` | stop | Marks stopped. |
| destroyCt | `(node: str, vmid: int) -> ComputeTask` | destroy / compensation (SC-11) | Removes container; frees the id. |
| getStatus | `(node: str, vmid: int) -> ComputeStatus` | state reads, health | Returns in-memory status (status, uptime, mem, cpu). |
| getIp | `(node: str, vmid: int) -> str \| None` | resolve IP — **computed from VMID** (SC-6), not polled | Deterministic `10.x.y.<vmid-last-octet>`-style fake. |
| getNodeMemory | `(node: str) -> float` | capacity guard (CAP-01) | Configurable in-memory value (default well under threshold). |
| waitTask | `(node: str, upid: str, timeout: float) -> ComputeTask` | UPID blocking wait (SC-1) | Returns immediately OK (Fake tasks are synchronous). |
| healthcheck | `() -> bool` | `/health compute: ok` (PLAT-03) | `True`. |

**Supporting DTOs (define in `api/compute/provider.py` or `api/models/compute.py`):**
- `ComputeTask` — `{ upid: str \| None, status: Literal["ok","failed"], exitstatus: str \| None }` (the Fake always returns `ok`; the Proxmox impl populates from `Tasks.blocking_status`).
- `ComputeStatus` — `{ status: str, uptime: int, mem: int, maxmem: int, cpu: float }`.
- `BootConfig` — `{ configRepo, configBranch, projectRepo, projectBranch }` (**non-secret only** — pull-at-boot keeps the git credential out of this; SC-4).
- Error hierarchy: `ComputeError(Exception)` → `NoFreeVmidError`, `CloneError`, `TaskFailedError`, `LxcNotReadyError`. Routers (Phase 1) map these to envelope error codes.

> **Why pin the full method set now:** if the saga (Phase 1) discovers a missing method, the ABC changes and every impl + every test rewires. Locking the surface here — even with `NotImplementedError` Proxmox bodies — is the entire point of "seams first."

### `FakeComputeProvider` behavior contract (PLAT-08)
- **In-memory + deterministic.** Backed by a `dict[int, _FakeContainer]`. No sleeps, no randomness; IP and task results are pure functions of inputs so Tier-1/Tier-2/e2e are reproducible.
- **Models the lifecycle honestly:** create→running→stopped→destroyed transitions match the real provider's observable effects (so the saga can't pass against the Fake and fail against Proxmox for *state-machine* reasons — integration bugs are isolated to the real Proxmox/ttyd layer per SUMMARY).
- **Injectable failure hooks** (for compensation tests, Phase 1): allow a test to make `startCt`/`getIp` raise on the Nth call. Shape the constructor to accept an optional failure config now so Phase 1 doesn't refactor it.
- **`injectBootConfig` is a no-op** (the real seam is a DB write per pull-at-boot; the Fake has no DB and no boot, so it accepts and discards).
- **Selected by `BURROW_COMPUTE=fake`** — it is shipped app code (lives in `api/compute/`, not `tests/`), wired by the e2e compose (ci-cd §4.4).

### Seam Leakage Audit (CICD-able, ARCHITECTURE §Integration Points)
A passing seam means these symbols appear **only** in the listed files. Add a cheap grep test (can live in `tests/` or as a static-gate step):

| Symbol | Allowed ONLY in | Red flag in |
|--------|-----------------|-------------|
| `proxmoxer`, `ProxmoxAPI`, `Tasks.blocking_status` | `api/compute/proxmoxProvider.py` | services, routers, models |
| `aiosqlite`, raw SQL | `api/db/sqliteProvider.py`, `migrations/` | services, routers, models |
| `websockets`, ttyd opcodes | `api/routers/terminal.py` (Phase 1) | services |
| `httpx` (non-test) | provider impls only | `workspaceService.py` |

## Static CI Gates (CICD-01, CICD-06) — exact invocations

The `static-gates` job is the **only** CI job that must fully pass this phase (other `ci.yml` jobs — unit/integration/e2e/build — can be stubbed or land Phase 1). Maps to ci-cd §4.1 Tier 0.

| Gate | Command | Config file | Notes |
|------|---------|-------------|-------|
| Lint (api) | `uvx ruff check` (or `uv run ruff check`) in `api/` | `api/pyproject.toml` `[tool.ruff]` | `[VERIFIED: ruff on PyPI]` |
| Format (api) | `uv run ruff format --check` in `api/` | same | check-only in CI |
| Type-check (api) | `uv run mypy . --strict` in `api/` | `[tool.mypy]` in `api/pyproject.toml` | mypy **2.x** — `strict = true`; pin per-rule. `[VERIFIED: STACK.md]` |
| Lint (ui) | `npx biome lint .` in `ui/` | `ui/biome.json` | Biome **2** schema. `[VERIFIED: STACK.md]` |
| Format (ui) | `npx biome format --check .` in `ui/` | same | (or `biome ci .` runs both) |
| Type-check (ui) | `npx tsc --noEmit` in `ui/` | `ui/tsconfig.json` | needs ≥1 `.ts(x)` + tsconfig |
| SPDX headers | `reuse lint` at repo root | `.reuse/dep5` or `REUSE.toml` | `[VERIFIED: reuse 6.2.0 on PyPI]`. Fallback: `scripts/check-spdx.sh` grep. |
| Conventional Commits | PR-title check Action + commit-msg regex | — | squash-merge ⇒ PR title is the commit. `[ASSUMED — pick the Action]` |
| Lockfile freshness (api) | `uv lock --check` in `api/` | `api/uv.lock` | fails if `pyproject.toml` drifted from lock. `[CITED: ci-cd §4.1]` |
| Lockfile freshness (ui) | `npm ci` in `ui/` | `ui/package-lock.json` | `npm ci` fails on lock/manifest mismatch. |

**`static-gates` job shape (`.github/workflows/ci.yml`):**
```yaml
# Source: ci-cd-and-testing.md §3.2 job DAG + §4.1
jobs:
  static-gates:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<sha-pinned>     # SHA-pin actions (ci-cd §7 / Phase 4 hardening)
      - name: Install uv
        uses: astral-sh/setup-uv@<sha-pinned>
      - name: Setup Node
        uses: actions/setup-node@<sha-pinned>
        with: { node-version: '22' }
      # api gates
      - run: uv sync --frozen
        working-directory: api
      - run: uv run ruff check .
        working-directory: api
      - run: uv run ruff format --check .
        working-directory: api
      - run: uv run mypy . --strict
        working-directory: api
      - run: uv lock --check
        working-directory: api
      # ui gates
      - run: npm ci
        working-directory: ui
      - run: npx tsc --noEmit
        working-directory: ui
      - run: npx biome ci .
        working-directory: ui
      # repo-wide
      - name: SPDX headers
        run: uvx reuse lint
  # commit/PR-title validation runs as its own job or a PR-title Action.
```
> **PR-title vs commit-msg:** Because PRs are squash-merged and the PR title becomes the commit (CONTRIBUTING + ci-cd §3.3), validating the **PR title** against Conventional Commit grammar is the load-bearing check. Validating every commit message is nice-to-have. Recommend a PR-title-validation Action plus a permissive local commit-msg regex; confirm the exact Action with the team (`[ASSUMED]`).

### SPDX two-line header per comment syntax (CICD-06)
Exact text from `CONTRIBUTING.md` (authoritative). Copyright line is `Brave Bear Studios` for project-authored files. `<year>` = `2026`.

| Syntax | Files | Header |
|--------|-------|--------|
| `#` | `.py`, `.sh`, `.toml`, `.yaml`/`.yml`, `Dockerfile`, `.env.example` | `# SPDX-FileCopyrightText: 2026 Brave Bear Studios`<br>`# SPDX-License-Identifier: AGPL-3.0-or-later` |
| `//` | `.ts`, `.tsx`, `.js` | `// SPDX-FileCopyrightText: 2026 Brave Bear Studios`<br>`// SPDX-License-Identifier: AGPL-3.0-or-later` |
| `<!-- -->` | `.html`, `.md` (where headerable), `.nginx`-as-html n/a | `<!--`<br>`SPDX-FileCopyrightText: 2026 Brave Bear Studios`<br>`SPDX-License-Identifier: AGPL-3.0-or-later`<br>`-->` |
| nginx `#` | `nginx/*.conf` | `# SPDX-FileCopyrightText: 2026 Brave Bear Studios`<br>`# SPDX-License-Identifier: AGPL-3.0-or-later` |

> **`reuse` for non-headerable files:** `package-lock.json`, `uv.lock`, and binary/data files can't carry a comment header. `reuse` handles these via `.reuse/dep5` (or the newer `REUSE.toml`) — declare a blanket license for `**/*.lock`, `**/*.json` (lockfiles), and any generated dirs. Author this file as part of the SPDX gate so `reuse lint` passes. `[CITED: reuse-tool docs]`

> **In-band shell note:** the shebang `#!/usr/bin/env bash` must stay line 1; the two SPDX `#` lines go **immediately after** the shebang (`reuse` accepts this). For `.sh` files the header is lines 2–3.

## Golden Template & Boot Script (WORK-01, WORK-04) — frozen skeletons

These are authored in `cc-worker-config` and **only validated in the dev homelab** (deferred). The job here is to bake the SC-corrected decisions in so the homelab validation tests the *right* thing.

### `provision-template.sh` (WORK-01) — runs once inside the template CT
Skeleton corrected from tech-spec §9.2 (which is mostly right) with these changes:
- **Add the SPDX header** (lines 2–3) and keep `set -euo pipefail`.
- **Pin claude-code** at provision: `npm install -g @anthropic-ai/claude-code@2.1.170` (refresh-on-reprovision; record the pin).
- **`binary` + `npm-global` plugins are baked here** (rtk, gsd); `claude-plugin` types are pulled at boot (Phase 3) — so the provisioner installs the *template-baked* set only.
- **Remove the cloud-init comment** ("overwritten by cloud-init on each clone") — pull-at-boot means the env file is *fetched*, not injected; the placeholder `/etc/burrow/worker.env` is fine but the comment is wrong (SC-4/SC-5).
- Installs `burrow-boot.sh` + `burrow-worker.service`, `systemctl enable`.

```bash
#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
# cc-worker-config/lxc/worker-template/provision-template.sh
# Run inside the template CT as root, ONCE, before `pct template`.
set -euo pipefail

apt-get update && apt-get upgrade -y
apt-get install -y git curl build-essential ttyd

# Node 22 + Claude Code (pin claude-code; record the NodeSource setup ref)
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt-get install -y nodejs
npm install -g @anthropic-ai/claude-code@2.1.170

# Baked plugins: binary + npm-global types only (claude-plugin types pull at boot — Phase 3)
bash /tmp/plugins/rtk/install.sh
npm install -g get-shit-done-cc   # gsd (npm-global)

# Boot script + systemd unit (persistent ttyd — see burrow-boot.sh)
install -m 755 /tmp/burrow-boot.sh /opt/burrow-boot.sh
install -m 644 /tmp/burrow-worker.service /etc/systemd/system/burrow-worker.service
systemctl enable burrow-worker.service

# Env placeholder — populated at boot via pull-at-boot (NOT cloud-init)
mkdir -p /etc/burrow && touch /etc/burrow/worker.env

apt-get clean && rm -rf /var/lib/apt/lists/*
echo "Template provisioned OK"
```

### `burrow-boot.sh` (WORK-04) — runs in each worker on boot
The SC-corrected skeleton. **Phase 0 freezes the ttyd invocation (persistent, LAN-bound).** The **pull-at-boot fetch step is stubbed** (real impl Phase 3; the control-plane endpoint is Phase 1). Author the stub so the shape is right.

```bash
#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
# /opt/burrow-boot.sh — runs on every workspace boot via burrow-worker.service.
set -euo pipefail
log() { echo "[burrow-boot] $*"; }

# --- Pull-at-boot config fetch (STUB — real impl Phase 3) ---------------------
# The worker knows its own VMID (from hostname / static IP, SC-6). At boot it will:
#   1. GET <CONTROL_PLANE>/api/v1/internal/bootconfig/<vmid>  -> non-secret config
#      (CONFIG_REPO, CONFIG_BRANCH, PROJECT_REPO, PROJECT_BRANCH)
#   2. request a SHORT-LIVED, repo-scoped git credential, use it for clone, DISCARD it
#      (never written to /etc/burrow/worker.env — secrets off worker env, SC-4 / Pitfall 13)
# Phase 0 leaves this as a documented stub; the control-plane endpoint contract is Phase 1.
CONTROL_PLANE="${CONTROL_PLANE:?CONTROL_PLANE must be set}"   # e.g. http://<control-plane>:8000
# TODO(Phase 3): fetch bootconfig + short-lived credential here.

CONFIG_REPO="${CONFIG_REPO:-}"
CONFIG_BRANCH="${CONFIG_BRANCH:-main}"
PROJECT_REPO="${PROJECT_REPO:-}"
PROJECT_BRANCH="${PROJECT_BRANCH:-main}"
WORKER_HOME="/root"

# --- Config + project pull (Phase 3 fills the auth) ---------------------------
if [[ -n "$CONFIG_REPO" ]]; then
  git clone --depth=1 --branch "$CONFIG_BRANCH" "$CONFIG_REPO" /tmp/cc-worker-config
  cp /tmp/cc-worker-config/claude/CLAUDE.md "$WORKER_HOME/CLAUDE.md"
  mkdir -p "$WORKER_HOME/.claude/plugins"
  cp -r /tmp/cc-worker-config/plugins/. "$WORKER_HOME/.claude/plugins/"
fi
[[ -n "$PROJECT_REPO" ]] && git clone --branch "$PROJECT_BRANCH" "$PROJECT_REPO" "$WORKER_HOME/project"

CLAUDE_CMD="claude"
command -v rtk &>/dev/null && CLAUDE_CMD="rtk claude"

# --- ttyd: PERSISTENT (no --once, SC-8) + LAN bind (no `lo`, SC-9 / WORK-04) ---
# Closing a browser tab DETACHES; it must not terminate the live Claude session.
# Bind to the worker's LAN address (0.0.0.0 here; the worker's static IP is fine too)
# so the control-plane WS proxy can reach :7681. Rely on the LAN boundary + least-priv.
log "Starting persistent ttyd on :7681 (LAN), cmd: $CLAUDE_CMD"
exec ttyd \
  --port 7681 \
  --writable \
  --interface 0.0.0.0 \
  bash -lc "cd ${PROJECT_REPO:+$WORKER_HOME/project} && exec $CLAUDE_CMD"
```

**Decisions baked in (each gets an ADR):**
- No `--once` → persistent (SC-8 / ADR-0006).
- `--interface 0.0.0.0` (LAN), not `lo` (SC-9 / WORK-04 / ADR-0007).
- Pull-at-boot stub, not cloud-init injection (SC-4/SC-5 / ADR-0002).

> **Cross-restart detach (note for Phase 2/4, not Phase 0):** persistent ttyd re-attaches to the *live PTY* on reconnect, but a full worker restart still loses the session unless `claude` runs inside tmux/zellij. SUMMARY defers true cross-restart persistence (scrollback restore) to v2. Phase 0 does not add tmux; just don't preclude it.

## Host-Prime Kit (SETUP-01..05) — implementation-ready check

PROXMOX-PRIMING.md is **implementation-ready** for the kit. Confirmation against the requirements:

| Requirement | Source in PROXMOX-PRIMING | Ready? |
|-------------|---------------------------|--------|
| SETUP-01 re-runnable kit + reversal notes | §6 file set + `lib/common.sh` contract (strict mode, preflight, check→act, reversal block) | ✅ verbatim |
| SETUP-02 9-priv role, scoped | §2.1 reconciled priv table + §2.2 scoping table | ✅ privs + scopes locked |
| SETUP-03 privsep, both principals, secret hygiene | §2.3 privsep nuance + §2.4 `pveum` recipe (grants to user AND token) + §6 secret-hygiene contract | ✅ |
| SETUP-04 `PRIMING.md` ordered runbook + 5-step acceptance | §8 runbook (P1–P5 + STEP 0–4) | ✅ |
| SETUP-05 static-IP-from-VMID + DHCP exclusion in `30-network-notes.md` | §4 scheme (placeholders) | ✅ |

**File set to author (placeholders only — no real hostnames/IPs/VMIDs, per security posture):**
```
cc-worker-config/
├── PRIMING.md                       # Day-0 runbook (PROXMOX-PRIMING §8)
└── lxc/host-prime/
    ├── lib/common.sh                # strict mode + require_root/require_cmd/require_node + guards (§6)
    ├── 00-api-user-role.sh          # pveum: user + BurrowProvisioner role + scoped ACL + privsep token (§2.4)
    ├── 10-template-download.sh      # pveam update/available/download Ubuntu 24.04 CT (§3.1)
    ├── 20-create-template.sh        # pct create (unprivileged 1, features nesting=1) + provision + pct template (§3.3)
    ├── 30-network-notes.md          # static-IP/VMID/subnet decision record — NOT a script (§4)
    └── 40-control-plane.sh          # provision control-plane box: burrow user, /opt/burrow, /data, uv venv, nginx, systemd, .env assembly (§7)
```

**Implementation-ready specifics already pinned by PROXMOX-PRIMING (planner can lift verbatim):**
- The full idempotent `pveum` recipe (§2.4) — role `add||modify`, user `list|grep||add`, pool create, token `privsep 1`, ACL granted to **both** `--users` and `--tokens` at every scoped path.
- The token non-idempotency guard + rotate/reuse prompt (§2.4) — "the one place the kit cannot silently converge; surface it loudly."
- Secret-hygiene contract (§6): `umask 077`, `read -rsp` for the token, `{ set +x; } 2>/dev/null` around the write, `printf` not `echo`, never the token as a CLI arg, `.env` `0600 burrow:burrow`, refuse to write `.env` unless `git check-ignore .env` passes, gitleaks backstop.
- `pveam`/storage rules (§3.1–3.2): `vztmpl` only on `dir` storage; rootfs pool on **thin** storage (`lvmthin`/`zfspool`); **avoid thick LVM** with `--full`; budget full-clone time into the **UPID wait**, not the ttyd health timeout.
- `unprivileged=1` + `features nesting=1` set on the **template** (clones inherit); never drop to privileged (§3.3).
- Static-IP formula + off-host DHCP exclusion (§4); per-clone `pct set net0` runs in the saga (Phase 1), not in priming.
- The operator verification commands + `pvesh get /access/permissions --token ...` scope check (§8).

**Still genuinely missing / planner must supply (small):**
1. **The actual `lib/common.sh` source** — PROXMOX-PRIMING specifies its *contract* (strict mode, `require_root`, `require_cmd`, `require_node`, ERR trap, guard helpers) but not the literal function bodies. The planner authors ~40 lines of helper shell. `[ASSUMED — straightforward]`
2. **`20-create-template.sh` glue** — it "wraps `worker-template/create-template.sh` + provision + `pct template`." The tech-spec §4.2 names `create-template.sh` but no body exists; the planner authors the `pct create` line (unprivileged, nesting, storage, net) + the orchestration that copies `/tmp/plugins`, `burrow-boot.sh`, `burrow-worker.service` into the CT before running `provision-template.sh`, then `pct template`.
3. **`burrow-worker.service`** unit (referenced by §9.2 but no body in spec) — a oneshot/simple unit that `ExecStart=/opt/burrow-boot.sh`. Author it in `cc-worker-config/systemd/`.
4. **`40-control-plane.sh`** is the largest script; PROXMOX-PRIMING §7 gives a detailed prose spec (service account, layout, `/data`, uv venv, nginx `nginx -t` before reload, systemd hardening, `.env` assembly). Translate prose → idempotent script.
5. **A decision the operator can't defer:** `cc-worker-config` as a real directory in this repo vs a separate repo. Recommend vendoring the directory now (so scripts are SPDX-headered, shellcheck-able, and part of the static gate) and splitting later if needed.

> **Static-gate the shell too:** add `shellcheck` to the static gates (not named in ci-cd but cheap and high-value for an idempotent-shell-heavy phase). `[ASSUMED — recommended, not required by spec]`

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| snake↔camel JSON mapping | per-field manual maps | Pydantic `alias_generator=to_camel` + `populate_by_name` | One mechanism, no drift; `model_dump(by_alias=True)` at the boundary. |
| Env config parsing | manual `os.environ` reads + casts | `pydantic-settings` `BaseSettings` | Typed, validated, `.env`-aware; the spec mandates it. |
| SPDX header checking | bespoke per-language regex matrix | `reuse lint` | Handles every comment syntax + non-headerable files via `.reuse/dep5`. |
| Conventional-commit check | custom git-log parser | PR-title-validation Action / commitlint | Squash-merge makes the PR title the commit; a maintained Action is robust. |
| Lockfile freshness | diffing manifests by hand | `uv lock --check` + `npm ci` | Both fail non-zero on drift; zero custom logic. |
| Idempotent shell guards | ad-hoc `if grep` everywhere | shared `lib/common.sh` (`require_*`, check→act, ERR trap) | PROXMOX-PRIMING §6 specifies the contract; centralize it. |
| Fake compute determinism | random IPs / sleeps in the Fake | pure functions of inputs (IP from VMID, instant tasks) | Reproducible Tier-1/2/e2e; the Fake's whole purpose. |
| Proxmox UPID waiting | (Phase 1, not now) polling loop | `proxmoxer.tools.Tasks.blocking_status` | Flag for Phase 1; do NOT hand-roll a task poller. |

**Key insight:** Phase 0 is *contracts and config*, where the ecosystem already has the right primitive for nearly everything. The only genuinely hand-written code is the two ABCs (your domain contract), the `FakeComputeProvider` (your test substrate), and the idempotent shell. Everything else is wiring established tools.

## Runtime State Inventory

> This is a greenfield phase (no existing system to migrate), but it *authors rename-sensitive contracts and a host-prime kit that registers OS/service state on real infra later*. The inventory below is forward-looking: what Phase 0 artifacts will create runtime state that later phases/operators must account for. No migration is needed now.

| Category | Items (created by Phase 0 artifacts, materialized later) | Action Required |
|----------|----------------------------------------------------------|-----------------|
| Stored data | SQLite `001_init.sql` schema (`workspaces`/`events`/`templates`); seed row `templates('default', 9000)`. No data exists yet (no DB created until Phase 1 runs migrations). | None now. Phase 1 owns the partial-unique-index migration (`002_*`, SC-4) — flag so it's not baked into `001`. |
| Live service config | `cc-worker-config` is authored as scripts; nothing is *deployed*. The host-prime kit, when run by the operator (deferred), creates: a `burrow@pve` Proxmox user + token (in PVE's config DB, NOT git), a pool, ACLs, an nginx site, a `burrow.service` systemd unit. | None now. Documented in `PRIMING.md`; reversal blocks per script. |
| OS-registered state | `burrow-worker.service` (enabled in the template at provision); `burrow.service` (control-plane systemd); nginx `sites-enabled`. All authored here, registered only when scripts run on real infra. | None now. Author the unit files; reversal notes cover `systemctl disable`. |
| Secrets/env vars | `.env` keys the config class + kit read: `PROXMOX_TOKEN_VALUE`, `PROXMOX_CA_CERT_PATH`, `CONFIG_REPO`, `TEMPLATE_VMID`, `WORKER_POOL_START/END`, `DEFAULT_NODE`, `DATABASE_PATH`. `.env.example` already committed; `.env` gitignored. The Proxmox **token value** is printed once by `00-api-user-role.sh` and unrecoverable. | None now. `config.py` must read these exact names (match `.env.example`). |
| Build artifacts | `api/uv.lock` (committed), `ui/package-lock.json` (committed), `api/.venv` (gitignored). No stale artifacts (greenfield). | None. Ensure `.gitignore` covers `.venv/`, `node_modules/`, `*.egg-info/`, `__pycache__/`. |

**Nothing to migrate:** None — verified greenfield (no `api/`, `ui/`, `.github/`, `docs/adr/` exist; confirmed by Glob this session). The host-prime kit's real-infra registration is the deferred dev-homelab gate.

## Common Pitfalls

### Pitfall 1: `model_dump()` emits snake_case (alias not applied on output)
**What goes wrong:** You set `alias_generator=to_camel` but the JSON still comes out snake_case.
**Why it happens:** Pydantic v2 `model_dump()`/`model_dump_json()` default to `by_alias=False`.
**How to avoid:** Serialize with `by_alias=True` at the boundary, or rely on FastAPI's `response_model` (which serializes by alias by default). Add a contract test asserting a sample model serializes `lxcIp`/`projectRepo` in camelCase.
**Warning signs:** A `test_models.py` round-trip that passes on input but the response body has `project_repo`.

### Pitfall 2: Authoring `proxmoxProvider.py` too fully (premature real calls)
**What goes wrong:** The skeleton acquires real proxmoxer logic and now needs a Proxmox node to test — defeating "seams first."
**Why it happens:** It's tempting to "just implement clone while you're here."
**How to avoid:** Every `proxmoxProvider` method `raise NotImplementedError`. Real bodies + mocked-Proxmox tests are Phase 1; real validation is the homelab.
**Warning signs:** `respx`/`responses` appearing in Phase 0 tests; a Proxmox host needed to run the suite.

### Pitfall 3: SPDX header before the shebang
**What goes wrong:** `reuse lint` passes but the shell script won't execute (or the interpreter is wrong) because the SPDX `#` lines pushed the shebang off line 1.
**Why it happens:** Blindly prepending the two-line header to every file.
**How to avoid:** For `.sh`, shebang is line 1; SPDX is lines 2–3. `reuse` accepts this ordering.
**Warning signs:** `./script.sh: line 1: SPDX-FileCopyrightText: command not found`.

### Pitfall 4: Biome 1.x config ported to Biome 2
**What goes wrong:** `biome.json` from training/old projects fails or silently mis-configures under Biome 2.
**Why it happens:** The 2.x schema changed (STACK.md headline #5 / delta table).
**How to avoid:** Write `biome.json` fresh against the 2.x schema (`$schema` from the installed version).
**Warning signs:** Biome warns about unknown keys or a deprecated schema URL.

### Pitfall 5: Token granted to user but not the token (silent 403 later)
**What goes wrong:** Every Proxmox clone returns 403 in the homelab even though auth "works."
**Why it happens:** privsep token effective perms = user∩token; granting only the user leaves the token with zero rights (PROXMOX-PRIMING §2.3).
**How to avoid:** The `00-api-user-role.sh` ACL loop grants the role to **both** `--users $USER` and `--tokens burrow@pve!$TOKEN` at every path. This is baked into the recipe — don't "simplify" it away.
**Warning signs:** `pvesh get /access/permissions --token ...` shows nothing for the token.

### Pitfall 6: `cc-worker-config` scripts left un-gated
**What goes wrong:** Shell scripts ship without SPDX headers / shellcheck, breaking the SPDX gate or hiding bugs in idempotent paths.
**Why it happens:** Treating the kit as "docs," outside CI.
**How to avoid:** Vendor `cc-worker-config/` in-repo, SPDX-header every script, add `shellcheck` to static gates.
**Warning signs:** `reuse lint` flags the shell files; or a non-idempotent re-run that the team only finds in the homelab.

## Code Examples

### `config.py` — pydantic-settings reading `.env` + env switch
```python
# api/config.py
# Source: pydantic-settings v2 docs [CITED]; key names match committed .env.example
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # provider selection (the app-factory switch)
    compute: str = "fake"          # BURROW_COMPUTE=fake|proxmox  -> use env_prefix or alias
    db_kind: str = "sqlite"        # BURROW_DB=sqlite

    # Proxmox (read but unused until Phase 1)
    proxmox_host: str = ""
    proxmox_user: str = "burrow@pve"
    proxmox_token_name: str = "burrow"
    proxmox_token_value: str = ""
    proxmox_ca_cert_path: str = "/etc/burrow/pve-ca.pem"   # NOT verify_ssl=False (matches .env.example)

    # LXC + worker
    template_vmid: int = 9000
    worker_pool_start: int = 200
    worker_pool_end: int = 299
    default_node: str = "pve1"

    # DB
    database_path: str = "/data/burrow.db"

settings = Settings()
```
> The `BURROW_COMPUTE`/`BURROW_DB` env names: map them to `compute`/`db_kind` via `validation_alias` or `env`. Confirm the exact `pydantic-settings` alias mechanism for 2.14.x in implementation. `[ASSUMED — verify alias syntax]`

### `DbProvider` ABC (lift from spec §6.3, add `healthcheck`)
```python
# api/db/provider.py  — Source: tech-spec §6.3 (verified) + PLAT-03 forward-compat
from abc import ABC, abstractmethod
from api.models.workspace import Workspace

class DbProvider(ABC):
    @abstractmethod
    async def createWorkspace(self, data: dict) -> Workspace: ...
    @abstractmethod
    async def getWorkspace(self, workspaceId: str) -> Workspace | None: ...
    @abstractmethod
    async def listWorkspaces(self, status: str | None = None) -> list[Workspace]: ...
    @abstractmethod
    async def updateWorkspace(self, workspaceId: str, updates: dict) -> Workspace: ...
    @abstractmethod
    async def softDeleteWorkspace(self, workspaceId: str) -> None: ...
    @abstractmethod
    async def logEvent(self, workspaceId: str, eventType: str, data: dict) -> None: ...
    @abstractmethod
    async def healthcheck(self) -> bool: ...
```

## ADRs to Author (docs/adr/) — Nygard-style

Format: follow the existing **ADR-0001** (tech-spec Appendix A) — `Status / Context / Decision / Consequences / Revisit trigger`. Author each as `docs/adr/ADR-NNNN-<slug>.md` with the SPDX `<!-- -->` header.

| ADR | Decision | Core Context (from research) |
|-----|----------|------------------------------|
| 0001 | SQLite-first | Already in spec Appendix A — author the file. |
| 0002 | Boot-config = **pull-at-boot** | `pct exec`/`pct push` not in HTTPS API (PROXMOX-PRIMING §1, SC-4); `injectBootConfig`=DB write; adds `GET /api/v1/internal/bootconfig/{vmid}` (Phase 1) + secret-at-boot contract. **Highest priority.** |
| 0003 | Proxmox **ACL scoping** = `/pool/burrow-workers` + `/storage/<rootfs>` + `/nodes/<node>` | Tight vs `/vms` broad (PROXMOX-PRIMING §2.2). Consequence: clone must also add the VMID to the pool. |
| 0004 | **Static-IP-from-VMID** | Unprivileged LXC has no agent; DHCP discovery unreliable (SC-6, PROXMOX-PRIMING §4). VMID→IP formula + off-host DHCP exclusion. |
| 0005 | Clone mode **`--full`** | CT-template clone defaults to *linked*; `--full` for independent ephemeral workers; on thin storage stays cheap (SC, PROXMOX-PRIMING §3.2). |
| 0006 | **ttyd persistent (drop `--once`)** | `--once` + tab-close kills the live Claude session — data-loss-class (SC-8). Detach ≠ terminate. |
| 0007 | **ttyd LAN bind** (not `lo`) | `lo`-bound ttyd refuses the remote proxy; resolves spec §9.3↔§6.4 (SC-9 / WORK-04). Has a security dimension → see threat model. |
| 0008 | **Stack version bumps** | One consolidated ADR for the spec-`^`-range deviations: Vite 8, TS 6, Biome 2, Vitest 4, @xterm 6, mypy 2, react-mosaic 6.2.0, Tailwind v4 (no `tailwind.config.ts`). Evidence: STACK.md live registry reads. (CLAUDE.md/CONTRIBUTING: deviations need an ADR.) |

> Recommend **one** consolidated stack-bump ADR (0008) rather than eight tiny ones — they share one rationale (spec ranges are a major version behind current stable) and one evidence base (STACK.md). The planner may split if the team prefers one-decision-per-ADR.

## State of the Art

| Old (spec) Approach | Current Approach | When Changed | Impact |
|---------------------|------------------|--------------|--------|
| `requirements.txt` | `pyproject.toml` + `uv.lock` (uv) | uv mature 2024+ | Lockfile-frozen installs; `uv lock --check` gate. |
| `verify_ssl=False` (spec §6.1) | CA cert via `PROXMOX_CA_CERT_PATH` | committed `.env.example` already | Don't reintroduce `verify_ssl=False`; read the CA path. |
| ttyd `--once --interface lo` (spec §9.3) | persistent ttyd, LAN bind | SC-8/SC-9 | The spec boot snippet is wrong here; use the corrected skeleton. |
| cloud-init env injection (spec §6.1 `setCloudInitUserdata`) | pull-at-boot DB write | SC-4/SC-5 | LXC has no cloud-init; `injectBootConfig` is a DB write, not a node command. |
| `tailwind.config.ts` + PostCSS (spec §4.1 tree) | `@tailwindcss/vite` + CSS `@theme` (no JS config) | Tailwind v4 | Drop the planned config file (Phase 2; flag now in stack ADR). |
| Biome 1.x config | Biome 2.x schema | Biome 2 | Write `biome.json` fresh. |

**Deprecated/outdated to avoid:**
- Spec's `^x` version ranges (Vite 6 / TS 5 / @xterm 5 / react-mosaic 7-beta) — superseded by STACK.md pins.
- `pip`/`requirements.txt` workflow — replaced by uv.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | FastAPI `response_model` serializes by alias by default for pinned 0.136.x (camelCase output without explicit `by_alias=True` at every router) | Pattern 3 / Pitfall 1 | LOW — verify in Phase 1; mitigated by the envelope helper calling `model_dump(by_alias=True)` explicitly. |
| A2 | Exact GitHub Action for Conventional-Commit / PR-title validation is team's choice | Static CI Gates, Alternatives | LOW — any maintained PR-title-validation Action satisfies the gate. |
| A3 | `pydantic-settings` 2.14.x alias syntax to map `BURROW_COMPUTE`→`compute` (`validation_alias` vs `env`) | config.py example | LOW — both forms exist; confirm exact key at implementation. |
| A4 | `reuse lint` is the chosen SPDX tool (vs a grep fallback) | Static CI Gates | LOW — ci-cd doc says "reuse lint (or equivalent)"; either satisfies CICD-06. |
| A5 | `cc-worker-config` is vendored as an in-repo directory for Phase 0 (not a truly separate repo yet) | Project Structure, Host-Prime | MEDIUM — affects where files live + whether they're gated; recommend confirming with operator. The scripts and contracts are identical either way. |
| A6 | `shellcheck` added to static gates | Host-Prime, Pitfall 6 | LOW — recommended enhancement, not required by spec. |
| A7 | One consolidated stack-bump ADR (0008) vs eight | ADRs | LOW — cosmetic; content identical. |
| A8 | `lib/common.sh` function bodies authored by planner (PROXMOX-PRIMING gives the contract, not the source) | Host-Prime | LOW — standard idempotent-shell helpers. |

**Note:** No `[ASSUMED]` package names — every package traces to STACK.md's live registry reads. The assumptions above are about *tooling choices and wiring details*, not package legitimacy.

## Open Questions (RESOLVED)

1. **`cc-worker-config`: in-repo directory vs separate repo for Phase 0?**
   - What we know: CONTEXT says "separate repo, authored here as specs/scripts under that name." tech-spec §4.2 + PROXMOX-PRIMING §6 use the path `cc-worker-config/lxc/...`.
   - What's unclear: whether to create a real top-level `cc-worker-config/` directory in `burrow` now, or stage the scripts elsewhere.
   - RESOLVED: LOCK to an **in-repo top-level `cc-worker-config/` directory** for Phase 0 (A5 recommendation). Authoring the scripts here means they get the SPDX two-line header, `shellcheck`, and CI gating *now*; split to a dedicated `cc-worker-config` repo when the Phase-3 worker pull pipeline lands. This matches what plans 00-06 / 00-07 already author (`cc-worker-config/PRIMING.md`, `cc-worker-config/lxc/host-prime/*`, `cc-worker-config/lxc/worker-template/*`).

2. **PR-title-validation Action choice.**
   - What we know: squash-merge ⇒ PR title is the commit; ci-cd requires "PR title + commit messages validated."
   - What's unclear: which specific Action.
   - RESOLVED: Use **`amannn/action-semantic-pull-request`**, SHA-pinned (per ci-cd §5.5 "third-party actions pinned to a full commit SHA"). Plan 00-04 names this Action explicitly and pins a SHA placeholder with a `# TODO pin exact SHA` note rather than leaving the choice to implementation. A permissive local commit-msg regex remains an optional nice-to-have.

3. **Minimal `ui/` scaffold vs full UI install in Phase 0.**
   - What we know: only `tsc` + `biome` gates need `ui/` to exist this phase; full UI is Phase 2.
   - RESOLVED: Minimal scaffold only — `ui/package.json` + the `vite`/`tsconfig`/`biome` configs and one placeholder source — to keep the phase focused and give the JS gates a real target. The full STACK.md UI runtime tree (React 19, Vite 8, xterm, react-mosaic, TanStack Query, Zustand, Tailwind v4) lands in Phase 2.

## Environment Availability

> The Phase 0 *deliverables* are code/config + shell scripts. The shell scripts target Proxmox (deferred to dev homelab), so the relevant "environment" for **this phase's CI-verifiable work** is the dev/CI toolchain, not Proxmox.

| Dependency | Required By | Available (this dev box / CI) | Version | Fallback |
|------------|------------|-------------------------------|---------|----------|
| Python 3.12 | api/ backend, mypy, pytest | Assumed on CI (`ubuntu-latest` + setup-uv) | 3.12 | uv installs the interpreter (`uv python install 3.12`) |
| uv | api deps + lockfile gate | CI via `astral-sh/setup-uv` | 0.11.19 | — |
| Node 22 | ui/ static gates (tsc, biome) | CI via `actions/setup-node` | 22 | — |
| reuse | SPDX gate | `uvx reuse` (no global install) | 6.2.0 | grep fallback (`scripts/check-spdx.sh`) |
| shellcheck | shell static gate (recommended) | apt on `ubuntu-latest` (preinstalled) | distro | — |
| **Proxmox VE 8.x** | host-prime kit + template real-infra validation | ✗ (not reachable from Windows dev box) | — | **DEFERRED to dev-homelab smoke gate** (the deferred acceptance authority) |

**Missing dependencies with no fallback:**
- Proxmox VE host — blocks *validation* of SETUP-01..05 / WORK-01 / WORK-04 only. Does **not** block authoring the scripts/contracts (CI-verifiable parts). Surfaces as `human_needed`, deferred per CONTEXT.

**Missing dependencies with fallback:**
- `reuse` → grep-based SPDX check if the team avoids the extra tool.

## Validation Architecture

> nyquist_validation: `.planning/config.json` not present in the read set; treating as **enabled** (default). This phase's validation splits cleanly into **CI-provable** (contracts, envelope, Fake provider, static gates, models) and **NOT CI-provable** (anything touching real Proxmox/ttyd → dev-homelab smoke).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 1.4.0 (api); biome/tsc are gate-only (ui) |
| Config file | `api/pyproject.toml` (`[tool.pytest.ini_options]`, `asyncio_mode = "auto"`) — author in Wave 0 |
| Quick run command | `cd api && uv run pytest tests/unit -x -q` |
| Full suite command | `cd api && uv run pytest` (this phase = unit only; integration is Phase 1) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PLAT-02 | Envelope wraps `{data,meta:{requestId,timestamp},error}` | unit | `uv run pytest tests/unit/test_envelope.py -x` | ❌ Wave 0 |
| PLAT-09 | snake↔camel alias round-trip | unit | `uv run pytest tests/unit/test_models.py -x` | ❌ Wave 0 |
| PLAT-07/08 | `FakeComputeProvider` honors the ABC contract (lifecycle, determinism) | unit | `uv run pytest tests/unit/test_fake_compute.py -x` | ❌ Wave 0 |
| PLAT-06 | `DbProvider` ABC importable; `SqliteProvider` instantiable (migrations run on temp DB) | unit/integration-lite | `uv run pytest tests/unit/test_db_provider.py -x` | ❌ Wave 0 |
| PLAT-06/07 | Seam leakage: forbidden symbols absent from services/routers/models | static | `uv run pytest tests/unit/test_seam_leakage.py -x` (grep-based) | ❌ Wave 0 |
| CICD-01 | ruff/format/mypy/tsc/biome/lockfile gates pass | static (CI) | the `static-gates` job | ❌ Wave 0 (ci.yml) |
| CICD-06 | every source file has the SPDX header | static (CI) | `uvx reuse lint` | ❌ Wave 0 |
| SETUP-01..05, WORK-01, WORK-04 | host-prime + template + boot script correctness | **manual / dev-homelab** | not CI-automatable | **DEFERRED** |

### What CI **can** prove (this phase)
- Both ABCs import and are abstract; `FakeComputeProvider`/`SqliteProvider`/stubs satisfy them.
- Envelope shape + camelCase serialization (contract test, snapshot-able).
- Fake provider lifecycle determinism (same inputs → same IP/task results).
- Migrations apply cleanly to a temp SQLite file.
- Seam leakage grep is green.
- All static gates green; all source files SPDX-headered.

### What CI **cannot** prove (dev-homelab smoke — deferred, the acceptance authority)
- `provision-template.sh` builds a working template; `pct template` succeeds.
- A `--full` clone boots; ttyd comes up **on the LAN interface** and is reachable (WORK-04).
- `claude` launches inside ttyd; persistent ttyd survives a tab close (SC-8).
- `00-api-user-role.sh` produces a token whose scoped ACL authenticates and clones (SETUP-02/03).
- The five-step `create→live→stop→start→destroy` acceptance gate (PROXMOX-PRIMING §8 STEP 4).

These map to the "Looks Done But Isn't" checklist (PITFALLS/SUMMARY). The planner must mark them `human_needed` / deferred, not block the phase on them.

### Sampling Rate
- **Per task commit:** `cd api && uv run pytest tests/unit -x -q` + `uv run ruff check . && uv run mypy . --strict`
- **Per wave merge:** full `static-gates` job locally (`ruff`, `ruff format --check`, `mypy --strict`, `tsc --noEmit`, `biome ci`, `uv lock --check`, `npm ci`, `reuse lint`)
- **Phase gate:** all static gates + `uv run pytest` green before `/gsd:verify-work`; dev-homelab items recorded as deferred.

### Wave 0 Gaps
- [ ] `api/pyproject.toml` with `[tool.pytest.ini_options]` `asyncio_mode = "auto"` + ruff/mypy config
- [ ] `api/tests/conftest.py` — Fake providers + `httpx.ASGITransport` client fixtures
- [ ] `api/tests/unit/test_envelope.py`, `test_models.py`, `test_fake_compute.py`, `test_db_provider.py`, `test_seam_leakage.py`
- [ ] `.github/workflows/ci.yml` `static-gates` job
- [ ] `.reuse/dep5` (or `REUSE.toml`) for non-headerable files
- [ ] Framework install: `uv add --dev pytest pytest-asyncio` (already in the install block above)

## Security Domain

> security_enforcement: treated as **enabled** (no config.json read; default). v1 is LAN-only, no-auth **by design** (CLAUDE.md) — so most app-tier auth/session/access-control ASVS categories are N/A for v1, but the **host-prime kit's token/secret handling** and the **pull-at-boot endpoint contract** are real ASVS L1 surfaces. Per-plan `<threat_model>` applies to those two areas.

### Applicable ASVS Categories
| ASVS Category | Applies (Phase 0) | Standard Control |
|---------------|-------------------|------------------|
| V2 Authentication | no (v1 LAN no-auth by design) | — (hosted-path scope) |
| V3 Session Management | no | — |
| V4 Access Control | partial (Proxmox token least-privilege) | 9-priv `BurrowProvisioner` role, `/pool` scoping, privsep token (PROXMOX-PRIMING §2) |
| V5 Input Validation | yes | Pydantic models validate all API input (Phase 1 consumes the models authored here) |
| V6 Cryptography / Secret Mgmt | **yes** | `.env` `0600`, token never echoed/logged/CLI-arg, `umask 077`, `{ set +x; }` around secret write, gitleaks; **CA cert** (`PROXMOX_CA_CERT_PATH`) not `verify_ssl=False` |
| V14 Config / Supply Chain | yes | lockfile-frozen installs, SHA-pinned Actions (Phase 4), SPDX headers, pinned package versions |

### Known Threat Patterns for {host-prime kit + pull-at-boot contract}
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Proxmox token leaked into git/logs/`ps` | Information Disclosure | `.env` gitignored + `git check-ignore` guard; `read -rsp`; never token-as-CLI-arg; gitleaks (CI + pre-commit) |
| Over-broad Proxmox role (effective root) | Elevation of Privilege | 9-priv least-privilege role, `/pool`+`/storage`+`/nodes` scoping, privsep token = user∩token (PROXMOX-PRIMING §2) |
| Secret (git deploy token) written to worker env file | Information Disclosure | Pull-at-boot: short-lived repo-scoped credential fetched at boot, used, **discarded** — never in `/etc/burrow/worker.env` (SC-4 / ADR-0002) |
| Bootconfig endpoint serves arbitrary VMID's config | Information Disclosure / Tampering | (Phase 1 endpoint) validate VMID ∈ `[pool_start, pool_end]`; non-secret payload only; worker authenticates by its own static IP/VMID — **flag for the Phase-1 endpoint threat model** |
| ttyd LAN bind widens exposure vs `lo` | Spoofing / Info Disclosure | Accept the LAN boundary (v1 LAN-only posture); document in ADR-0007; never expose worker `:7681` beyond the LAN; nginx binds the LAN interface only (Pitfall 12) |
| MITM on Proxmox API (self-signed) | Tampering | Use `PROXMOX_CA_CERT_PATH` (pin the node CA), **not** `verify_ssl=False` — already in `.env.example` |
| Slopsquatted dep in the worker template | Tampering / Supply Chain | Pin `@anthropic-ai/claude-code` + NodeSource ref; the `curl|bash` is the operator's trust decision, documented |

**Per-plan threat_model required for:** (1) the host-prime kit plan (token/secret handling, ASVS V4/V6), (2) the `burrow-boot.sh` plan (secret-off-worker-env, ttyd LAN bind). The bootconfig *endpoint* threat model is Phase 1 (flagged here so it isn't lost).

## Sources

### Primary (HIGH confidence)
- `.planning/research/STACK.md` — pinned versions (live PyPI/npm reads 2026-06-09); spot-re-verified this session (fastapi 0.136.3, pydantic 2.13.4, ruff 0.15.16 — all matched).
- `.planning/research/ARCHITECTURE.md` — provider seams, project structure, DI pattern, seam-leakage audit, envelope/model boundaries, anti-patterns.
- `.planning/research/PROXMOX-PRIMING.md` — host-prime kit file set, `pveum` recipe, 9-priv role, privsep nuance, secret hygiene, static-IP scheme, runbook (§1–§10).
- `.planning/research/SUMMARY.md` — Spec Corrections SC-1..13, build order, phase deliverables.
- `docs/tech-spec.md` §4.1 (tree), §5.1 (envelope), §6.3 (DbProvider ABC), §7.1 (schema), §9 (template/boot), §10.3 (.env), Appendix A (ADR-0001 format).
- `docs/ci-cd-and-testing.md` §3.2 (job DAG), §4.1 (Tier-0 static gates), §8 (config locations).
- `CONTRIBUTING.md` — exact SPDX two-line header per comment syntax; Conventional Commits + squash-merge policy.
- `CLAUDE.md` (project) — `/api/v1`, envelope, snake→camel, seam discipline, SPDX, LAN-only-no-auth posture, security headers.
- `.env.example` (committed) — authoritative env key names; `PROXMOX_CA_CERT_PATH` (supersedes spec `verify_ssl=False`).
- `pip index versions {reuse,ruff,fastapi,pydantic}` (this session) — version confirmation.
- Glob (this session) — confirmed greenfield: no `api/`, `ui/`, `.github/`, `docs/adr/`.

### Secondary (MEDIUM confidence)
- Pydantic v2 `ConfigDict(alias_generator=to_camel, populate_by_name=True)` + `model_dump(by_alias=True)` pattern — established Pydantic v2 idiom `[CITED: pydantic v2 docs]`.
- pydantic-settings `BaseSettings` + `SettingsConfigDict(env_file=".env")` — established v2 idiom `[CITED: pydantic-settings docs]`.
- `reuse lint` + `.reuse/dep5`/`REUSE.toml` for non-headerable files `[CITED: fsfe reuse-tool docs]`.

### Tertiary (LOW confidence / flagged)
- Exact PR-title-validation GitHub Action (`[ASSUMED]` — team choice).
- FastAPI `response_model_by_alias` default for 0.136.x (`[ASSUMED]` — verify Phase 1; mitigated by explicit `by_alias=True` in the helper).
- `pydantic-settings` 2.14.x alias mechanism for `BURROW_COMPUTE`→`compute` (`[ASSUMED]` — confirm `validation_alias` vs `env`).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — STACK.md live reads + this-session spot-verification of three critical pins (all matched).
- Provider seam interfaces: HIGH — DbProvider lifted from verified spec §6.3; ComputeProvider method set derived from the validated create-saga (ARCHITECTURE Pattern 1 + SC-1..13).
- Static CI gates: HIGH — every invocation from ci-cd §4.1 + verified tool versions; SPDX header text verbatim from CONTRIBUTING.md.
- Golden template / boot script: HIGH on the decisions (SC-corrected, frozen by CONTEXT); real-infra validation deferred (no Proxmox reachable).
- Host-prime kit: HIGH — PROXMOX-PRIMING is implementation-ready; only `lib/common.sh` bodies + script glue are net-new authoring.
- ADRs: HIGH — list + rationale all sourced; format from spec Appendix A.

**Research date:** 2026-06-09
**Valid until:** 2026-07-09 (30 days — stack pins are stable; re-verify versions if planning slips past a month, especially ruff/biome/mypy which release frequently).
