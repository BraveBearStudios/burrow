# Phase 1: Control Plane API - Context

**Gathered:** 2026-06-10
**Status:** Ready for planning
**Mode:** Auto (autonomous) — grey areas are pre-decided by the SC corrections, the Phase-0 ADRs, and the Phase-0 contracts. No new grey-area prompts.

<domain>
## Phase Boundary

Phase 1 builds the **full workspace lifecycle as a saga over both real providers**, on top of the Phase-0 seams. In scope: the FastAPI routers under `/api/v1` (workspaces CRUD + `/health`), the `WorkspaceService` create→stop→start→destroy saga with a server-enforced state machine, race-safe VMID allocation, capacity guard, node selection, the per-workspace event log, the **real `ProxmoxComputeProvider`** (filling the Phase-0 skeleton: UPID-blocking clone/start/stop/destroy, static-IP-from-VMID, capacity query — mocked in CI, real-infra deferred), the **pull-at-boot internal bootconfig endpoint** (WORK-03), structured JSON logging, security headers + non-`*` CORS, and the test pyramid (unit → integration over real SQLite + mocked Proxmox + stub ttyd → e2e over FakeComputeProvider). Out of scope: the WebSocket terminal proxy + UI (Phase 2), the worker pull-step implementation in `burrow-boot.sh` (Phase 3), the reaper/auto-stop/release (Phase 4).

Requirements owned: PLAT-01, PLAT-03, PLAT-04, PLAT-05, WS-01..11, WORK-03, CAP-01, CAP-04, CICD-02, CICD-03.
</domain>

<decisions>
## Implementation Decisions

### Create saga (SC-1, SC-2, SC-11)
- Order: (1) capacity guard; (2) **persist `creating` row + reserved VMID BEFORE clone** (SC-2, recoverability); (3) `cloneCt(full=True)` and **block on the UPID task** to OK (SC-1); (4) `injectBootConfig` = **DB write only** (pull-at-boot, ADR-0002) — no `pct`/cloud-init; (5) `startCt` (block on UPID); (6) resolve the **static IP from VMID** (SC-6, ADR-0004) — no DHCP poll; (7) await ttyd health (HTTP GET `:7681`, 60s timeout / 2s interval); (8) mark `running`.
- **Per-step compensation** (SC-11): any failure tears down the partial clone, frees the VMID reservation, and lands the row in `error` (never stuck `creating`). Saga is idempotent/recoverable.

### VMID allocation (SC-3, SC-4)
- Race-safe via a **DB unique reservation** using a **partial unique index `... WHERE deleted_at IS NULL`** in a `002_*.sql` migration (a plain UNIQUE would break destroy-then-recreate). `getNextVmid` is bounded to the worker pool range and backed by this reservation — `usedVmids`→`getNextVmid` is NOT race-safe on its own; the DB index is the arbiter.

### State machine (SC-12)
- Server-side **transition table** rejects illegal transitions with an envelope error (stop-during-creating, start-on-destroyed, double-destroy). A **per-workspace in-flight lock** blocks concurrent mutations on one workspace.

### API surface (PLAT-01/02/03)
- All routes under `/api/v1`; standard `data`/`meta`/`error` envelope (reuse the Phase-0 helper). `GET /api/v1/health` reports overall + `db` + `compute` connectivity (provider `healthcheck()`).
- Endpoints: `GET/POST /api/v1/workspaces`, `GET /api/v1/workspaces/{id}`, `POST .../{id}/stop|start`, `DELETE .../{id}`, `GET .../{id}/events`, `GET /api/v1/templates`, plus the internal bootconfig endpoint below.

### Pull-at-boot bootconfig endpoint (WORK-03, ADR-0002)
- `GET /api/v1/internal/bootconfig/{vmid}` returns the worker's **non-secret** config (config repo/branch, project repo/branch) + a **short-lived, repo-scoped git credential minted per-fetch and discarded**. Threat model: validate `vmid ∈ [pool_start, pool_end]`; non-secret payload only; the worker is identified by its static source IP (derived from VMID); never log the credential. The endpoint contract is built here; the `burrow-boot.sh` consumer pull-step is Phase 3.

### Security & observability (PLAT-04, PLAT-05)
- Structured JSON logging (no secrets/tokens/credentials in log or event payloads). Security headers middleware on all responses; CORS restricted to the LAN origin (non-`*`). LAN-only-no-auth posture preserved — no auth added.

### Capacity & node selection (CAP-01, CAP-04)
- Refuse create when `getNodeMemory(node) > 0.80` (CapacityError → envelope error). Operator selects the node at create time (manual; auto-select is Phase 4/v2).

### ProxmoxComputeProvider (real impl)
- Fill the Phase-0 skeleton with `proxmoxer` calls behind the ABC: clone/start/stop/destroy each **block on the Proxmox UPID** (`Tasks.blocking_status`, assert exitstatus OK), set `net0` static IP at clone, query node memory, CA-pinned TLS (`PROXMOX_CA_CERT_PATH`, never `verify_ssl=False`). No proxmoxer types leak past the ABC. Real-Proxmox acceptance is the dev-homelab smoke gate (deferred).

### Tests (CICD-02, CICD-03)
- Unit: saga + state machine + VMID reservation + capacity guard over the `FakeComputeProvider`. Integration: FastAPI via `httpx.ASGITransport` against **real SQLite** (exercises migrations + DbProvider) with the **Proxmox HTTP API mocked** (`respx`) and a **protocol-accurate stub ttyd**; cover the full CRUD, the create saga incl. compensation, the state machine, `/health`, and the bootconfig endpoint. e2e: full create→running→stop→start→destroy over the FakeComputeProvider. Every bug fix lands a failing-first regression test.

### Claude's Discretion
- Router/service file layout within `api/` (follow tech-spec §4.1 + Phase-0 patterns), exact logging library/format, the stub-ttyd test double's shape, and the in-flight lock mechanism (asyncio lock keyed by workspace id vs DB advisory) are at Claude's discretion within the above constraints.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets (from Phase 0 — frozen contracts)
- `api/lib/envelope.py` (`respond`/`respond_error`), `api/models/*` (CamelModel + Workspace/Event/Template + compute DTOs ComputeTask/ComputeStatus/BootConfig), `api/config.py` (Settings: provider switch, pool range, capacity threshold, ttyd timeouts, `proxmox_ca_cert_path`).
- `api/compute/provider.py` (ComputeProvider ABC — the method set to implement for real in `proxmoxProvider.py`) + `fakeProvider.py` (deterministic Fake for unit/e2e). `api/db/provider.py` (DbProvider ABC) + `sqliteProvider.py` (+ `_connect()` with `PRAGMA foreign_keys=ON`) + `migrations/001_init.sql`.
- `api/main.py` (`create_app()` factory + `get_compute`/`get_db` DI seam — extend with routers + middleware here).

### Established Patterns (CLAUDE.md — non-negotiable)
- `/api/v1` + envelope; snake_case DB → camelCase JSON via CamelModel; provider seams abstract (no driver leaks); structured JSON logging; security headers; SPDX header on every file; Conventional Commits; failing-first regression tests.

### Integration Points
- Routers register on the app factory; `WorkspaceService` depends only on the `DbProvider` + `ComputeProvider` ABCs. The `002_*.sql` migration adds the partial unique index on `vmid`.
</code_context>

<specifics>
## Specific Ideas

Implement the corrected saga (SC-1..SC-12), NOT the tech-spec §6 happy-path pseudocode (it treats async Proxmox mutations as synchronous, clones before persisting, and uses cloud-init injection — all wrong). The integration tier's Proxmox mock and stub-ttyd MUST be protocol-accurate (UPID task responses; the stub ttyd is for the bootconfig/health path here, the `tty` subprotocol bridge is Phase 2). CI proves the saga + compensation over mocks; real Proxmox clone/boot is the dev-homelab smoke gate.
</specifics>

<deferred>
## Deferred Ideas

- Real-Proxmox acceptance of `ProxmoxComputeProvider` (actual clone/start/stop/destroy/IP) → dev-homelab smoke gate (no Proxmox reachable from this box) — `human_needed`, not phase-blocking.
- The WS terminal proxy + `tty` subprotocol bridge → Phase 2. The `burrow-boot.sh` pull-step that consumes the bootconfig endpoint → Phase 3. Reaper / auto-stop / restore → Phase 4.
</deferred>
