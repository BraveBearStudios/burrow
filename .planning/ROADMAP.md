<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Roadmap: Burrow

## Overview

Burrow is built seams-first. Phase 0 lands the contracts, both provider
abstractions, the `FakeComputeProvider`, the response envelope, the app factory,
and the static CI gates — plus the golden-template and `burrow-boot.sh` decisions
(persistent ttyd bound to the LAN interface) that must freeze before any worker
can boot. That makes ~80% of the backend testable in hermetic CI before a single
real Proxmox call exists. Phase 1 builds the risky core — the create saga (UPID
waits, persist-before-clone, race-safe VMID reservation, per-step compensation),
the state machine, both real providers, the `/api/v1` envelope, `/health`,
structured logs and security headers — over the Fake provider first. Phase 2
bridges the browser to the worker's ttyd (the `tty` subprotocol bridge) and builds
the tiling React UI with reconnect and restore-after-refresh. Phase 3 makes workers
reproducible (manifest-driven plugin/CLAUDE.md pull, hardened boot). Phase 4
hardens the fleet (orphan reaper, auto-stop idle, capacity tuning, event drawer)
and lands the supply-chain release gates. The phases that touch real Proxmox
(0 template, 1 real-clone, 3 real worker boot) can only be fully verified against
the dev homelab — CI proves builds and inter-app behavior, never live infra.

## Phases

**Phase Numbering:**
- Integer phases (0, 1, 2): Planned milestone work
- Decimal phases (1.1, 1.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 0: Contracts, Seams & Golden Template** - Pydantic models, provider ABCs, FakeComputeProvider, envelope, app factory, static CI gates, the Proxmox host-prime kit + runbook, and the golden-template + boot-script decisions
- [ ] **Phase 1: Control Plane API** - The create saga, state machine, real SQLite + Proxmox providers, `/api/v1` envelope, `/health`, structured logs, security headers, test pyramid
- [ ] **Phase 2: Terminal Proxy + React UI** - ttyd-subprotocol WS bridge, xterm.js, react-mosaic tiling, reconnect overlay, sidebar, new-workspace modal, status bar, restore-after-refresh
- [ ] **Phase 3: Reproducible Workers** - Manifest-driven plugin/CLAUDE.md pull, hardened `burrow-boot.sh`, secret-safe boot config injection
- [ ] **Phase 4: Hardening & Release** - Orphan reaper, auto-stop idle, capacity tuning, event-log drawer, and the supply-chain release path (scan/SBOM/sign/provenance/GHCR)

## Phase Details

### Phase 0: Contracts, Seams & Golden Template
**Goal**: The seam contracts, hermetic test substrate, and golden-template decisions exist so every later phase can be built and CI-greened without real Proxmox, and so the worker template can be frozen.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: SETUP-01, SETUP-02, SETUP-03, SETUP-04, SETUP-05, PLAT-02, PLAT-06, PLAT-07, PLAT-08, PLAT-09, WORK-01, WORK-04, CICD-01, CICD-06
**Spec Corrections owned**: SC-13 (promote compute to first-class `api/compute/` package), SC-8 (drop ttyd `--once` — persistent ttyd, decide before the template freezes), SC-9 (bind ttyd to the worker LAN interface, not `lo`); full-vs-linked clone (use `--full`) and `burrow@pve` least-privilege role scoping (Pitfall 14) are decided here because they bake into the template and boot script. Also owns the Day-0 priming kit (`cc-worker-config/lxc/host-prime/` + `PRIMING.md`) and freezes the boot-config-injection decision (pull-at-boot recommended — `pct exec`/`pct push` are not in the HTTPS API).
**Success Criteria** (what must be TRUE):
  1. `DbProvider` and `ComputeProvider` ABCs exist in `api/db/` and `api/compute/`, and a `FakeComputeProvider` implements the compute contract in-memory so the integration and e2e tiers run with zero Proxmox.
  2. Pydantic models map snake_case DB columns to camelCase JSON, and a reusable response envelope produces `data`/`meta`/`error` with `requestId` + `timestamp` in `meta`.
  3. The app factory wires providers by env (`BURROW_COMPUTE=fake|proxmox`, `BURROW_DB=sqlite`) so swapping an impl is a one-line change, never a service edit.
  4. CI static gates run green: ruff + biome (lint/format), mypy strict + `tsc --noEmit`, SPDX two-line header check, Conventional Commit validation, and lockfile freshness — and every source file carries the SPDX header.
  5. `provision-template.sh` + `burrow-boot.sh` exist in `cc-worker-config` with a persistent ttyd (no `--once`) bound to the worker LAN interface; the template provisions Ubuntu 24.04 + Node 22 + `@anthropic-ai/claude-code` + ttyd reproducibly.
  6. A re-runnable `cc-worker-config/lxc/host-prime/` kit + `PRIMING.md` runbook prime a bare Proxmox host (least-privilege `burrow@pve` user + `BurrowProvisioner` role + privsep token scoped to the worker pool/storage/node, CT template downloaded and `pct template`-converted, control-plane box provisioned) such that the operator can reach `GET /api/v1/health` → `compute: ok` and clone the template by hand with `--full`.
**Plans**: 7 plans
- [x] 00-01-PLAN.md — Backend foundation: uv project, pydantic-settings config, response envelope (PLAT-02), camelCase models + compute DTOs (PLAT-09)
- [ ] 00-02-PLAN.md — Provider seams: ComputeProvider ABC + FakeComputeProvider + Proxmox skeleton (PLAT-07/08), DbProvider ABC + SqliteProvider + 001_init.sql + Postgres stub (PLAT-06)
- [ ] 00-03-PLAN.md — App factory DI by env + test substrate (conftest, envelope/models/fake-compute/db unit tests, seam-leakage guard)
- [ ] 00-04-PLAN.md — Static CI gates (CICD-01) + REUSE/SPDX (CICD-06) + minimal ui/ scaffold
- [x] 00-05-PLAN.md — Eight Nygard ADRs (pull-at-boot, ACL scoping, static-IP, --full, ttyd persistent, ttyd LAN bind/WORK-04, stack bumps)
- [ ] 00-06-PLAN.md — Proxmox host-prime kit + PRIMING.md runbook (SETUP-01..05)
- [ ] 00-07-PLAN.md — Golden-template provisioner + SC-corrected burrow-boot.sh + systemd unit (WORK-01, WORK-04)
**Infra note**: The template half (WORK-01), ttyd LAN reachability (WORK-04), and the host-prime kit (SETUP-01..05) can only be validated against real Proxmox + a real worker in the dev homelab — CI cannot prove them. Decisions are frozen here even though boot validation lands in Phase 1/3 dev smoke. **ADR candidates (decide in Phase 0):** (1) boot-config injection mechanism — pull-at-boot recommended vs SSH-push (`pct exec`/`pct push` are not in the HTTPS API); (2) Proxmox ACL scoping — `/pool/burrow-workers` (tight) vs `/vms` (simple, broad); (3) static-IP-from-VMID; (4) clone mode `--full`; plus SC-8 (`--once`) and SC-9 (ttyd binding).

### Phase 1: Control Plane API
**Goal**: The full workspace lifecycle — create/list/get/stop/start/destroy — runs as a saga over both real providers, with a server-enforced state machine, capacity guard, race-safe allocation, and the `/api/v1` contract, all CI-green over the Fake provider.
**Mode:** mvp
**Depends on**: Phase 0
**Requirements**: PLAT-01, PLAT-03, PLAT-04, PLAT-05, WS-01, WS-02, WS-03, WS-04, WS-05, WS-06, WS-07, WS-08, WS-09, WS-10, WS-11, WORK-03, CAP-01, CAP-04, CICD-02, CICD-03
**Spec Corrections owned**: SC-1 (block on each Proxmox UPID task), SC-2 (persist `creating` row + VMID before clone), SC-3 (DB unique-reservation VMID allocation before clone), SC-4 (partial unique index `WHERE deleted_at IS NULL`), SC-5 (`injectBootConfig` = pull-at-boot: DB write + worker fetches config from an internal control-plane endpoint at boot; NOT `pct exec`/`pct push` — absent from the HTTPS API — and NOT cloud-init; mechanism frozen by the Phase 0 ADR), SC-6 (static IP computed from VMID, no DHCP poll), SC-10 (proxy teardown — FIRST_COMPLETED + cancel + keepalive), SC-11 (per-step saga compensation), SC-12 (server-side transition table + per-workspace in-flight lock); Pitfall 12 (security headers, non-`*` CORS, LAN bind).
**Success Criteria** (what must be TRUE):
  1. Creating a workspace runs the full saga — persist `creating` row + reserved VMID before clone, clone (await UPID OK), inject boot config via `injectBootConfig`, start (await UPID OK), resolve the static IP, await ttyd health, mark `running` — and a forced post-clone failure leaves NO orphaned LXC, frees the VMID, and lands the row in `error` (never `creating`).
  2. Two concurrent creates never collide on a VMID: a DB unique reservation (partial index excluding soft-deleted rows) yields one success and one clean retryable error, and destroy-then-recreate reusing a VMID succeeds.
  3. The state machine rejects illegal transitions server-side with an envelope error (Stop-during-`creating`, Start-on-`destroyed`, double-destroy), and an in-flight lock blocks concurrent mutations on one workspace.
  4. Every route is served under `/api/v1` with the standard envelope; `GET /api/v1/health` reports overall status plus `db` and `compute` connectivity; responses carry security headers and non-`*` CORS; the backend emits structured JSON logs (no secrets in event/log payloads).
  5. Workspace creation is refused when the chosen node's RAM exceeds the capacity threshold; the operator can select the node at create time; and the per-workspace event log records created/started/stopped/destroyed/boot.error.
  6. The test pyramid runs in CI — unit (saga/state machine over the Fake provider) → integration (real SQLite, mocked Proxmox HTTP, protocol-accurate stub ttyd) → e2e (FakeComputeProvider) — and every bug fix lands a failing-first regression test in the right tier.
**Plans**: TBD
**Infra note**: `ProxmoxComputeProvider` (UPID waits, static-IP `net0` set, `injectBootConfig`, capacity query) is mocked in CI and validated against real Proxmox only in the dev homelab — the real-clone create path is a dev-only smoke gate. Needs ADRs for SC-5 (injection mechanism) and SC-6 (static-IP-from-VMID). Likely `--research-phase` during planning (UPID task-wait semantics, `/cluster/nextid` interplay, static-IP edge cases against the actual cluster).

### Phase 2: Terminal Proxy + React UI
**Goal**: The operator opens, tiles, and interacts with live Claude Code terminals in the browser, with auto-reconnect, and a still-running workspace's terminal reattaches after a page refresh.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: TERM-01, TERM-02, TERM-03, TERM-04, TERM-05, TERM-06, TERM-07, UI-01, UI-02, UI-03, UI-04, UI-05
**Spec Corrections owned**: SC-7 (xterm adapter half — input `'0'` prefix, `'1'`+JSON resize, preserve text-vs-binary), SC-10 (frontend jittered backoff, blip-vs-gone distinction), SC-12 (UI gates actions per state but treats the backend as the authority), SC-8 (detach-vs-terminate UX — close panel = detach, destroy is the only kill path); Pitfall 11 (poll/WS cache reconciliation), Pitfall 15 (xterm FitAddon timing + dispose/observer cleanup + Mosaic reconciliation).
**Success Criteria** (what must be TRUE):
  1. The WS bridge negotiates ttyd's `tty` subprotocol, relays frames opaquely in both directions preserving text-vs-binary, tears down cleanly when either side closes (no leaked upstream connection / FD growth), and emits a typed error frame when ttyd is unreachable.
  2. A terminal renders via xterm.js, the input/resize adapter drives a real `claude` TUI correctly (fits and reflows to its panel, not stuck at 80x24), and the panel unmounts cleanly (WS closed, terminal disposed, ResizeObserver disconnected).
  3. Terminals tile in a react-mosaic layout supporting open, split (H/V), drag, and resize; the sidebar lists workspaces with live polled status; a New Workspace modal collects name/repo/branch/node and shows live boot-progress; a status bar shows running/stopped counts, uptime, and node capacity.
  4. On a transient disconnect the terminal auto-reconnects with jittered backoff behind a visible reconnecting overlay, stops retrying (showing a terminal error) on `error`/`destroyed`, and never thunders the API across many panels.
  5. After a browser refresh, the UI reconnects to the same live `claude` session of a still-running workspace (no fresh process, no scrollback restore in v1), and the persisted Mosaic layout reconciles against the live workspace list.
**Plans**: TBD
**UI hint**: yes
**Infra note**: CI exercises the bridge against a protocol-accurate stub ttyd (not a bare echo) and the UI via MSW + Playwright over the Fake provider; the real `tty` handshake/resize framing is confirmed against the pinned ttyd version, with full terminal correctness validated against real ttyd in the dev homelab. Likely `--research-phase` to confirm the AuthToken/init handshake + resize frame format before the xterm adapter is finalized.

### Phase 3: Reproducible Workers
**Goal**: A booted worker pulls its CLAUDE.md and plugin set fresh from `cc-worker-config` so workspaces are reproducible and plugin drift is impossible, with no credentials left behind.
**Mode:** mvp
**Depends on**: Phase 1 (a working create-to-boot path to exercise)
**Requirements**: WORK-02, WORK-05
**Spec Corrections owned**: builds on SC-8/SC-9 (the frozen boot-script contract from Phase 0); resolves open question B4 (boot-time-latest vs snapshot-at-create plugin cadence); Pitfall 13 (secrets never persisted in `/etc/burrow/worker.env` post-boot or in event/log payloads).
**Success Criteria** (what must be TRUE):
  1. `burrow-boot.sh` fetches its boot config (project repo/branch + a short-lived git credential) from the control-plane internal endpoint (pull-at-boot, per the Phase 0 ADR), pulls the master CLAUDE.md and a versioned plugin manifest from `cc-worker-config`, clones the project repo, and launches ttyd shelling into Claude Code — with error trapping so a boot failure surfaces as a typed `boot.error`, not a silent hang.
  2. The plugin set is manifest-defined: `claude-plugin` types are pulled fresh at boot while `binary`/`npm-global` types are baked into the template, and two boots of the same manifest produce the same plugin set.
  3. Git credentials used for the clone are short-lived/scoped and scrubbed after use — no token remains in `/etc/burrow/worker.env` post-boot, and no repo URL or credential appears in event-log `data` or structured logs.
  4. The plugin-cadence decision (boot-time-latest vs snapshot-at-create) is resolved and recorded, so reproducibility semantics are explicit.
**Plans**: TBD
**Infra note**: True acceptance — a real worker booting and pulling its config — requires a real Proxmox node + the golden template, validated in the dev homelab smoke gate; CI can only lint/unit-test the boot script and manifest schema. Needs an ADR for the B4 cadence decision.

### Phase 4: Hardening & Release
**Goal**: The fleet stays healthy unattended — orphans are reaped, idle workspaces auto-stop, capacity holds under concurrency — and the release path produces signed, attested, scanned images in GHCR.
**Mode:** mvp
**Depends on**: Phase 2 (event drawer needs the UI; reaper/auto-stop need the real create path)
**Requirements**: CAP-02, CAP-03, UI-06, CICD-04, CICD-05
**Spec Corrections owned**: SC-11 (the periodic reaper as the crash safety net beyond per-step compensation); auto-stop is reconciled with the SC-8 detach semantics (idle = no active terminal beyond the window, the intentional lifecycle end — not an accidental socket drop); Pitfall 12 (confirm no public exposure), Pitfall 14 (least-privilege per-job CI permissions + SHA-pinned actions).
**Success Criteria** (what must be TRUE):
  1. A reaper reconciles desired vs actual — it destroys Proxmox LXCs with no owning row, frees leaked VMIDs, and marks timed-out `creating` rows `error` (destroying their CTs) — verified against an injected orphan.
  2. Idle workspaces (no active terminal connection beyond the configured window) are auto-stopped as a deliberate lifecycle end, consistent with the detach-not-terminate semantics.
  3. A per-workspace activity drawer surfaces the full event log in the UI, and the capacity guard is tuned so concurrent creates cannot both pass the check and overcommit the node.
  4. CI builds both images (`burrow-api`, `burrow-ui`) multi-stage, digest-pinned, non-root, with HEALTHCHECKs, and the image scan fails the build on HIGH/CRITICAL findings.
  5. The release path emits an SBOM (syft), a cosign keyless signature, and SLSA build provenance, and publishes to GHCR with least-privilege per-job permissions and SHA-pinned third-party actions.
**Plans**: TBD
**UI hint**: yes
**Infra note**: The reaper, auto-stop, and capacity-under-concurrency behaviors are only meaningful against real workspaces on real Proxmox — their true acceptance is the dev-homelab smoke gate (the "Looks Done But Isn't" checklist), not CI. The supply-chain gates (CICD-04/05) are fully CI-verifiable.

## Progress

**Execution Order:**
Phases execute in numeric order: 0 → 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 0. Contracts, Seams & Golden Template | 2/7 | In progress | - |
| 1. Control Plane API | 0/TBD | Not started | - |
| 2. Terminal Proxy + React UI | 0/TBD | Not started | - |
| 3. Reproducible Workers | 0/TBD | Not started | - |
| 4. Hardening & Release | 0/TBD | Not started | - |
