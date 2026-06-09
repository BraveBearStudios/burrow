# Requirements: Burrow

**Defined:** 2026-06-09
**Core Value:** One operator can create, watch, and manage many concurrent Claude Code sessions from a browser, each in an ephemeral, reproducible container that is gone when destroyed.

> Requirements are grounded in `docs/tech-spec.md`, `docs/ci-cd-and-testing.md`, and
> `.planning/research/` (esp. SUMMARY.md "Spec Corrections" SC-1..SC-13). Where a
> requirement encodes corrected behavior that contradicts the spec's happy-path
> pseudocode, the relevant SC is cited — the corrected behavior is authoritative.

## User Stories

- As an operator, I open Burrow in my browser and see all my workspaces with live status, so I know what is running at a glance.
- As an operator, I create a workspace from a git repo and watch it boot into a live Claude Code terminal, so I can start work without touching the Proxmox host.
- As an operator, I tile several workspace terminals side by side and switch between them, so I can supervise multiple agent sessions at once.
- As an operator, I stop, start, and destroy workspaces, so idle sessions free hardware and finished ones leave no trace.
- As an operator, I trust that a failed create never leaves an orphaned container eating my VMID pool, so the system stays healthy unattended.

## v1 Requirements

Requirements for the initial self-host release. Each maps to a roadmap phase (Traceability below).

### Platform & API (PLAT)

- [ ] **PLAT-01**: All API routes are served under `/api/v1` (resolves spec §5.2 un-versioned examples)
- [ ] **PLAT-02**: Every API response uses the standard envelope (`data`/`meta`/`error`) with `requestId` + `timestamp` in `meta`
- [ ] **PLAT-03**: `GET /api/v1/health` reports overall status plus `db` and `compute` connectivity
- [ ] **PLAT-04**: Backend emits structured JSON logs
- [ ] **PLAT-05**: API responses carry security headers
- [ ] **PLAT-06**: Persistence goes through an abstract `DbProvider`; v1 ships the SQLite (`aiosqlite`) impl with no SQLite specifics leaking past the interface
- [ ] **PLAT-07**: Compute goes through an abstract `ComputeProvider` in a first-class `api/compute/` package; v1 ships the Proxmox impl with no Proxmox specifics leaking past the interface (SC-13)
- [ ] **PLAT-08**: A `FakeComputeProvider` lets the integration + e2e tiers run hermetically with no real Proxmox
- [ ] **PLAT-09**: snake_case DB columns map to camelCase JSON in Pydantic models

### Workspace Lifecycle (WS)

- [ ] **WS-01**: Operator can create a workspace from name, git repo, branch (default `main`), plugin set, and node
- [ ] **WS-02**: Create runs the full saga — persist `creating` row + reserved VMID *before* clone (SC-2) → clone golden template → inject boot config → start → await IP → await ttyd health → mark `running` — awaiting each Proxmox UPID task to completion (SC-1)
- [ ] **WS-03**: Create compensates on any failure (tear down partial clone, free the VMID, mark `error`), leaving no orphaned LXC (SC-9)
- [ ] **WS-04**: Operator can list workspaces, filterable by `status`
- [ ] **WS-05**: Operator can fetch a single workspace by id
- [ ] **WS-06**: Operator can stop a running workspace (LXC stopped, disk state preserved)
- [ ] **WS-07**: Operator can start a stopped workspace (awaits ttyd health)
- [ ] **WS-08**: Operator can destroy a workspace (stop + destroy LXC, soft-delete the row)
- [ ] **WS-09**: Workspace status follows the enforced state machine (creating→running|error; running→stopped|destroyed; stopped→running|destroyed)
- [ ] **WS-10**: VMID allocation is race-safe across uvicorn workers via a DB unique reservation using a partial unique index that excludes soft-deleted rows (SC-3)
- [ ] **WS-11**: Operator can read a workspace's event log (created/started/stopped/destroyed/terminal.connected/terminal.disconnected/boot.error)

### Terminal Proxy (TERM)

- [ ] **TERM-01**: A WebSocket endpoint bridges the browser terminal to the worker's ttyd, relaying frames in both directions
- [ ] **TERM-02**: The proxy negotiates ttyd's `tty` subprotocol and preserves its frame framing without corruption (SC-6; fixes spec §6.4 `msg.encode()`)
- [ ] **TERM-03**: The proxy logs connect/disconnect events and emits a typed error frame when ttyd is unreachable
- [ ] **TERM-04**: The proxy tears down cleanly when either side closes (FIRST_COMPLETED + cancel; no half-open leaks)
- [ ] **TERM-05**: The browser terminal renders via xterm.js and fits/reflows to its panel on resize
- [ ] **TERM-06**: The browser terminal auto-reconnects with backoff and shows a reconnecting overlay
- [ ] **TERM-07**: The terminal unmounts cleanly on panel close (WebSocket closed, xterm disposed)

### UI (UI)

- [ ] **UI-01**: A sidebar lists workspaces with live, polled status indicators
- [ ] **UI-02**: Terminals render in a tiling react-mosaic layout supporting open, split (H/V), drag, and resize
- [ ] **UI-03**: A New Workspace modal collects name/repo/branch/node and shows live boot-progress states
- [ ] **UI-04**: A status bar shows running/stopped counts, session uptime, and node capacity
- [ ] **UI-05**: After a browser refresh, the UI reconnects the terminal of a still-running workspace (live session; prior scrollback is not restored in v1)
- [ ] **UI-06**: A per-workspace activity drawer surfaces the event log

### Workers & Config Pipeline (WORK)

- [ ] **WORK-01**: A golden template LXC spec provisions all worker software reproducibly (Ubuntu 24.04, Node 22, `@anthropic-ai/claude-code`, ttyd, configured plugins)
- [ ] **WORK-02**: Each worker boots via `burrow-boot.sh`: pulls CLAUDE.md + plugin manifest from `cc-worker-config`, clones the project repo, launches ttyd shelling into Claude Code
- [ ] **WORK-03**: Boot config (config/project repo + branch) is injected via the `ComputeProvider` using `pct exec`/`pct push` to write `/etc/burrow/worker.env`, not QEMU cloud-init (SC-4)
- [ ] **WORK-04**: ttyd is reachable by the control-plane proxy over the worker's network address (not `lo`-only), resolving the spec §9.3↔§6.4 contradiction (SC-7)
- [ ] **WORK-05**: The worker plugin set is defined by a versioned manifest; `claude-plugin` types are pulled fresh at boot, `binary`/`npm-global` types are baked into the template

### Capacity & Hardening (CAP)

- [ ] **CAP-01**: Workspace creation is refused when the target node's memory exceeds the capacity threshold
- [ ] **CAP-02**: Idle workspaces (no active terminal connection beyond a configured window) are auto-stopped
- [ ] **CAP-03**: A reaper reconciles and destroys orphaned LXCs and frees leaked VMIDs (SC-9)
- [ ] **CAP-04**: Operator can select the worker node at create time

### CI/CD & Supply Chain (CICD)

- [ ] **CICD-01**: CI static gates run ruff + biome (lint/format), mypy (strict) + `tsc --noEmit`, SPDX header check, Conventional Commit validation, and lockfile freshness
- [ ] **CICD-02**: CI runs the test pyramid — unit → integration (real SQLite, mocked Proxmox, protocol-accurate stub ttyd) → e2e (FakeComputeProvider + Playwright) → container smoke
- [ ] **CICD-03**: Every bug fix lands a failing-first regression test in the appropriate tier
- [ ] **CICD-04**: CI builds both images (`burrow-api`, `burrow-ui`) multi-stage, digest-pinned, non-root, with HEALTHCHECKs; image scan fails on HIGH/CRITICAL
- [ ] **CICD-05**: The release path emits an SBOM (syft), a cosign keyless signature, and SLSA build provenance, and publishes to GHCR
- [ ] **CICD-06**: Every source file carries the SPDX two-line header

## v2 Requirements

Deferred to a future release. Tracked, not in the current roadmap.

### Compute & Workspaces

- **WSX-01**: Auto node selection (capacity-aware / round-robin) instead of manual pick
- **WSX-02**: Persistent / snapshotted workspaces that survive destroy
- **WSX-03**: Full terminal scrollback restore after refresh (requires tmux/zellij in the worker template)

### Release & Runner

- **RELX-01**: Release automation (release-please or semantic-release) opening release PRs and tagging
- **RELX-02**: Hardened-runner egress allowlist (`step-security/harden-runner`)

## Out of Scope

Explicitly excluded for v1. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Authentication / login | v1 is LAN-only single-user by design; auth is hosted-path scope (tech-spec §13) |
| Multi-tenancy / per-user rows / RLS | No second user in v1; additive on the provider seams later |
| Postgres as primary DB | SQLite is the v1 store (ADR-0001); Postgres impl is a stub behind `DbProvider` |
| Cloud / container compute backend | v1 targets Proxmox LXC only; the `ComputeProvider` seam exists but no other impl |
| Real Proxmox exercised in CI | CI is hermetic (FakeComputeProvider + mocks); real infra validated in the dev homelab |
| Native mobile app | Browser-first, responsive web only |
| Secrets manager | v1 uses a gitignored `.env`; secrets manager is hosted-path scope |
| In-browser IDE / file editor | Burrow is a session manager, not an IDE |
| Terminal sharing / multi-user collaboration | Single-operator tool; no shared sessions in v1 |

## Definition of Done

v1 is releasable when:

- All v1 requirements above are implemented and mapped to a completed phase.
- The full CI pipeline is green: static gates, unit, integration, e2e (FakeComputeProvider), container smoke, and the supply-chain gates (scan/SBOM/sign/provenance) on the release path.
- A real-infrastructure smoke test in the dev homelab confirms create → live terminal → stop → start → destroy against a real Proxmox node and golden template (the "looks done but isn't" gate — CI cannot prove this).
- Every source file carries the SPDX header; deviations from the baseline architecture (incl. the stack version bumps and SC-* corrections) are recorded as ADRs in `docs/adr/`.
- Affected docs (tech-spec, ci-cd, ADRs, README) are updated to match shipped reality.

## Traceability

Which phases cover which requirements. **Populated during roadmap creation.**

| Requirement | Phase | Status |
|-------------|-------|--------|
| PLAT-01 | Phase 1 | Pending |
| PLAT-02 | Phase 0 | Pending |
| PLAT-03 | Phase 1 | Pending |
| PLAT-04 | Phase 1 | Pending |
| PLAT-05 | Phase 1 | Pending |
| PLAT-06 | Phase 0 | Pending |
| PLAT-07 | Phase 0 | Pending |
| PLAT-08 | Phase 0 | Pending |
| PLAT-09 | Phase 0 | Pending |
| WS-01 | Phase 1 | Pending |
| WS-02 | Phase 1 | Pending |
| WS-03 | Phase 1 | Pending |
| WS-04 | Phase 1 | Pending |
| WS-05 | Phase 1 | Pending |
| WS-06 | Phase 1 | Pending |
| WS-07 | Phase 1 | Pending |
| WS-08 | Phase 1 | Pending |
| WS-09 | Phase 1 | Pending |
| WS-10 | Phase 1 | Pending |
| WS-11 | Phase 1 | Pending |
| TERM-01 | Phase 2 | Pending |
| TERM-02 | Phase 2 | Pending |
| TERM-03 | Phase 2 | Pending |
| TERM-04 | Phase 2 | Pending |
| TERM-05 | Phase 2 | Pending |
| TERM-06 | Phase 2 | Pending |
| TERM-07 | Phase 2 | Pending |
| UI-01 | Phase 2 | Pending |
| UI-02 | Phase 2 | Pending |
| UI-03 | Phase 2 | Pending |
| UI-04 | Phase 2 | Pending |
| UI-05 | Phase 2 | Pending |
| UI-06 | Phase 4 | Pending |
| WORK-01 | Phase 0 | Pending |
| WORK-02 | Phase 3 | Pending |
| WORK-03 | Phase 1 | Pending |
| WORK-04 | Phase 0 | Pending |
| WORK-05 | Phase 3 | Pending |
| CAP-01 | Phase 1 | Pending |
| CAP-02 | Phase 4 | Pending |
| CAP-03 | Phase 4 | Pending |
| CAP-04 | Phase 1 | Pending |
| CICD-01 | Phase 0 | Pending |
| CICD-02 | Phase 1 | Pending |
| CICD-03 | Phase 1 | Pending |
| CICD-04 | Phase 4 | Pending |
| CICD-05 | Phase 4 | Pending |
| CICD-06 | Phase 0 | Pending |

**Coverage:**
- v1 requirements: 48 total
- Mapped to phases: 48
- Unmapped: 0

---
*Requirements defined: 2026-06-09*
*Last updated: 2026-06-09 after roadmap creation (traceability populated)*
