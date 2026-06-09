# Phase 0: Contracts, Seams & Golden Template - Context

**Gathered:** 2026-06-09
**Status:** Ready for planning
**Mode:** Auto (autonomous) — grey areas were pre-decided in PROJECT.md / STATE.md / research and the user signed off (esp. pull-at-boot). No new grey-area prompts.

<domain>
## Phase Boundary

Phase 0 lands the **contracts, the hermetic test substrate, and the frozen golden-template + host-priming decisions** — everything later phases build on, with zero dependence on a real Proxmox node. In scope: Pydantic models + the `data`/`meta`/`error` response envelope; the `DbProvider` ABC + SQLite impl + Postgres stub; a first-class `api/compute/` `ComputeProvider` ABC + `FakeComputeProvider` (+ a `ProxmoxComputeProvider` skeleton); the FastAPI app factory wiring providers by env; static CI gates (ruff/biome/mypy/tsc/SPDX/conventional-commits/lockfile) + SPDX headers; and the `cc-worker-config` artifacts that must freeze here — `provision-template.sh`, `burrow-boot.sh` (persistent ttyd, LAN-bound), and the `lxc/host-prime/` Day-0 kit + `PRIMING.md`. Out of scope: the create saga and real Proxmox calls (Phase 1), the WS proxy + UI (Phase 2), the worker pull pipeline runtime (Phase 3).

Requirements owned: SETUP-01..05, PLAT-02, PLAT-06, PLAT-07, PLAT-08, PLAT-09, WORK-01, WORK-04, CICD-01, CICD-06.
</domain>

<decisions>
## Implementation Decisions

### Provider seams & contracts
- `ComputeProvider` is a **first-class `api/compute/` package** (ABC + `fakeProvider.py` + a `proxmoxProvider.py` skeleton), mirroring `api/db/` — the spec only named the seam; promote it (SC-13).
- `DbProvider` ABC in `api/db/` with `sqliteProvider.py` (`aiosqlite`) and a `postgresProvider.py` stub (ADR-0001). No SQLite/Proxmox specifics leak past the interfaces.
- App factory wires providers by env: `BURROW_COMPUTE=fake|proxmox`, `BURROW_DB=sqlite` — swapping an impl is a one-line/env change, never a service edit. Config via `pydantic-settings`.
- Response envelope helper produces `{data, meta:{requestId, timestamp}, error}`; Pydantic v2 models map snake_case DB columns → camelCase JSON (alias generator).
- `FakeComputeProvider` is in-memory and deterministic so the integration + e2e tiers (Phase 1+) run with zero Proxmox.

### Golden template & boot script (frozen here)
- ttyd is **persistent — drop `--once`** (SC-8): closing a tab must not kill the Claude session (detach ≠ terminate; destroy is the only kill path).
- ttyd binds the **worker LAN interface, not `lo`** (SC-9), so the control-plane proxy can reach it (resolves spec §9.3 ↔ §6.4).
- Clone mode: **`--full`** (ephemeral workers; avoids linked-clone base coupling).
- Template: Ubuntu 24.04 + Node 22 + `@anthropic-ai/claude-code` + ttyd, provisioned reproducibly; CT template downloaded to a `vztmpl` (`dir`) storage and `pct template`-converted on a thin rootfs storage so `--full` clones stay cheap. `unprivileged=1` + `features nesting=1`.

### Boot-config delivery (decision frozen, impl later)
- **Pull-at-boot** (user-approved recommendation): `pct exec`/`pct push` are NOT in the Proxmox HTTPS API, so the spec's push is impossible (SC-4). `injectBootConfig` becomes a DB write; the worker fetches non-secret config + a short-lived git credential from an internal control-plane endpoint at boot. Keeps the `ComputeProvider` seam HTTPS-only and secrets off worker env. Endpoint impl = Phase 1; `burrow-boot.sh` pull step = Phase 3. **ADR authored this phase.**

### Proxmox priming (host-prime kit)
- `burrow@pve` user + `BurrowProvisioner` role, minimal 9-priv set: `VM.Audit VM.Clone VM.Allocate VM.Config.Network VM.Config.Options VM.PowerMgmt Datastore.AllocateSpace Datastore.Audit Sys.Audit` (+ conditional `SDN.Use`).
- API token `privsep=1`; role granted to **both** user and token (effective = user∩token). Scope **recommended `/pool/burrow-workers` + `/storage/<rootfs>` + `/nodes/<node>`** (ADR: `/pool` tight vs `/vms` broad). Token value → gitignored `.env` only; never committed/logged/echoed.
- **Static IP from VMID** (SC-6); worker range excluded from DHCP; recorded in `30-network-notes.md` (placeholders only).
- Kit files: `lib/common.sh`, `00-api-user-role.sh`, `10-template-download.sh`, `20-create-template.sh`, `30-network-notes.md`, `40-control-plane.sh`, + top-level `PRIMING.md`. All idempotent (`set -euo pipefail`, check→act, reversal notes).

### CI gates, scaffolding & ADRs
- Static gates land here (ruff + biome lint/format, mypy strict, `tsc --noEmit`, SPDX header check, Conventional Commit validation, lockfile freshness). Full test pyramid = Phase 1. SPDX two-line header on every source file (CICD-06).
- Pin the researched current versions; the bumps over the spec's `^` ranges (Vite 8, TS 6, Biome 2, Vitest 4, `@xterm` 6, mypy 2, `react-mosaic-component` 6.2.0, Tailwind v4 via `@tailwindcss/vite` with no `tailwind.config.ts`) each get an ADR in `docs/adr/`.
- ADRs to author this phase: (1) boot-config = pull-at-boot, (2) Proxmox ACL scoping, (3) static-IP-from-VMID, (4) clone-mode `--full`, (5) ttyd persistent (drop `--once`), (6) ttyd LAN bind, plus the stack-version-bump ADR(s).

### Claude's Discretion
- Exact module/file layout within `api/` and `ui/` (follow tech-spec §4.1 + CLAUDE.md conventions), test scaffolding style, and the precise envelope helper signature are at Claude's discretion within the above constraints.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- Greenfield — no `api/` or `ui/` code exists yet. Authoritative sources: `docs/tech-spec.md` (§4.1 tree, §5 API, §6 backend, §7 data model, §9 template, §10 control plane), `docs/ci-cd-and-testing.md` (test tiers, gates, supply chain), and `.planning/research/` (STACK.md pinned versions; ARCHITECTURE.md seams + build order; PITFALLS.md; SUMMARY.md SC-1..13; PROXMOX-PRIMING.md Day-0 kit).
- `.env.example` exists at repo root (Proxmox + config-repo + LXC + DB vars) — the env contract the app factory + settings read.

### Established Patterns (from CLAUDE.md — non-negotiable)
- All routes under `/api/v1`; standard `data`/`meta`/`error` envelope; snake_case DB → camelCase JSON; provider seams abstract; structured JSON logging; security headers; SPDX header on every source file; Conventional Commits.

### Integration Points
- App factory (`api/main.py`) registers routers + middleware and injects providers via FastAPI DI. `cc-worker-config` is a **separate repo** (authored here as specs/scripts under that name) the workers pull from at boot.
</code_context>

<specifics>
## Specific Ideas

Implement the **Spec Corrections (SC-1..SC-13)**, not the spec's happy-path pseudocode. The `FakeComputeProvider` + protocol-accurate test seams are what make ~80% of the backend CI-verifiable here. The host-prime kit + template are authorable here but their true acceptance (a real CT cloning/booting, ttyd reachable, `/health` `compute: ok`) is a **dev-homelab smoke gate** — not provable in CI or on this Windows dev box.
</specifics>

<deferred>
## Deferred Ideas

- Real-infrastructure validation of WORK-01 / WORK-04 / SETUP-01..05 (template boots, host prime runs, ttyd reachable) → dev-homelab smoke gate. Will surface as `human_needed` and is **deferred** per the operator's full-autonomous choice (no Proxmox reachable from here).
- The pull-at-boot internal endpoint implementation → Phase 1. The `burrow-boot.sh` pull step → Phase 3.
</deferred>
