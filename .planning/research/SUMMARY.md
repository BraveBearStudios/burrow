<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Project Research Summary

**Project:** Burrow
**Domain:** Self-hosted browser control plane for ephemeral Claude Code worker LXCs (FastAPI control plane + Vite/React tiling terminal UI + Proxmox compute + ttyd/WebSocket terminal proxy)
**Researched:** 2026-06-09
**Confidence:** HIGH

> **How to read this file.** The stack is fixed by `docs/tech-spec.md` and the build is greenfield. Research did not redesign Burrow; it (1) pinned current-stable versions, (2) confirmed the component split and saga are sound, and (3) found that the spec's happy-path pseudocode is *literally broken* in several places against how Proxmox LXC and ttyd actually behave. Those are collected under **Spec Corrections** — the roadmap must implement the corrected behavior, not the spec's happy path. Each correction is research-backed (HIGH confidence unless noted) and tied to the phase that owns it.

## Executive Summary

Burrow is a single-operator, LAN-only orchestrator that clones a golden Proxmox LXC per workspace, boots Claude Code + ttyd inside it, and bridges that terminal to a tiling browser UI. Experts build this class of tool as a **modular monolith control plane** (one FastAPI process, no message bus) sitting behind two provider seams — `ComputeProvider` (Proxmox) and `DbProvider` (SQLite) — with a saga-based lifecycle engine and a WebSocket bridge between the browser and the worker's ttyd. The architecture in `docs/tech-spec.md` is correct at this level; the risk is entirely in the implementation details of the two external integrations (Proxmox and ttyd), which is exactly where the spec's pseudocode is wrong.

The recommended approach is **seams-and-fakes first**: build the Pydantic models, both provider ABCs, a `FakeComputeProvider`, the response envelope, and the app factory before any real Proxmox call exists. That makes ~80% of the backend testable in hermetic CI (real SQLite, mocked Proxmox HTTP, a protocol-accurate stub ttyd) and isolates the un-CI-able 20% (real Proxmox + the golden template) to the end, where it can only be validated in the dev homelab. Promote compute to a first-class `api/compute/` package (the spec only *names* the seam but instantiates Proxmox directly inside the service) so the Fake provider has a home and the e2e tier can run without a node. On the stack: use Vite 8 / TS 6 / Biome 2 / Vitest 4 / @xterm 6 / mypy 2 (the spec's `^` ranges are a major version behind reality), `react-mosaic-component@6.2.0` (stable, React-19-compatible — the spec's `^7` would pull a beta), and Tailwind v4 via `@tailwindcss/vite` with **no** `tailwind.config.ts` (the spec's v3 pattern). All deviations need an ADR per CLAUDE.md.

The key risks are concentrated and well-understood. **Proxmox mutations are async UPID tasks**, not synchronous calls — the spec races clone into start. **VMID allocation is a TOCTOU race** under two uvicorn workers that an in-process lock can't fix — it needs a DB unique reservation, and that reservation collides with soft-delete tombstones unless you use a partial unique index. **ttyd speaks a framed `tty` subprotocol**, not raw bytes — the spec's passthrough-with-`msg.encode()` bridge produces a dead terminal, and a bare-echo test stub *hides the bug until real infra*. **ttyd `--once` + closing a tab destroys the live Claude session** — a data-loss-class UX failure that contradicts the core value prop. **Failed creates orphan LXCs** and slowly exhaust the 100-id VMID pool without saga compensation plus a reaper. Mitigation is to bake UPID-waits, DB-first VMID reservation, the `tty` subprotocol, persistent ttyd, and per-step compensation into Phase 1 / the boot script, and to make the test stubs protocol-accurate so they don't paper over the integration bugs.

## Spec Corrections (implement these, not the spec's happy path)

Each item below contradicts `docs/tech-spec.md`; implementing the spec literally produces a broken, racy, or insecure system. These cross-cut Architecture + Pitfalls research and are the single most important input to the roadmap. Several need an ADR before their phase (CLAUDE.md: deviations from baseline need an ADR in `docs/adr/`).

| # | Spec says | Reality (confidence) | Correct implementation | Owning phase |
|---|-----------|----------------------|------------------------|--------------|
| SC-1 | `clone` then `start` then `getIp` treated as synchronous | Every mutation returns a UPID *task*; clone of a 30 GB rootfs is not instant (HIGH) | Block on each UPID inside the provider (`Tasks.blocking_status`, assert `exitstatus==OK`); raise typed `ComputeError` on non-OK | Phase 1 |
| SC-2 | DB `creating` row written *after* clone (step 5) | Crash between clone and row-write orphans a VMID with no record to find it by (HIGH) | Write `creating` row **+ persist VMID before** clone, so every later failure is reaper-recoverable | Phase 1 |
| SC-3 | `getNextVmId()` scans for first-free id | TOCTOU race; two uvicorn workers defeat an `asyncio.Lock` (HIGH) | DB `UNIQUE(vmid)` reservation INSERT-before-clone; treat collision as retryable; combine with static-IP-from-VMID | Phase 1 |
| SC-4 | Soft-delete keeps the row + its `vmid` | A `UNIQUE(vmid)` collides with the tombstone when the small pool recycles 207 (HIGH) | **Partial unique index** `UNIQUE(vmid) WHERE deleted_at IS NULL`; allocation reads live rows + Proxmox truth only, never tombstones | Phase 1 |
| SC-5 | `setCloudInitUserdata(...)` injects env via cloud-init | Proxmox LXC has **no** cloud-init (`cicustom` is QEMU/VM-only) (HIGH) | `ComputeProvider.injectBootConfig(vmid, env)` via `pct exec`/`pct push` to `/etc/burrow/worker.env`; **ADR** before Phase 1 | Phase 1 |
| SC-6 | `getLxcIp()` polls the interfaces API (DHCP) | Unprivileged LXC has no guest agent; interfaces endpoint flaky/empty for DHCP (HIGH) | **Static IP pool from VMID** (VMID 2xx then `10.a.b.2xx`) set at clone via `pct set net0`; IP known at allocation, no polling; **ADR** (resolves open question B1) | Phase 1 |
| SC-7 | Bridge raw bytes; `msg.encode()` on text frames | ttyd uses the `tty` subprotocol: `Sec-WebSocket-Protocol: tty`, first frame `{AuthToken,columns,rows}`, opcode-prefixed frames (`'0'` input, `'1'` resize JSON, server `'1'`/`'2'` title/prefs) (HIGH) | Negotiate `subprotocols=["tty"]` upstream; pass frames **opaquely**, preserve text-vs-binary; xterm adapter prefixes input `'0'` + sends `'1'`+JSON on resize | Phase 1 (proxy) + Phase 2 (xterm adapter) |
| SC-8 | `burrow-boot.sh` runs `ttyd --once` | `--once` exits ttyd on disconnect; ttyd is PID1 then a browser refresh **kills the live Claude session** (HIGH) | **Drop `--once`** (persistent ttyd; reconnect re-attaches to the live PTY). For true cross-restart detach, run `claude` inside tmux. Resolves open question B2; **decide before Phase 0 finalizes the template** | Phase 0 (boot) + Phase 2 (detach-vs-terminate UI) |
| SC-9 | ttyd `--interface lo` **and** proxy connects to `ws://{lxcIp}:7681` | The two halves contradict: `lo`-bound ttyd refuses the remote proxy; every create times out at the ttyd health poll then lands in `error` (HIGH) | Bind ttyd to the worker LAN interface (`0.0.0.0`/worker IP); rely on the LAN boundary. **ADR** (has a security dimension) | Phase 0 (boot) + Phase 1 (health poll + proxy target) |
| SC-10 | Bare `asyncio.gather(clientToTtyd, ttydToClient)` | One side closing does not cancel the other then half-open hang, leaked upstream ttyd connection (HIGH) | `asyncio.wait(FIRST_COMPLETED)` + cancel the sibling task; add WS ping/pong keepalive on both legs | Phase 1 |
| SC-11 | No compensation; "raise and bail" on boot failure | Half-built LXC keeps running; the 100-id pool fills with orphans (HIGH) | Per-step **saga compensation** (stop+destroy on any post-clone failure, row then `error` not `creating`) + a periodic **reaper** as the crash safety net | Phase 1 (compensation) + Phase 4 (reaper) |
| SC-12 | State machine draws only happy edges | Stop-during-`creating`, double-destroy, Start-on-`destroyed`, undefined `error` exit (HIGH) | Server-side **transition table** rejecting illegal moves with an envelope error; per-workspace in-flight lock; define `error`'s exit (retry vs destroy-only) | Phase 1 (server) + Phase 2 (UI gating) |
| SC-13 | `ComputeProvider` named but Proxmox instantiated inside `WorkspaceService` | Breaks the "compute is swappable" promise; the e2e Fake provider has no home (HIGH) | Promote to first-class `api/compute/` package: `provider.py` (ABC) + `proxmoxProvider.py` + `fakeProvider.py` | Phase 0 (seams) |

Two structural choices worth noting alongside the corrections: **full clone vs linked clone** — CT-template clone defaults to *linked* (shares base disk); use `--full` for independent ephemeral workers so destroy frees space (MEDIUM, Phase 0/1); and **synchronous vs async create POST** — sync is fine for v1 single-operator (modal shows progress) but note the migration to `202 + poll` if boot times grow.

## Key Findings

### Recommended Stack

The stack is fixed by spec, so research pinned exact current-stable versions (verified live against npm/PyPI on 2026-06-09) and flagged where the spec's `^` ranges are now a major version behind. Recommend **maximum currency** — the plugin/test ecosystem has already moved, so staying current avoids a forced migration mid-build. See `STACK.md` for the full pin table and per-dep peer-compat proof. The deltas that need an ADR: Vite 8 (spec `^6`), TypeScript 6 (`^5`), Biome 2 (`^1`, config schema changed — write `biome.json` fresh), Vitest 4, @xterm 6 (+ addon-fit 0.11, web-links 0.12), mypy 2, `react-mosaic-component@6.2.0` (spec `^7` is a beta — use the stable), and dropping `tailwind.config.ts` for Tailwind v4's `@tailwindcss/vite` + CSS `@theme`.

**Core technologies:**
- **FastAPI 0.136.3 + uvicorn[standard] 0.49.0** (Python 3.12): HTTP + native WebSocket server — spec mandate; `[standard]` already bundles `websockets` for the upstream leg.
- **websockets 16.0** (`websockets.asyncio.client.connect`): the upstream WS *client* to ttyd — FastAPI has no WS client; do **not** add aiohttp/socket.io. ttyd is raw WebSocket with a `tty` subprotocol.
- **proxmoxer 2.3.0 + aiosqlite 0.22.1**: the two provider impls (behind the seams); `httpx 0.28.1` for ttyd health polls + ASGI test transport.
- **React 19.2.7 + Vite 8.0.16 + TS 6.0.3**: UI core; `@vitejs/plugin-react@6` pins Vite 8.
- **@xterm/xterm 6.0.0** (+ addon-fit, addon-web-links): terminal emulator — use scoped packages; legacy `xterm` is npm-deprecated. Hand-roll the WS in `useTerminal.ts`, don't use `addon-attach`.
- **react-mosaic-component 6.2.0**: tiling panels, React-19-compatible (`peer react >=16`); pin the stable, not `7.0.0-beta0`.
- **@tanstack/react-query 5.101.0 + zustand 5.0.14**: server-state (workspace polling) vs client-state (mosaic tree) — keep workspace status in Query, layout only in Zustand.
- **Worker:** Ubuntu 24.04 + Node 22 LTS + `@anthropic-ai/claude-code` (pin at provision) + ttyd (apt) — lives in the separate `cc-worker-config` repo.

### Expected Features

`FEATURES.md` traces every v1 feature to a spec capability; anything beyond is tagged out of scope to stop creep. The product class is the intersection of three things no single tool delivers: browser multi-session terminal UI, ephemeral backend lifecycle, and reproducible per-workspace tooling.

**Must have (table stakes):**
- **Create-from-git saga** with boot-progress states + capacity guard — the *primary critical path*; if create fails nothing else matters.
- **Live WebSocket terminal streaming** — the interactive Claude terminal *is* the product.
- **Workspace list with live status** (creating/running/stopped/error) — you can't manage what you can't see.
- **Stop/start/destroy + enforced state machine** — ephemeral lifecycle is half the value prop.
- **Tiling multi-panel terminals** (open/split/drag/resize) — the visible "multi-session" claim.
- **Auto-reconnect with overlay** — without it the terminal feels broken on every WiFi blip.
- **Response envelope + structured logging + health + security headers** — cross-cutting contract; absence breaks every consumer.

**Should have (differentiators):**
- **Reproducible workers** (CLAUDE.md + plugin manifest pulled fresh at boot from `cc-worker-config`) — the strongest moat; "plugin drift is impossible."
- **Capacity guard** (refuse create at node RAM > 80%) — cheap, prevents fleet-wide OOM.
- **Node selection** (manual pick at create) — multi-node placement; auto-balance deferred.
- **Auto-stop idle** and **restore-after-refresh** — both P2, both gated on the `--once` decision (SC-8).

**Defer (v2+ / hosted path):**
- Auth, multi-tenancy, Postgres-primary, cloud/container compute backend — the *entire* hosted path; the seams keep it additive.
- Full scrollback restore (needs tmux/zellij in the worker — ttyd has no replay buffer; v1 honestly reconnects to the live session and loses prior scrollback).
- Auto node selection / load balancing, built-in IDE/editor, terminal sharing/collaboration, persistent/snapshotted workspaces (contradicts "ephemeral by default"), native mobile app.

### Architecture Approach

A **modular monolith**: nginx (dumb LAN reverse proxy + static UI + WS upgrade with 3600s timeout) then one FastAPI process with thin routers / thick services then two provider seams to the only real external systems (Proxmox API, worker ttyd). `WorkspaceService` orchestrates four lifecycle **sagas** (create is the dangerous one) and imports *only* the abstractions — a CI-able grep audit keeps `proxmoxer`/`aiosqlite`/`websockets` from leaking past the seams. The load-bearing structural change vs spec: promote compute to a first-class `api/compute/` package so `FakeComputeProvider` (used by the *shipped* app under `BURROW_COMPUTE=fake` for e2e) has a home symmetric with `db/`.

**Major components:**
1. **nginx** — LAN entry, static UI, reverse-proxy `/api` + `/ws` (WS upgrade, long read timeout), security headers. Knows nothing about workspaces.
2. **routers/** (`workspaces.py` HTTP CRUD, `terminal.py` WS bridge, `health.py`) — envelope/validation + the WS pump only; never import a provider impl.
3. **WorkspaceService** — the create/stop/start/destroy sagas, state-machine enforcement, capacity guard, VMID allocation, compensation — over `ComputeProvider` + `DbProvider` abstractions only.
4. **ComputeProvider seam** (`provider.py` ABC, `proxmoxProvider.py`, `fakeProvider.py`) — compute contract incl. UPID waits, static-IP, `injectBootConfig`, capacity query.
5. **DbProvider seam** (`provider.py` ABC, `sqliteProvider.py`, `postgresProvider.py` stub) — persistence, soft-delete, `logEvent`.
6. **terminal.py to ttyd bridge** — the only place that knows the ttyd wire format; FIRST_COMPLETED+cancel teardown.

### Critical Pitfalls

`PITFALLS.md` enumerates 15; the top failures are also Spec Corrections above. Ranked by blast radius:

1. **Async Proxmox tasks treated as synchronous (SC-1)** — block on the UPID inside the provider so `WorkspaceService` can't race clone then start. *The* most common first-time-Proxmox failure.
2. **VMID race + soft-delete tombstone collision (SC-3/SC-4)** — DB unique *reservation* before clone (two uvicorn workers defeat an in-process lock) **plus** a partial unique index so a recycled VMID doesn't collide with the tombstone.
3. **ttyd `tty` subprotocol (SC-7)** — naive byte passthrough yields a dead/garbled terminal; **and make the Tier-2 stub ttyd protocol-accurate**, because a bare echo stub hides this until real infra.
4. **`--once` destroys live sessions (SC-8)** — drop `--once`; closing a tab must mean detach, never terminate. Data-loss-class.
5. **No saga compensation then orphan clones (SC-11)** — per-step compensation + a reaper, or the 100-id pool silently exhausts.
6. **WS half-open teardown + reconnect storms (SC-10)** — FIRST_COMPLETED+cancel + ping/pong keepalive; jittered frontend backoff that distinguishes "blip" (retry) from "workspace gone" (stop).
7. **xterm.js FitAddon/dispose leaks (Pitfall 15)** — fit only when visible/nonzero (debounced ResizeObserver), `terminal.dispose()` + `observer.disconnect()` on unmount, reconcile the persisted Mosaic tree against live workspaces.
8. **LAN-only is not security-out-of-scope (Pitfall 12)** — non-`*` CORS, security headers on every response, bind to LAN only, least-privilege `burrow@pve` token (not `root@pam`), never inject secrets into worker env or logs.

## Implications for Roadmap

The dependency graph dictates the order. The gating chain is: **golden template** gates the **create saga** gates **terminal streaming** gates **tiling + reconnect** gates **restore-after-refresh**; and orthogonally, **contracts + seams + Fake provider** gate everything testable. The seams-first insight is what makes the project's "control plane can't be booted from a dev workstation" constraint survivable — build and CI-green ~80% of the backend before a single real Proxmox call exists.

### Phase 0: Contracts, Seams, and Golden Template
**Rationale:** Two unblockers in one phase. (a) Models + both provider ABCs + `FakeComputeProvider` + envelope + app factory unblock *all* hermetic testing (SC-13). (b) The golden template + boot pipeline must exist before any workspace can boot, stream, or be validated on real infra — and the boot script decisions (SC-8 drop `--once`, SC-9 ttyd binding, full-vs-linked clone, `burrow@pve` role scoping) must be settled *here* before the template is finalized.
**Delivers:** `api/compute/` + `api/db/` ABCs, `FakeComputeProvider`, Pydantic models, response envelope, config, app factory; `provision-template.sh` + `burrow-boot.sh` in `cc-worker-config` with persistent ttyd bound to the LAN interface.
**Addresses:** Reproducible workers; the seam contract.
**Avoids:** SC-8, SC-9, SC-13; Proxmox least-privilege (Pitfall 14).
**Note:** The template half needs real Proxmox and can only be validated in the dev homelab.

### Phase 1: Control Plane API (saga, state machine, providers)
**Rationale:** The saga + state machine is the project's core risk; isolate and unit-test it over the Fake provider before HTTP shape or real Proxmox. This phase owns the largest cluster of Spec Corrections.
**Delivers:** `SqliteProvider` + migrations (incl. partial unique index), `WorkspaceService` (create/stop/start/destroy sagas with per-step compensation, state-machine table, capacity guard, DB-first VMID reservation), `ProxmoxComputeProvider` (UPID waits, static-IP-from-VMID, `injectBootConfig`), `/api/v1` routers + envelope + `/health`, security headers + non-`*` CORS.
**Uses:** FastAPI, proxmoxer, aiosqlite, httpx.
**Implements:** Compute + DB seams, the saga pattern.
**Avoids:** SC-1, SC-2, SC-3, SC-4, SC-5, SC-6, SC-10 (proxy teardown), SC-11 (compensation), SC-12; Pitfall 12 (headers/CORS/bind).
**Note:** `ProxmoxComputeProvider` is mocked in CI (respx/responses) and validated against real Proxmox only in dev.

### Phase 2: Terminal Proxy + React UI (streaming, tiling, reconnect)
**Rationale:** Backend `/api/v1` contract + envelope must exist for MSW mocking and e2e. Build a single working terminal before the mosaic. Restore-after-refresh is just reconnect triggered by page-load, so reconnect lands first.
**Delivers:** `terminal.py` WS bridge (`tty` subprotocol, FIRST_COMPLETED+cancel, keepalive), xterm adapter (input `'0'` prefix, `'1'`+JSON resize), `useTerminal` lifecycle (dispose + ResizeObserver cleanup), `WorkspaceList`, `TerminalPanel`, react-mosaic `layoutStore`, `NewWorkspaceModal` with boot-progress, auto-reconnect overlay with jittered backoff, poll-vs-WS cache reconciliation.
**Uses:** React 19, @xterm 6, react-mosaic 6.2.0, TanStack Query, Zustand, MSW, Playwright; honor `design/` tokens.
**Implements:** The browser-to-ttyd bridge + tiling UI.
**Avoids:** SC-7 (xterm adapter half), SC-10 (frontend backoff), SC-12 (UI gating), Pitfall 11 (poll/WS drift), Pitfall 15 (xterm leaks).

### Phase 3: Reproducible Workers (cc-worker-config integration)
**Rationale:** Boot-time plugin/CLAUDE.md pull is the strongest differentiator but depends on a working create-to-boot path (Phase 0/1) to exercise. Git-auth strategy is a security-sensitive subtask.
**Delivers:** Manifest-driven plugin/CLAUDE.md pull in `burrow-boot.sh`; scoped, scrubbed-after-use git credentials; ensure secrets never hit `/etc/burrow/worker.env` post-boot or event/log payloads.
**Addresses:** Reproducible workers; one-source plugin distribution.
**Avoids:** Pitfall 13 (secrets in env/logs).
**Note:** Resolve open question B4 (boot-time-latest vs snapshot-at-create) here.

### Phase 4: Hardening (reaper, auto-stop, restore, capacity tuning)
**Rationale:** These are the "compare desired vs actual" + long-tail correctness items that are only meaningful once the critical path runs on real infra. The reaper is not optional at any real usage.
**Delivers:** Orphan reaper (creating/error rows + Proxmox VMIDs with no row), auto-stop idle (reconciled with the SC-8 detach semantics), restore-after-refresh (live-session reconnect, no scrollback — the honest v1 behavior), event-log activity drawer, capacity-guard tuning, CI supply-chain hardening (SHA-pinned actions, least-privilege per-job permissions, cosign/SBOM/SLSA).
**Avoids:** SC-11 (reaper), Pitfall 12 (no public exposure), Pitfall 14 (CI tokens).

### Phase Ordering Rationale
- **Seams before consumers:** the Fake provider + stub ttyd let Phases 1–2 reach CI-green with zero Proxmox; this is the only way the "no dev-workstation infra" constraint is survivable.
- **Service before routers, backend before UI:** isolate the risky saga over the Fake provider first; the UI needs the `/api/v1` envelope to mock against.
- **Real Proxmox + template are deferred-but-also-Phase-0:** the *decisions* that shape the template (SC-8/SC-9, clone mode, role scoping) must be made early because they're baked into `burrow-boot.sh`, even though *validating* them needs the homelab and lands later.
- **Reconnect before restore; single terminal before mosaic:** restore reuses reconnect machinery; a panel is a container for a working `TerminalPanel`.

### Research Flags

Phases likely needing `/gsd:plan-phase --research-phase` during planning:
- **Phase 0 (template/boot):** Real-Proxmox-only mechanics — `pct exec`/`pct push` env injection (SC-5), static-IP `net0` config (SC-6), full-vs-linked clone semantics, `burrow@pve` role privileges. Verify against the actual Proxmox version/storage backend in the dev homelab.
- **Phase 1 (Proxmox provider):** UPID task-wait semantics (`Tasks.blocking_status` behavior on failure), `/cluster/nextid` + reservation interplay, and the static-IP edge cases — research-backed at HIGH but unverified against this specific cluster.
- **Phase 2 (ttyd bridge):** The `tty` subprotocol framing is HIGH-confidence from ttyd source, but the exact AuthToken/init handshake and resize frame format should be confirmed against the pinned ttyd version with a protocol-accurate stub before the xterm adapter is finalized.

Phases with standard patterns (skip research-phase):
- **Phase 3 (manifest pull) and the SQLite/migrations + envelope/router scaffolding in Phase 1** — well-documented, established patterns; the only novel risk (secret hygiene) is already specified.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Every version read live from npm/PyPI on 2026-06-09; peer-compat verified. Only open choice is the deliberate spec-deviation pins (need ADRs), not unknowns. |
| Features | HIGH | Every v1 feature anchored to tech-spec/PROJECT.md; ecosystem framing (Gitpod/ttyd) is MEDIUM but only used for positioning, not scope. |
| Architecture | HIGH | Validated against spec + current Proxmox/proxmoxer/ttyd/FastAPI sources; the SPEC GAPS are corroborated by official docs. The `compute/` package promotion is an opinion, not a risk. |
| Pitfalls | HIGH | Proxmox UPID/VMID semantics, ttyd protocol, WS bridge, xterm lifecycle all verified against official docs/source. MEDIUM only on a few cloud-init/cleanup specifics that depend on the Proxmox version + storage backend. |

**Overall confidence:** HIGH

### Gaps to Address

- **Real-infra-only validation (Proxmox + template).** The template, `pct`-based env injection, static-IP config, clone mode, UPID timing, and ttyd reachability cannot be CI-verified — they must be exercised in the dev homelab during Phases 0/1. The "Looks Done But Isn't" checklist in `PITFALLS.md` is the acceptance gate; verify against *real* Proxmox and *real* ttyd, never the mocks/stubs.
- **Open questions still to decide at roadmap/phase time** (each with the research recommendation):
  - **LXC IP (B1):** static pool from VMID. *Recommended — decided by SC-6; needs ADR (Phase 1).*
  - **ttyd `--once` / detach (B2):** drop `--once`, persistent ttyd. *Recommended — decided by SC-8; resolve before Phase 0 (Phase 2 UI).*
  - **Node selection (B3):** manual pick in v1, auto-balance deferred. *Recommended (Phase 2).*
  - **Plugin cadence (B4):** boot-time-latest vs snapshot-at-create. *Open — decide in Phase 3.*
  - **`burrow-api` base image:** `python:3.12-slim` first (spec), distroless later. *Recommended (CI phase).*
  - **Release automation, coverage ratchet, vuln-waiver format, harden-runner egress.** *CI-phase decisions; start ~80% coverage, adopt harden-runner post-MVP.*
  - **Full clone vs linked clone:** use `--full` for ephemeral workers. *Recommended (MEDIUM — confirm against storage backend, Phase 0/1).*
  - **Sync vs async create POST:** sync for v1, note the `202+poll` migration path. *Recommended (Phase 1).*

## Sources

### Primary (HIGH confidence)
- `docs/tech-spec.md` (§3 architecture, §5 API + state machine, §6 backend, §7 data model, §9 template/boot, §10 control plane, Appendix B) and `docs/ci-cd-and-testing.md` (§4.3–4.5 test tiers + Fake/stub seams, §5 supply chain) — authoritative internal spec.
- `.planning/PROJECT.md` — constraints, security posture, provider-seam decisions, open questions.
- npm registry + PyPI JSON API (2026-06-09) — all version pins and peer-compat (see `STACK.md` source list).
- proxmoxer Tasks tools (`Tasks.blocking_status`, `exitstatus==OK`) and basic usage docs; Proxmox `pct(1)` (clone `--full`, linked-clone default); Proxmox Cloud-Init Support wiki (QEMU-only, not LXC).
- ttyd `protocol.c` + terminal client (`tty` subprotocol, `{AuthToken}` first frame, opcode framing) and ttyd man page (`--once` semantics).
- FastAPI WebSockets reference (`iter_bytes`/`send_bytes`/`send_text`); FastAPI/Starlette discussions on `asyncio.gather` half-open teardown.
- xterm.js issues on FitAddon resize + ResizeObserver/dispose leaks.

### Secondary (MEDIUM confidence)
- Proxmox forum threads + Telmate provider issue #1453 — LXC DHCP IP not reliably exposed via interfaces API; `pct exec hostname -I` workaround.
- Gitpod workspace lifecycle (ephemeral create/stop/destroy + 30-min auto-stop as the expected baseline); tmux/zellij persistence guides (scrollback/replay-buffer constraint behind restore-after-refresh).
- Claude Code agent-teams / multi-agent orchestration docs — confirms the target problem space.

### Tertiary (LOW confidence)
- None load-bearing. The few MEDIUM cloud-init/cleanup specifics depend on the dev cluster's Proxmox version + storage backend and must be confirmed in-homelab during Phases 0/1.

---
*Research completed: 2026-06-09*
*Ready for roadmap: yes*
