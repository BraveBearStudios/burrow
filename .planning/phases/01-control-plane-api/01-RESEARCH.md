<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Phase 1: Control Plane API - Research

**Researched:** 2026-06-10
**Domain:** FastAPI control plane — create/stop/start/destroy saga over real `proxmoxer` + `aiosqlite`, server-enforced state machine, race-safe VMID reservation, pull-at-boot bootconfig endpoint, security middleware, hermetic test pyramid
**Confidence:** HIGH (built on the frozen Phase-0 contracts + SC-1..SC-13 corrections + four locked ADRs; library APIs verified live against PyPI + proxmoxer docs on 2026-06-10)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Create saga (SC-1, SC-2, SC-11)** — Order: (1) capacity guard; (2) persist `creating` row + reserved VMID BEFORE clone (SC-2, recoverability); (3) `cloneCt(full=True)` and block on the UPID task to OK (SC-1); (4) `injectBootConfig` = DB write only (pull-at-boot, ADR-0002) — no `pct`/cloud-init; (5) `startCt` (block on UPID); (6) resolve the static IP from VMID (SC-6, ADR-0004) — no DHCP poll; (7) await ttyd health (HTTP GET `:7681`, 60s timeout / 2s interval); (8) mark `running`. Per-step compensation (SC-11): any failure tears down the partial clone, frees the VMID reservation, and lands the row in `error` (never stuck `creating`). Saga is idempotent/recoverable.

**VMID allocation (SC-3, SC-4)** — Race-safe via a DB unique reservation using a partial unique index `... WHERE deletedAt IS NULL` in a `002_*.sql` migration (a plain UNIQUE would break destroy-then-recreate). `getNextVmid` is bounded to the worker pool range and backed by this reservation — `usedVmids`→`getNextVmid` is NOT race-safe on its own; the DB index is the arbiter.

**State machine (SC-12)** — Server-side transition table rejects illegal transitions with an envelope error (stop-during-creating, start-on-destroyed, double-destroy). A per-workspace in-flight lock blocks concurrent mutations on one workspace.

**API surface (PLAT-01/02/03)** — All routes under `/api/v1`; standard `data`/`meta`/`error` envelope (reuse the Phase-0 helper). `GET /api/v1/health` reports overall + `db` + `compute` connectivity (provider `healthcheck()`). Endpoints: `GET/POST /api/v1/workspaces`, `GET /api/v1/workspaces/{id}`, `POST .../{id}/stop|start`, `DELETE .../{id}`, `GET .../{id}/events`, `GET /api/v1/templates`, plus the internal bootconfig endpoint.

**Pull-at-boot bootconfig endpoint (WORK-03, ADR-0002)** — `GET /api/v1/internal/bootconfig/{vmid}` returns the worker's non-secret config (config repo/branch, project repo/branch) + a short-lived, repo-scoped git credential minted per-fetch and discarded. Threat model: validate `vmid ∈ [pool_start, pool_end]`; non-secret payload only; the worker is identified by its static source IP (derived from VMID); never log the credential. The endpoint contract is built here; the `burrow-boot.sh` consumer pull-step is Phase 3.

**Security & observability (PLAT-04, PLAT-05)** — Structured JSON logging (no secrets/tokens/credentials in log or event payloads). Security headers middleware on all responses; CORS restricted to the LAN origin (non-`*`). LAN-only-no-auth posture preserved — no auth added.

**Capacity & node selection (CAP-01, CAP-04)** — Refuse create when `getNodeMemory(node) > 0.80` (CapacityError → envelope error). Operator selects the node at create time (manual; auto-select is Phase 4/v2).

**ProxmoxComputeProvider (real impl)** — Fill the Phase-0 skeleton with `proxmoxer` calls behind the ABC: clone/start/stop/destroy each block on the Proxmox UPID (`Tasks.blocking_status`, assert exitstatus OK), set `net0` static IP at clone, query node memory, CA-pinned TLS (`PROXMOX_CA_CERT_PATH`, never `verify_ssl=False`). No proxmoxer types leak past the ABC. Real-Proxmox acceptance is the dev-homelab smoke gate (deferred).

**Tests (CICD-02, CICD-03)** — Unit: saga + state machine + VMID reservation + capacity guard over the `FakeComputeProvider`. Integration: FastAPI via `httpx.ASGITransport` against real SQLite (exercises migrations + DbProvider) with the Proxmox HTTP API mocked (`respx`) and a protocol-accurate stub ttyd; cover the full CRUD, the create saga incl. compensation, the state machine, `/health`, and the bootconfig endpoint. e2e: full create→running→stop→start→destroy over the FakeComputeProvider. Every bug fix lands a failing-first regression test.

### Claude's Discretion

- Router/service file layout within `api/` (follow tech-spec §4.1 + Phase-0 patterns).
- Exact logging library/format.
- The stub-ttyd test double's shape.
- The in-flight lock mechanism (asyncio lock keyed by workspace id vs DB advisory).

(All four are constrained by the locked decisions above.)

### Deferred Ideas (OUT OF SCOPE)

- Real-Proxmox acceptance of `ProxmoxComputeProvider` (actual clone/start/stop/destroy/IP) → dev-homelab smoke gate (no Proxmox reachable from this box) — `human_needed`, not phase-blocking.
- The WS terminal proxy + `tty` subprotocol bridge → Phase 2.
- The `burrow-boot.sh` pull-step that consumes the bootconfig endpoint → Phase 3.
- Reaper / auto-stop / restore → Phase 4.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PLAT-01 | All API routes under `/api/v1` | Router structure (APIRouter `prefix="/api/v1"`); main.py `include_router`. Bootconfig under `/api/v1/internal/...`. |
| PLAT-03 | `GET /api/v1/health` reports overall + db + compute | Aggregate `db.healthcheck()` + `compute.healthcheck()`; degrade-not-500 pattern below. |
| PLAT-04 | Structured JSON logs | stdlib `logging` + JSON formatter (recommended) vs `structlog`; secret-redaction discipline. |
| PLAT-05 | Security headers on responses | `BaseHTTPMiddleware` SecurityHeaders + non-`*` CORS (LAN origin). |
| WS-01 | Create from name/repo/branch/plugin/node | `WorkspaceCreate` (already in models); maps to `createWorkspace` saga. |
| WS-02 | Full create saga, awaiting each UPID (SC-1, SC-2) | 8-step saga table; UPID-blocking provider; persist-before-clone. |
| WS-03 | Compensation on failure, no orphan (SC-9) | Per-step reverse-compensation; `error` not `creating`; idempotent destroy. |
| WS-04 | List, filterable by status | `listWorkspaces(status)` (already in DbProvider). |
| WS-05 | Fetch single by id | `getWorkspace` (already in DbProvider). |
| WS-06 | Stop running (state preserved) | `stopCt` UPID-blocked; status→`stopped`; transition guard. |
| WS-07 | Start stopped (await ttyd health) | `startCt` + IP + ttyd-health; status→`running`. |
| WS-08 | Destroy (stop+destroy LXC, soft-delete row) | `stopCt`→`destroyCt`→`softDeleteWorkspace`; idempotent. |
| WS-09 | Enforced state machine | Transition table (below); illegal→envelope error. |
| WS-10 | Race-safe VMID via partial unique index (SC-3) | `002_*.sql` partial unique index; INSERT-as-reservation; collision→retry. |
| WS-11 | Event log readable | `logEvent` writes; new `getEvents`/`listEvents` DbProvider method + `GET .../events`. |
| WORK-03 | Boot config via pull-at-boot (ADR-0002) | `injectBootConfig`=DB write; `GET /api/v1/internal/bootconfig/{vmid}`; secret hygiene. |
| CAP-01 | Refuse create at node RAM > threshold | `getNodeMemory(node) > 0.80` → `CapacityError` → envelope error. |
| CAP-04 | Operator selects node at create | `WorkspaceCreate.node` (already present); no auto-select. |
| CICD-02 | Test pyramid (unit→integration→e2e) | Validation Architecture section; respx + stub ttyd + ASGITransport. |
| CICD-03 | Failing-first regression test per bug fix | Regression-test discipline embedded in each tier. |
</phase_requirements>

## Summary

Phase 1 fills the frozen Phase-0 skeletons with the real lifecycle engine. The hard, novel work is concentrated in three places: (1) a **`ProxmoxComputeProvider`** that wraps a *synchronous* `proxmoxer` (requests-based) client and blocks on every Proxmox UPID task before returning — and does so without stalling the asyncio event loop; (2) a **`WorkspaceService` create saga** that persists a `creating` row with a DB-reserved VMID *before* the clone and runs per-step compensation on any failure, so a failed create never orphans an LXC or wedges a row in `creating`; and (3) a **race-safe VMID reservation** built on a `002_*.sql` partial unique index (`WHERE deletedAt IS NULL`) where the DB INSERT — not the in-process `getNextVmid` scan — is the allocation arbiter. Everything else (routers, `/health`, security middleware, the bootconfig endpoint, structured logging) is well-trodden FastAPI work, but the integration test tier must be **protocol-accurate** (real SQLite via migrations, `respx`-mocked Proxmox returning realistic UPID task responses, a stub ttyd that answers the health GET) or it will paper over the exact bugs SC-1..SC-12 exist to prevent.

The single most important correction to absorb: **do not implement tech-spec §6.2's pseudocode.** It treats async Proxmox mutations as synchronous, clones before persisting the row, and injects via cloud-init — all three are wrong for LXC. The authoritative behavior is the SC-corrected saga in CONTEXT.md (matching `.planning/research/ARCHITECTURE.md` Pattern 1) and the four locked ADRs (0002 pull-at-boot, 0003 ACL scoping → clone must add the VMID to the pool, 0004 static-IP-from-VMID, 0005 `--full` clone). The Phase-0 `ComputeProvider` ABC already encodes the corrected method set (`cloneCt(full=True)`, `injectBootConfig` as a DB-write seam, `getIp` computed-not-polled, `waitTask`), so the saga and provider just have to honor it.

**Primary recommendation:** Build in dependency order — (a) `002_*.sql` + the `SqliteProvider` reservation + `getEvents` extension; (b) the `WorkspaceService` saga + state machine over the `FakeComputeProvider` (fully unit-testable, zero Proxmox); (c) `/api/v1` routers + envelope success-wrapping + `/health` + security middleware + the bootconfig endpoint; (d) the real `ProxmoxComputeProvider` (proxmoxer bodies, `respx`-mocked in CI, dev-homelab for real infra). Wrap every blocking proxmoxer call in `asyncio.to_thread`. Land the integration tier (real SQLite + respx + stub ttyd) alongside (c)/(d).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| HTTP request shape, envelope wrapping, error→code mapping | Routers (`api/routers/`) | — | Thin: parse/validate/wrap only; never touches a provider impl (ARCHITECTURE component table). |
| Create/stop/start/destroy saga, state-machine enforcement, capacity guard, VMID allocation policy, compensation | `WorkspaceService` (`api/services/`) | — | The orchestration core; depends ONLY on the two ABCs (CLAUDE.md seam rule). |
| Proxmox clone/start/stop/destroy, UPID blocking, static-IP set, node-memory query, pool membership add | `ProxmoxComputeProvider` (`api/compute/`) | — | The only place `proxmoxer`/`Tasks.blocking_status`/`ProxmoxAPI` appear (seam-leakage audit). |
| Persistence, soft-delete, VMID reservation INSERT, event log, migrations | `SqliteProvider` (`api/db/`) | — | The only place `aiosqlite` + raw SQL appear; the partial unique index is the allocation arbiter. |
| Bootconfig issuance (non-secret payload + short-lived git credential), vmid-in-pool validation | Router (`api/routers/internal.py` or `bootconfig.py`) | `WorkspaceService` (lookup by vmid) | A control-plane HTTP surface; the worker is the client (pull-at-boot, ADR-0002). The main ASVS L1 surface. |
| Structured JSON logging, security headers, CORS | App factory / middleware (`api/main.py`) | — | Cross-cutting; applied once at the ASGI boundary. |
| Capacity decision (RAM fraction vs threshold) | `WorkspaceService` | `ProxmoxComputeProvider.getNodeMemory` (data) | Provider returns the fraction; the *policy* (> 0.80 → refuse) lives in the service (CAP-01). |

**Tier-correctness note for the planner:** No business logic in routers; no `proxmoxer`/`aiosqlite` in `WorkspaceService`; the capacity *threshold* and the state-transition *table* are service-owned, not provider-owned. The bootconfig endpoint is a router that reads the DB (by VMID) and mints a credential — it is the one router with a real threat model.

## Standard Stack

All packages are already pinned in Phase-0 `pyproject.toml` from `.planning/research/STACK.md`; Phase 1 adds **no new runtime dependency** (the WS-client `websockets` leg is Phase 2). Versions re-verified on PyPI 2026-06-10.

### Core (already installed — confirm, do not re-add)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | 0.136.3 | Routers, DI (`Depends`), `/health`, bootconfig endpoint | Spec mandate; native `APIRouter` + dependency injection. `[VERIFIED: PyPI 2026-06-10]` |
| proxmoxer | 2.3.0 | Real Proxmox API client (`ProxmoxComputeProvider`) | Spec mandate; thin HTTPS wrapper, ships `Tasks.blocking_status` for UPID waits. `[VERIFIED: PyPI 2026-06-10]` |
| aiosqlite | 0.22.1 | Async SQLite (`SqliteProvider`, `002_*.sql`) | Spec mandate / ADR-0001. `[VERIFIED: PyPI 2026-06-10]` |
| httpx | 0.28.1 | ttyd health poll (`GET :7681`) + ASGI test transport | Used in saga step 7 + integration tier. `[VERIFIED: PyPI 2026-06-10]` |
| pydantic | 2.13.4 | `WorkspaceCreate` validation, envelope shaping | snake↔camel via `CamelModel` (frozen Phase-0). `[CITED: STACK.md]` |
| pydantic-settings | 2.14.1 | `Settings` (pool range, threshold, CA path) | Already wired in `api/config.py`. `[CITED: STACK.md]` |

### Supporting (dev/test — already installed)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest + pytest-asyncio | 9.0.3 / 1.4.0 | Async test runner (`asyncio_mode="auto"`) | All tiers. `[CITED: STACK.md]` |
| respx | 0.23.1 | Mock the **httpx** legs (ttyd health GET) | Integration tier. `[VERIFIED: PyPI 2026-06-10]` |
| responses | 0.26.1 | Mock proxmoxer's underlying **requests** calls | When mocking the Proxmox HTTP API at the provider level (proxmoxer is requests-based, NOT httpx — see Pitfall 5 below). `[CITED: STACK.md]` |

### Logging library (Claude's Discretion — recommendation below)

| Option | Tradeoff | Recommendation |
|--------|----------|----------------|
| stdlib `logging` + a small JSON formatter | Zero new dep; one `Formatter` subclass emitting `{ts, level, logger, msg, ...extra}`; routes uvicorn logs through the same handler | **Recommended.** PLAT-04 only requires "structured JSON logs"; KISS (CLAUDE.md). No new dependency, no future-proofing. `[ASSUMED]` (A1) |
| `structlog` | Composable processors, contextvars request-id propagation, native JSON renderer; faster JSON; more setup | Adopt only if request-scoped context propagation becomes a real need (it is not in v1). Defer. `[CITED: apitally.io/blog/fastapi-logging-guide]` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `asyncio.to_thread` wrapping proxmoxer | An async Proxmox client | None mature/maintained at proxmoxer's coverage; proxmoxer is the spec mandate. Wrap the sync client. |
| respx for the Proxmox mock | responses (requests-mock) | **Use responses for the Proxmox leg** — proxmoxer rides `requests`, which respx (httpx-only) cannot intercept. Use respx only for the httpx ttyd-health leg. |
| stdlib JSON formatter | structlog / loguru | structlog is heavier; loguru diverges from stdlib. KISS wins for v1. |

**Installation:** No new packages. Verify the lockfile is unchanged for runtime deps:

```bash
cd api && uv lock --check
```

## Package Legitimacy Audit

> No new external packages are introduced in Phase 1. Every library below was installed and audited in Phase 0 (all from the spec-mandated stack, all major maintained projects). slopcheck was not run because no install occurs this phase; the existing `uv.lock` is the authority and `uv lock --check` is a CI gate (CICD-01).

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| fastapi | PyPI | 7+ yrs | ~100M/mo | github.com/fastapi/fastapi | n/a (no install) | Approved (Phase-0) |
| proxmoxer | PyPI | 10+ yrs | established | github.com/proxmoxer/proxmoxer | n/a | Approved (Phase-0) |
| aiosqlite | PyPI | 7+ yrs | high | github.com/omnilib/aiosqlite | n/a | Approved (Phase-0) |
| httpx | PyPI | 6+ yrs | very high | github.com/encode/httpx | n/a | Approved (Phase-0) |
| respx | PyPI | 5+ yrs | established | github.com/lundberg/respx | n/a | Approved (Phase-0) |
| responses | PyPI | 9+ yrs | very high | github.com/getsentry/responses | n/a | Approved (Phase-0) |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
  Operator browser / curl (LAN)
        │  POST /api/v1/workspaces {name, projectRepo, branch, pluginSet, node}
        ▼
  ┌───────────────────────────────────────────────────────────────┐
  │ FastAPI app (create_app factory)                              │
  │  ── middleware (outermost→inner): CORS(LAN origin) →          │
  │       SecurityHeaders → (envelope success-wrap)               │
  │                                                               │
  │  routers/workspaces.py  ── parse WorkspaceCreate, wrap reply  │
  │        │  Depends(get_service)                                │
  │        ▼                                                       │
  │  WorkspaceService.createWorkspace(payload)                    │
  │     0 capacity guard ── compute.getNodeMemory(node) ≤ 0.80    │
  │     1 reserve VMID    ── getNextVmid(snapshot) then           │
  │                          db.createWorkspace(status=creating,  │
  │                          vmid=N)  ◀── partial-unique INSERT    │
  │                          is the race arbiter (collision→retry)│
  │     2 clone           ── compute.cloneCt(full=True)           │
  │                          → block on UPID (waitTask, OK)       │
  │     3 inject bootcfg  ── compute.injectBootConfig (DB write)  │
  │     4 start           ── compute.startCt → block on UPID      │
  │     5 resolve IP      ── compute.getIp (computed from VMID)   │
  │     6 ttyd health     ── httpx GET http://{ip}:7681/ (60s)    │
  │     7 mark running    ── db.updateWorkspace(status=running)   │
  │        │                                                      │
  │     ANY failure after step 1 ─▶ COMPENSATE (reverse):        │
  │        stop+destroy CT (idempotent) · row→error (not delete) │
  └───────────────┬───────────────────────────────┬──────────────┘
                  │ ComputeProvider ABC            │ DbProvider ABC
                  ▼                                ▼
   ProxmoxComputeProvider                  SqliteProvider
    (proxmoxer, sync, run in              (aiosqlite, 001+002 migrations,
     asyncio.to_thread; UPID waits;        partial unique index on vmid)
     net0 static IP; pool-add;             → SQLite /data/burrow.db
     CA-pinned TLS)                         (FakeComputeProvider in CI)
        │
        ▼ HTTPS :8006 (real Proxmox — dev homelab only; respx/responses in CI)

  Worker LXC (Phase 3 consumer) ── GET /api/v1/internal/bootconfig/{vmid}
        ◀── non-secret {configRepo,branch,projectRepo,branch} + short-lived git cred
```

### Recommended Project Structure (extends the frozen Phase-0 tree)

```
api/
├── main.py                       # EXTEND: include_router(...), add middleware, get_service DI
├── config.py                     # (frozen) Settings: pool range, threshold, CA path
├── routers/                      # NEW this phase
│   ├── workspaces.py             #   /api/v1/workspaces CRUD + stop/start/destroy/events
│   ├── templates.py              #   /api/v1/templates
│   ├── health.py                 #   /api/v1/health (db + compute aggregate)
│   └── internal.py               #   /api/v1/internal/bootconfig/{vmid}  (ASVS surface)
├── services/                     # NEW this phase
│   └── workspaceService.py       #   saga + state machine + capacity + VMID policy + compensation
├── lib/
│   ├── envelope.py               # (frozen) respond / respond_error
│   ├── logging.py                # NEW: JSON formatter + setup (PLAT-04)
│   ├── middleware.py             # NEW: SecurityHeadersMiddleware (PLAT-05)
│   └── statemachine.py           # NEW (or inline in service): transition table + guard
├── compute/
│   ├── provider.py               # (frozen ABC)
│   ├── proxmoxProvider.py        # FILL: real proxmoxer bodies (UPID waits, net0, pool-add, mem)
│   └── fakeProvider.py           # (frozen) Fake for unit/e2e
├── db/
│   ├── provider.py               # EXTEND ABC: add getEvents(workspaceId)
│   ├── sqliteProvider.py         # EXTEND: reservation insert, getEvents, migrate runs 002
│   └── migrations/
│       ├── 001_init.sql          # (frozen)
│       └── 002_vmid_unique.sql   # NEW: partial unique index on vmid
└── tests/
    ├── unit/                     # saga/state-machine/VMID/capacity over Fake
    └── integration/             # ASGITransport + real SQLite + responses(proxmox) + stub ttyd
```

### Pattern 1: UPID-blocking provider over a synchronous proxmoxer client

**What:** Every mutating Proxmox call returns a UPID immediately; the work runs async on the node. The provider must block on the UPID (`Tasks.blocking_status`) and assert `exitstatus == "OK"` **before returning**, so `WorkspaceService` can never race clone→start (SC-1, Pitfall 1). `proxmoxer` is **synchronous** (requests-based), but the ABC methods are `async def` — so each blocking call must run in a worker thread to avoid stalling the event loop.

**When to use:** Every `cloneCt`/`startCt`/`stopCt`/`destroyCt`/`getNodeMemory`/`getNextVmid`/`usedVmids`.

**Example:**

```python
# Source: proxmoxer.github.io/docs/latest/{tools/tasks,basic_usage}  (verified 2026-06-10)
# api/compute/proxmoxProvider.py  — illustrative; the only file that may import proxmoxer
import asyncio
from proxmoxer import ProxmoxAPI
from proxmoxer.tools import Tasks
from models.compute import ComputeTask
from compute.provider import TaskFailedError, CloneError

class ProxmoxComputeProvider(ComputeProvider):
    def __init__(self, settings) -> None:
        self._settings = settings
        # CA-pinned TLS: pass the CA path to requests' `verify`; NEVER verify_ssl=False.
        self._api = ProxmoxAPI(
            settings.proxmox_host,
            user=settings.proxmox_user,
            token_name=settings.proxmox_token_name,
            token_value=settings.proxmox_token_value,
            verify_ssl=settings.proxmox_ca_cert_path,   # str path → requests verify=<path>
        )

    async def _block(self, upid: str, timeout: float) -> ComputeTask:
        # blocking_status polls until the task leaves 'running' or timeout; None on timeout.
        status = await asyncio.to_thread(
            Tasks.blocking_status, self._api, upid, timeout
        )
        if status is None:
            raise TaskFailedError(f"task {upid} timed out after {timeout}s")
        exit_ = status.get("exitstatus")
        if exit_ != "OK":
            raise TaskFailedError(f"task {upid} exited {exit_!r}")
        return ComputeTask(upid=upid, status="ok", exitstatus=exit_)

    async def cloneCt(self, template_vmid, new_vmid, name, node, full=True) -> ComputeTask:
        def _do() -> str:
            upid = self._api.nodes(node).lxc(template_vmid).clone.post(
                newid=new_vmid, hostname=name, full=1 if full else 0,
            )
            # ADR-0003: scoped to /pool/burrow-workers → add the new VMID to the pool
            self._api.pools("burrow-workers").put(vms=str(new_vmid))
            # ADR-0004: set static net0 from VMID (CIDR ip=, bare gw=)
            self._api.nodes(node).lxc(new_vmid).config.put(net0=self._net0_for(new_vmid))
            return upid
        try:
            upid = await asyncio.to_thread(_do)
        except Exception as e:                       # proxmoxer ResourceException etc.
            raise CloneError(str(e)) from e
        return await self._block(upid, timeout=self._settings.clone_timeout)
```

Key points: `Tasks.blocking_status(prox, task_id, timeout=300, polling_interval=0.01)` returns a dict with `exitstatus` (`"OK"` on success) or `None` on timeout `[VERIFIED: proxmoxer docs]`. The POST return value **is** the UPID string `[CITED: proxmoxer basic_usage]`. `verify_ssl` accepts a CA-cert path and forwards it to `requests` `verify` `[VERIFIED: proxmoxer issue #65 + requests semantics]`.

### Pattern 2: Persist-before-clone saga with reverse compensation

**What:** A multi-step transaction across Proxmox + DB with no shared rollback. Persist the `creating` row (with the reserved VMID) **first**, then clone; on any post-reservation failure, run compensations in reverse and land the row in `error` (never delete — keep audit; never leave `creating`).

**When to use:** `createWorkspace`. (stop/start/destroy are simpler single-mutation sagas but still UPID-blocked + state-guarded.)

**Canonical create saga (CONTEXT.md / ARCHITECTURE Pattern 1):**

| Step | Forward | Compensation on later failure |
|------|---------|-------------------------------|
| 0 capacity guard | `getNodeMemory(node) ≤ 0.80` | (read-only) |
| 1 reserve VMID + row | `getNextVmid(snapshot)` → `db.createWorkspace(status=creating, vmid=N)` | mark `error` (keep row) + free reservation |
| 2 clone | `cloneCt(full=True)` + block UPID | `destroyCt(vmid)` (idempotent) |
| 3 inject bootcfg | `injectBootConfig(vmid, cfg)` (DB write) | (covered by step-2 destroy) |
| 4 start | `startCt(vmid)` + block UPID | `stopCt` then `destroyCt` |
| 5 resolve IP | `getIp(vmid)` (computed) | `stopCt`+`destroyCt` |
| 6 ttyd health | httpx GET `:7681` (60s/2s) | `stopCt`+`destroyCt` |
| 7 mark running | `db.updateWorkspace(status=running)` | — |

```python
# Illustrative — api/services/workspaceService.py
async def createWorkspace(self, payload: WorkspaceCreate) -> Workspace:
    # 0
    if await self.compute.getNodeMemory(payload.node) > self.threshold:
        raise CapacityError(payload.node)
    # 1 reserve (DB partial-unique INSERT is the arbiter; retry on collision)
    ws = await self._reserve_vmid_and_row(payload)
    vmid = ws.vmid
    try:
        await self.compute.cloneCt(self.template_vmid, vmid, payload.name, payload.node)  # 2
        await self.compute.injectBootConfig(vmid, self._boot_config(payload))             # 3
        await self.compute.startCt(payload.node, vmid)                                     # 4
        ip = await self.compute.getIp(payload.node, vmid)                                  # 5
        await self.db.updateWorkspace(ws.id, {"lxc_ip": ip})
        await self._wait_ttyd(ip)                                                          # 6
        await self.db.logEvent(ws.id, "workspace.created", {})
        return await self.db.updateWorkspace(ws.id, {"status": "running"})                 # 7
    except Exception as exc:
        await self._compensate(payload.node, vmid)         # idempotent stop+destroy
        await self.db.logEvent(ws.id, "boot.error", {"reason": _safe(exc)})  # no secrets
        await self.db.updateWorkspace(ws.id, {"status": "error"})
        raise
```

`_compensate` must tolerate a not-yet-cloned VMID (destroy a nonexistent CT is a no-op success), so a failure at step 2 and step 6 both clean up safely (Pitfall 7/8). The `FakeComputeProvider`'s `FakeFailures(raise_on_nth_call={...})` hook (frozen Phase-0) drives these compensation tests deterministically.

### Pattern 3: Race-safe VMID reservation via partial unique index

**What:** `getNextVmid` is a *pure scan over a snapshot* — it does NOT reserve (the ABC docstring says this explicitly). The atomic reservation is the DB `INSERT` under `CREATE UNIQUE INDEX ... ON workspaces(vmid) WHERE deletedAt IS NULL`. A second concurrent create that picks the same free VMID gets an `IntegrityError` on INSERT; treat it as "lost the race" and retry the scan (Pitfall 2, SC-3/SC-4).

**Why partial:** A plain `UNIQUE(vmid)` collides with soft-deleted tombstones when the 100-id pool recycles a VMID (Pitfall 9). The `WHERE deletedAt IS NULL` predicate lets a tombstoned `vmid=207` coexist with a freshly-recycled active `207`.

**`002_vmid_unique.sql`:**

```sql
-- SPDX-FileCopyrightText: 2026 Brave Bear Studios
-- SPDX-License-Identifier: AGPL-3.0-or-later
-- Migrations: /api/db/migrations/002_vmid_unique.sql
-- SC-3/SC-4 / WS-10: race-safe VMID reservation that survives destroy-then-recreate.
CREATE UNIQUE INDEX IF NOT EXISTS idx_workspaces_vmid_active
  ON workspaces(vmid)
  WHERE deletedAt IS NULL AND vmid IS NOT NULL;
```

(SQLite supports partial indexes; `vmid IS NOT NULL` keeps rows whose VMID is not yet assigned out of the index. Verify the `migrate()` method runs **both** 001 and 002 — the frozen `SqliteProvider.migrate()` only checks for the `workspaces` table and `executescript`s a single file; it must be extended to apply 002, e.g. a small ordered-migrations loop with a `schema_migrations` ledger or an explicit "apply 002 if index absent" check.)

**Reservation insert (service-side):**

```python
async def _reserve_vmid_and_row(self, payload, attempts=10) -> Workspace:
    for _ in range(attempts):
        used = await self.compute.usedVmids() | await self._db_used_vmids()
        vmid = await self.compute.getNextVmid(self.pool_start, self.pool_end, used)
        try:
            return await self.db.createWorkspace({**payload_dict, "vmid": vmid,
                                                  "status": "creating"})
        except VmidTakenError:        # SqliteProvider maps IntegrityError → this
            continue                  # lost the race; rescan + retry
    raise NoFreeVmidError(...)
```

`SqliteProvider.createWorkspace` must catch `aiosqlite.IntegrityError` on the vmid index and raise a typed `VmidTakenError` (a new db-seam error) so the service can distinguish "collision, retry" from a real failure. Union DB-known VMIDs with `compute.usedVmids()` (Proxmox truth) so a reaper-uncleaned row and a Proxmox leak both count as taken (ARCHITECTURE Pattern 2).

### Pattern 4: Server-side state-machine transition table

**What:** An explicit `{(from_state, action) → to_state}` table rejecting illegal transitions with an envelope error; a per-workspace in-flight lock blocks concurrent mutations on one workspace (SC-12, Pitfall 8).

```python
# Legal transitions (creating is internal-only; reached via create, never an action)
TRANSITIONS = {
    ("running", "stop"):    "stopped",
    ("stopped", "start"):   "running",
    ("running", "destroy"): "destroyed",
    ("stopped", "destroy"): "destroyed",
    ("error",   "destroy"): "destroyed",   # error's defined exit = destroy-only (decided)
}
def assert_transition(state: str, action: str) -> str:
    to = TRANSITIONS.get((state, action))
    if to is None:
        raise IllegalTransitionError(state, action)   # → 409 + envelope error
    return to
```

`error` is a **defined** state whose only exit is `destroy` (not retry) — pin this so the UI (Phase 2) gates correctly. The in-flight lock: a `dict[str, asyncio.Lock]` keyed by workspace id is sufficient for a single uvicorn worker; **note** that the spec runs `--workers 2`, so for true cross-process safety the DB is the ultimate guard (the reservation index covers create-create; for stop/destroy double-fire, an optimistic status-CAS `UPDATE ... WHERE status = :expected` is the cross-process equivalent). Recommend the asyncio-lock for in-process correctness **plus** status-guarded updates so a second worker's mutation fails safely (Claude's Discretion — both layers cheap). `[ASSUMED]` (A2: the `--workers 2` cross-process double-mutation edge is real but low-frequency for a single operator; the status-CAS is the honest guard.)

### Pattern 5: Routers + DI + degrade-not-500 `/health`

**What:** `APIRouter(prefix="/api/v1")`; the service is injected via `Depends(get_service)` where `get_service` composes `get_compute()` + `get_db()` (the frozen factory functions in `main.py`). Responses serialize camelCase via `model_dump(by_alias=True)` (the `CamelModel` mechanism, frozen Phase-0) wrapped in `respond(...)`.

```python
# api/main.py — compose the service from the frozen provider factories
def get_service(compute=Depends(get_compute), db=Depends(get_db)) -> WorkspaceService:
    return WorkspaceService(compute=compute, db=db, settings=settings)

# api/routers/health.py — aggregate; report degraded, do not 500
@router.get("/health")
async def health(compute=Depends(get_compute), db=Depends(get_db)):
    db_ok = await _safe(db.healthcheck)
    compute_ok = await _safe(compute.healthcheck)
    overall = "ok" if (db_ok and compute_ok) else "degraded"
    return respond({"status": overall,
                    "db": "ok" if db_ok else "error",
                    "compute": "ok" if compute_ok else "error"})
```

`/health` must catch provider exceptions and report `error` for that dependency rather than letting the envelope error-handler turn the whole call into a 500 — a degraded compute backend should still yield a 200 with `compute: "error"` so the operator sees *which* dependency is down (PLAT-03). FastAPI serializes Pydantic models with `by_alias` automatically when a `response_model` is set; since responses go through the `respond(...)` envelope helper (which takes already-serialized `data`), call `model.model_dump(by_alias=True)` before handing `data` to `respond` so JSON stays camelCase.

### Pattern 6: Pull-at-boot bootconfig endpoint (the ASVS surface)

**What:** `GET /api/v1/internal/bootconfig/{vmid}` returns the worker's **non-secret** identifiers (`configRepo`, `configBranch`, `projectRepo`, `projectBranch` — the `BootConfig` DTO already exists) plus a **short-lived, repo-scoped git credential minted per-fetch and discarded** (ADR-0002). The credential is never persisted to the worker env and never logged.

**Threat model (the main ASVS L1 surface for this phase):**
- **Input validation (ASVS V5):** validate `vmid ∈ [pool_start, pool_end]` (reject out-of-pool with 404/403, do not echo the value into an error that aids enumeration). The path param is an `int`; FastAPI rejects non-int.
- **Identity (LAN posture):** the worker is identified by its **static source IP derived from its VMID** (ADR-0004) — the endpoint may assert `request.client.host == compute.getIp(vmid)` as a defense-in-depth check that the caller is the workspace it claims. This is not auth (v1 is no-auth LAN); it is a sanity binding that costs nothing.
- **Secrets in logs (ASVS V7):** the minted git credential MUST NOT appear in any structured log line or event payload. Add a redaction guard; log only `{vmid, repo, issued: true}`, never the token.
- **Credential mechanism (v1 placeholder):** v1 ships a **short-lived, repo-scoped placeholder credential** — the real minting (a GitHub App installation token, a deploy token, or an ephemeral PAT) is an operator-config detail. For Phase 1, the contract is: the endpoint returns a `gitCredential` field that is short-lived and single-repo-scoped; the actual issuance is pluggable (read a configured token from `Settings` and return it, or call out to a token broker). Mark the issuance mechanism as `[ASSUMED]` (A3) — it needs operator confirmation; do not hard-code a long-lived PAT.

```python
@router.get("/internal/bootconfig/{vmid}")
async def bootconfig(vmid: int, request: Request,
                     service: WorkspaceService = Depends(get_service)):
    if not (settings.worker_pool_start <= vmid <= settings.worker_pool_end):
        raise IllegalVmidError(vmid)                  # → 404 envelope, no enumeration aid
    ws = await service.get_by_vmid(vmid)              # new lookup; 404 if none/destroyed
    payload = {
        "configRepo": settings.config_repo, "configBranch": settings.config_branch,
        "projectRepo": ws.project_repo, "projectBranch": ws.project_branch,
        "gitCredential": await service.mint_repo_credential(ws.project_repo),  # short-lived
    }
    logger.info("bootconfig.issued", extra={"vmid": vmid, "repo": ws.project_repo})  # NO cred
    return respond(payload)
```

### Pattern 7: Security headers + non-`*` CORS middleware

```python
# api/lib/middleware.py
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'none'"  # API-only
        return response
# Note: omit HSTS for a LAN HTTP app (no TLS at the API; nginx terminates) — adding
# Strict-Transport-Security on a plain-HTTP LAN service is misleading.

# api/main.py — CORS FIRST (outermost), then security headers
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CORSMiddleware,
    allow_origins=[settings.allowed_origin],   # the LAN UI origin, NEVER "*"
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
```

`allow_origins=["*"]` is **incompatible with `allow_credentials=True`** and contradicts Pitfall 12 — read the LAN origin from `Settings` (add `allowed_origin`, default the LAN UI host). CORS must be added so it is the outermost middleware (handles preflight + error responses) `[CITED: fastapi.tiangolo.com/advanced/middleware + Discussion #8548]`.

### Anti-Patterns to Avoid

- **Implementing tech-spec §6.2 literally:** synchronous-treated mutations, clone-before-row, cloud-init injection. All three are SC-corrected and ADR-overridden. Use the CONTEXT saga.
- **`verify_ssl=False`** (the spec §6.1 snippet): forbidden by CLAUDE.md + the Phase-0 skeleton. Pass the CA-cert path.
- **Blocking proxmoxer calls on the event loop:** every proxmoxer call is sync; un-wrapped it stalls all concurrent requests (Performance Traps). Wrap in `asyncio.to_thread`.
- **In-process `asyncio.Lock` as the VMID guard:** defeated by `--workers 2`. The DB partial-unique index is the arbiter; the lock is only an in-process optimization.
- **Bare echo stub ttyd / mocking only success:** hides UPID-race and compensation bugs. The stub must answer the health GET; the Proxmox mock must return realistic UPID strings and a `blocking_status` that can be made to fail.
- **`error.message` leaking internals / creds in event `data`:** envelope errors carry a safe code+message; `boot.error` events and logs are redacted.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Wait for a Proxmox clone/start to finish | A hand-rolled `GET /tasks/{upid}/status` poll loop | `proxmoxer.tools.Tasks.blocking_status` | Handles UPID decode, polling, timeout, and the `stopped`+`exitstatus` semantics correctly (Pitfall 1). |
| Compute a worker IP | A DHCP interface poll | The VMID→IP formula (ADR-0004) | Unprivileged LXC has no guest agent; the interfaces API is unreliable (SC-6). |
| Race-safe VMID allocation | An in-process lock or `/cluster/nextid` | DB partial-unique-index INSERT + retry | `/cluster/nextid` is not race-safe; a lock is defeated by `--workers 2` (SC-3, PROXMOX-PRIMING §5). |
| Run a sync client in async code | Manual thread pools | `asyncio.to_thread(fn, *args)` | One-liner, correct executor handling, no event-loop stall. |
| Mock the Proxmox HTTP API | A fake HTTP server | `responses` (requests-mock) | proxmoxer rides `requests`; `responses` intercepts it. respx is httpx-only (won't catch proxmoxer). |
| camelCase JSON | Per-field mapping | `CamelModel.model_dump(by_alias=True)` | The sole snake↔camel mechanism, frozen Phase-0 (PLAT-09). |
| Security headers | Hand-set per route | One `BaseHTTPMiddleware` | Applied once at the boundary for every response incl. errors (PLAT-05). |

**Key insight:** Almost every hard part of this phase has a correct library primitive (`blocking_status`, `to_thread`, partial indexes, `responses`, `CamelModel`). The custom code that *should* exist is the **saga orchestration and the compensation tree** — that is the genuinely novel logic; everything else is wiring.

## Common Pitfalls

### Pitfall 1: Treating Proxmox mutations as synchronous (SC-1)
**What goes wrong:** `clone` then immediately `start`/`getIp` races a not-yet-cloned CT → "CT is locked", intermittent boot failures vanishing under a manual sleep.
**Why it happens:** The HTTP 200 means "task accepted," not "done"; a `--full` clone of a 30 GB rootfs takes seconds-to-minutes (worse on non-thin storage).
**How to avoid:** Block on the UPID inside the provider (`Tasks.blocking_status`, assert `OK`) before returning. Budget `--full` clone time into the `waitTask` timeout, NOT the ttyd-health timeout (ADR-0005).
**Warning signs:** Tests pass against the Fake (instant tasks) but real creates fail; "volume already exists."

### Pitfall 2: proxmoxer is sync — wrap or stall the loop
**What goes wrong:** Calling `self._api.nodes(...).clone.post(...)` directly from an `async def` blocks the entire event loop for the clone's duration; `/health` and other requests hang.
**Why it happens:** proxmoxer is requests-based; there is no async client. The ABC is `async` but the impl is sync underneath.
**How to avoid:** `await asyncio.to_thread(blocking_fn, ...)` for every proxmoxer call. (This is why the `respx` mock cannot intercept the Proxmox leg — see Pitfall 5.)
**Warning signs:** Concurrent requests serialize; latency spikes during a create. `[VERIFIED: proxmoxer is requests-based, PyPI + GitHub]`

### Pitfall 3: VMID race + tombstone collision (SC-3/SC-4)
**What goes wrong:** Two creates pick the same free VMID; or a recycled VMID collides with a soft-deleted row's `vmid`.
**Why it happens:** `getNextVmid` is a TOCTOU scan; a plain `UNIQUE(vmid)` includes tombstones.
**How to avoid:** The `002_*.sql` **partial** unique index (`WHERE deletedAt IS NULL`) + INSERT-as-reservation + catch `IntegrityError`→retry. Union DB + Proxmox used-sets.
**Warning signs:** "CT already exists" under rapid creates; `UNIQUE constraint failed: workspaces.vmid` after a destroy-recreate.

### Pitfall 4: Saga lands in `creating` or orphans an LXC (SC-9/SC-11)
**What goes wrong:** A failure after clone leaves a running CT + a row stuck `creating`; the 100-id pool slowly fills.
**Why it happens:** The happy path is written; compensation isn't, and "raise and bail" feels done against always-succeed mocks.
**How to avoid:** Per-step reverse compensation (stop+destroy, idempotent) + row→`error`. Test it with `FakeFailures(raise_on_nth_call=...)` at each step.
**Warning signs:** Rows stuck `creating`; "no free VMID" with few visible workspaces.

### Pitfall 5: respx cannot mock proxmoxer
**What goes wrong:** Writing the Proxmox integration mock with `respx` — it never intercepts, the real client tries to connect, tests fail or hit the network.
**Why it happens:** respx patches **httpx**; proxmoxer uses **requests**. They are different transports.
**How to avoid:** Mock the Proxmox HTTP API with **`responses`** (requests-mock). Use `respx` only for the **httpx** ttyd-health GET (saga step 6). Two different mock libraries for two different transports — by design (STACK.md).
**Warning signs:** Mocked routes never match; outbound connection attempts in test logs.

### Pitfall 6: `migrate()` only applies 001
**What goes wrong:** The frozen `SqliteProvider.migrate()` checks for the `workspaces` table and `executescript`s **one** file; the `002` index never gets created, and the reservation guard silently does nothing.
**Why it happens:** The Phase-0 migrate was written for a single migration.
**How to avoid:** Extend `migrate()` to apply ordered migrations (a `schema_migrations` ledger table, or an explicit "create 002 index if absent" step). Add an integration test that asserts the index exists and that a duplicate-active-vmid INSERT raises.
**Warning signs:** Two active rows with the same `vmid`; the destroy-then-recreate test passes for the wrong reason.

### Pitfall 7: Secrets in logs / event payloads (Pitfall 13 project-wide, ASVS V7)
**What goes wrong:** The bootconfig git credential, or a repo URL with an embedded token, lands in a structured log line or a `boot.error` event `data` blob.
**How to avoid:** Log only non-secret fields (`vmid`, `repo`, `issued: true`). Redact exception text before writing it to events. Never put the credential in any response field that is also logged.
**Warning signs:** gitleaks hits; a token visible in `events.data`.

## Code Examples

### Node memory fraction for the capacity guard (CAP-01)

```python
# Source: GET /nodes/{node}/status returns mem + maxmem in bytes (verified, Proxmox API)
async def getNodeMemory(self, node: str) -> float:
    status = await asyncio.to_thread(lambda: self._api.nodes(node).status.get())
    mem, maxmem = status["mem"], status["maxmem"]
    return mem / maxmem if maxmem else 1.0
# service: if await compute.getNodeMemory(node) > 0.80: raise CapacityError(node)
```

### ttyd health poll (saga step 6) — httpx, respx-mockable

```python
# Source: tech-spec §6.2 _waitForTtyd (the ONE part of §6.2 that is correct)
async def _wait_ttyd(self, ip: str) -> None:
    deadline = asyncio.get_event_loop().time() + self.ttyd_timeout   # 60s
    async with httpx.AsyncClient() as client:
        while asyncio.get_event_loop().time() < deadline:
            try:
                r = await client.get(f"http://{ip}:7681/", timeout=2)
                if r.status_code < 500:
                    return
            except (httpx.ConnectError, httpx.TimeoutException):
                pass
            await asyncio.sleep(2)
    raise WorkspaceBootError(f"ttyd not ready in {self.ttyd_timeout}s")
```

### Integration test wiring (real SQLite + ASGITransport + responses + stub ttyd)

```python
# Source: ci-cd §4.3 + httpx ASGITransport docs
@pytest.fixture
async def client(tmp_path):
    # real SQLite (exercises migrations 001+002), Fake or respx/responses Proxmox
    settings.database_path = str(tmp_path / "burrow.db")
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

# stub ttyd: a tiny aiohttp/uvicorn server (or a respx route on :7681) that answers
# GET / with 200 so the health poll resolves; the tty-subprotocol WS bridge is Phase 2.
```

## State of the Art

| Old Approach (tech-spec §6) | Current Approach (this phase) | When Changed | Impact |
|------------------------------|-------------------------------|--------------|--------|
| Sync-treated Proxmox calls | UPID-blocked + `asyncio.to_thread` | SC-1 / Phase 0 | No clone→start race; no loop stall. |
| Clone, then write row (step 5) | Persist row + VMID first (step 1) | SC-2 | Every failure is reaper-recoverable. |
| `getNextVmId` scan only | DB partial-unique-index reservation | SC-3/SC-4 | Race-safe across `--workers 2`; survives recycle. |
| `setCloudInitUserdata` | `injectBootConfig` = DB write + pull-at-boot | SC-5 / ADR-0002 | LXC has no cloud-init; secrets stay off worker env. |
| DHCP IP poll (`getLxcIp`) | IP computed from VMID | SC-6 / ADR-0004 | No agent, no poll, no race. |
| `verify_ssl=False` | CA-pinned `verify_ssl=<ca_path>` | Phase 0 | TLS actually verified (CLAUDE.md). |
| Un-versioned `/api/...` | `/api/v1/...` | PLAT-01 | Versioned surface. |

**Deprecated/outdated:** the entire tech-spec §6.2 `createWorkspace` pseudocode (ordering + cloud-init); `getLxcIp` DHCP polling; `verify_ssl=False`. Do not port them.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | stdlib `logging` + a JSON formatter satisfies PLAT-04 (vs structlog) | Standard Stack / logging | Low — both produce JSON; if request-scoped context becomes required, swap to structlog (additive). |
| A2 | A single uvicorn worker is the common dev case; cross-process stop/destroy double-fire is guarded by status-CAS, not just the asyncio lock | Pattern 4 | Low — the status-CAS `UPDATE ... WHERE status=:expected` is the honest cross-process guard; confirm `--workers` count at deploy. |
| A3 | The bootconfig git-credential issuance mechanism (deploy token vs GitHub App vs ephemeral PAT) is operator-config; v1 returns a short-lived repo-scoped placeholder | Pattern 6 | **Medium** — must NOT hard-code a long-lived PAT. Needs operator confirmation on the real minting mechanism (it is an ASVS-relevant decision). Phase-3 `burrow-boot.sh` consumes it. |
| A4 | `error` state's only exit is `destroy` (no in-place retry in v1) | Pattern 4 | Low — a retry path can be added later; destroy-only is the safe default and matches "ephemeral." |
| A5 | The `clone`/`start` UPID timeout values (clone budget vs ttyd-health budget kept separate) need concrete numbers in `Settings` | Pattern 1/2 | Low — add `clone_timeout`, `task_timeout` to `Settings`; defaults chosen conservatively; tune against real clone times in the homelab. |

## Open Questions

1. **Git-credential minting for bootconfig (A3).**
   - What we know: ADR-0002 mandates a short-lived, repo-scoped, used-and-discarded credential; never logged, never persisted to worker env.
   - What's unclear: the concrete issuer (GitHub App installation token / repo deploy token / ephemeral PAT). The repos in the test fixtures are placeholders.
   - Recommendation: build the endpoint with a pluggable `mint_repo_credential(repo)` seam that returns a short-lived value; v1 reads a configured short-lived token from `Settings` (gitignored `.env`) or returns a clearly-marked placeholder. Confirm the real mechanism with the operator before Phase 3 wires `burrow-boot.sh`. Do not hard-code a long-lived PAT.

2. **`--workers` count for the control plane (A2).**
   - What we know: tech-spec §10.2 mentions `--workers 2`; an in-process asyncio lock is then insufficient for stop/destroy double-fire.
   - What's unclear: whether v1 actually runs 2 workers in the dev/homelab deploy.
   - Recommendation: implement both guards (asyncio lock + status-CAS update) so correctness holds regardless; cheap, and the DB is authoritative.

3. **Pool-membership add timing on clone (ADR-0003).**
   - What we know: with `/pool/burrow-workers` scoping, each new VMID must be `pvesh set /pools/burrow-workers -vms <id>` (over the API: `pools(...).put(vms=...)`) or the scoped token loses rights over its own clone.
   - What's unclear: exact ordering vs the clone task (before vs after the clone UPID resolves) on the real cluster — a homelab-verifiable detail.
   - Recommendation: add the VMID to the pool as part of `cloneCt` (illustrated above); verify ordering against real Proxmox in the dev-homelab smoke gate.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 + uv | All backend work | ✓ (Phase-0 env) | 3.12 / 0.11.x | — |
| proxmoxer / aiosqlite / httpx / respx / responses | Provider + tests | ✓ (in `uv.lock`) | 2.3.0 / 0.22.1 / 0.28.1 / 0.23.1 / 0.26.1 | — |
| Real Proxmox node (:8006) | `ProxmoxComputeProvider` real-infra acceptance | ✗ (not reachable from this box) | — | **CI: respx/responses mock + FakeComputeProvider.** Real clone/boot deferred to dev-homelab smoke gate (CONTEXT deferred). |
| ttyd worker (:7681) | Real ttyd health | ✗ (no worker booted) | — | **Integration tier: protocol-accurate stub ttyd** answering the health GET; real ttyd is the homelab gate. |

**Missing dependencies with no fallback:** none that block this phase — every CI-provable surface runs hermetically (Fake + mocks + stub).
**Missing dependencies with fallback:** real Proxmox and real ttyd — both substituted in CI; their *real* behavior is the dev-homelab smoke gate (the "Looks Done But Isn't" acceptance authority), not a Phase-1 CI gate.

## Validation Architecture

> `workflow.nyquist_validation = true` in config.json — section included.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 1.4.0 (`asyncio_mode="auto"`) |
| Config file | `api/pyproject.toml` (`[tool.pytest.ini_options]`) — extend Phase-0 config |
| Quick run command | `cd api && uv run pytest tests/unit -x -q` |
| Full suite command | `cd api && uv run pytest -q` (unit + integration) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WS-02 | Create saga reaches `running` over Fake | unit | `pytest tests/unit/test_create_saga.py -x` | ❌ Wave 0 |
| WS-03 | Compensation: forced failure → `error`, no orphan (FakeFailures at each step) | unit | `pytest tests/unit/test_compensation.py -x` | ❌ Wave 0 |
| WS-09 | Illegal transitions rejected (stop-on-creating, start-on-destroyed, double-destroy) | unit | `pytest tests/unit/test_state_machine.py -x` | ❌ Wave 0 |
| WS-10 | Duplicate active vmid INSERT raises; destroy-recreate reuses vmid | integration | `pytest tests/integration/test_vmid_reservation.py -x` | ❌ Wave 0 |
| CAP-01 | Create refused at node RAM > 0.80 | unit | `pytest tests/unit/test_capacity_guard.py -x` | ❌ Wave 0 |
| WS-01/04/05/06/07/08/11 | Full `/api/v1/workspaces` CRUD + stop/start/destroy/events over real SQLite | integration | `pytest tests/integration/test_workspaces_api.py -x` | ❌ Wave 0 |
| PLAT-03 | `/health` reports db + compute; degraded not 500 | integration | `pytest tests/integration/test_health.py -x` | ❌ Wave 0 |
| PLAT-05 | Security headers present on every response; CORS non-`*` | integration | `pytest tests/integration/test_security_headers.py -x` | ❌ Wave 0 |
| WORK-03 | Bootconfig: in-pool vmid → non-secret payload; out-of-pool → 404; no cred in logs | integration | `pytest tests/integration/test_bootconfig.py -x` | ❌ Wave 0 |
| WS-02 (real-infra) | Real clone/start UPID + static IP + real ttyd | manual (homelab) | dev-homelab five-step smoke (PRIMING.md STEP 4) | ❌ deferred |

### Sampling Rate
- **Per task commit:** `cd api && uv run pytest tests/unit -x -q` (sub-second feedback).
- **Per wave merge:** `cd api && uv run pytest -q` (unit + integration; real SQLite + mocks).
- **Phase gate:** full suite green + ruff + ruff format + mypy --strict + `uv lock --check` + reuse lint before `/gsd:verify-work`. Real-Proxmox acceptance is the homelab smoke gate (out of CI, by design).

### Wave 0 Gaps
- [ ] `tests/unit/test_create_saga.py` — WS-02 happy path over Fake
- [ ] `tests/unit/test_compensation.py` — WS-03 per-step `FakeFailures`
- [ ] `tests/unit/test_state_machine.py` — WS-09 transition table
- [ ] `tests/unit/test_capacity_guard.py` — CAP-01
- [ ] `tests/integration/test_vmid_reservation.py` — WS-10 partial-unique-index (real SQLite)
- [ ] `tests/integration/test_workspaces_api.py` — full CRUD via ASGITransport
- [ ] `tests/integration/test_health.py` — PLAT-03
- [ ] `tests/integration/test_security_headers.py` — PLAT-05
- [ ] `tests/integration/test_bootconfig.py` — WORK-03 incl. no-secret-in-logs assertion
- [ ] `tests/integration/test_proxmox_provider.py` — UPID-block + net0 + mem via `responses` (requests-mock)
- [ ] `tests/integration/conftest.py` — ASGITransport client fixture + temp-SQLite + stub-ttyd fixture
- [ ] Framework: extend `[tool.pytest.ini_options]` (existing Phase-0 unit substrate covers the base)

## Security Domain

> `security_enforcement = true`, ASVS L1, block_on=high — section required.

### Applicable ASVS Categories (L1, scoped to this phase's surfaces)

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | v1 is **LAN-only, no auth by design** (tech-spec §13, CLAUDE.md). Do NOT add auth assumptions into v1 paths. The LAN boundary is the precondition (Pitfall 12). |
| V3 Session Management | no | No sessions in v1 (no auth). |
| V4 Access Control | partial | Bootconfig: `vmid ∈ [pool_start, pool_end]` gate; optional source-IP-binding (`request.client.host == getIp(vmid)`) as defense-in-depth, not auth. |
| V5 Input Validation | yes | Pydantic `WorkspaceCreate` validation; `vmid` is `int` path-param (FastAPI rejects non-int); reject out-of-pool vmid without enumeration-aiding errors; parameterized SQL only (already the SqliteProvider pattern). |
| V6 Cryptography | partial | CA-pinned TLS to Proxmox (`verify_ssl=<ca_path>`, never `False`). No hand-rolled crypto. Git credential issuance must be short-lived (ADR-0002). |
| V7 Error/Logging | yes | Structured JSON logs with **no secrets** (git cred, Proxmox token, repo-embedded tokens redacted from logs + event `data`); envelope `error.message` carries no internals. gitleaks backstop (CICD). |
| V13 API/Web Service | yes | `/api/v1` versioned surface; standard envelope; security headers; non-`*` CORS; the internal bootconfig endpoint is the one non-CRUD surface and carries the threat model above. |

### Known Threat Patterns for FastAPI + Proxmox control plane

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection in workspace/event queries | Tampering | Parameterized queries only (SqliteProvider already uses `?`/named params) — keep it. |
| Over-privileged Proxmox token (root@pam / cluster-wide) | Elevation of Privilege | `BurrowProvisioner` 9-priv role scoped to `/pool/burrow-workers` + storage + node, granted to user∩token (ADR-0003, Phase-0 host-prime). Token in gitignored `.env` only. |
| `verify_ssl=False` (MITM the Proxmox channel) | Spoofing/Info Disclosure | CA-pinned TLS via `proxmox_ca_cert_path` — enforced by the Phase-0 skeleton. |
| Git credential / Proxmox token in logs or event `data` | Information Disclosure | Redact; log non-secret fields only; gitleaks CI gate; never persist the bootconfig cred to worker env (ADR-0002). |
| Bootconfig VMID enumeration / out-of-pool probe | Information Disclosure | Validate `vmid ∈ pool`; 404 without echoing the probed value; optional source-IP binding. |
| Capacity exhaustion / DoS by mass-create (no auth) | Denial of Service | Capacity guard (node RAM > 0.80 → refuse, CAP-01) caps node overcommit; the bounded VMID pool caps fleet size; the LAN boundary is the trust precondition. Note as a v1 accepted-risk (no rate-limit in no-auth v1). |
| `ALLOWED_ORIGINS=*` / missing headers | Tampering | Non-`*` CORS (LAN origin from `Settings`) + SecurityHeaders middleware on every response (PLAT-05, Pitfall 12). |

**ASVS scoping note:** Because v1 is deliberately no-auth/LAN-only, V2/V3 do not apply and **must not** be retro-fitted into v1 code (auth is the additive hosted path). The L1 effort concentrates on V5 (input validation), V7 (no secrets in logs), and the bootconfig endpoint's V4/V13 surface. block_on=high: the secrets-in-logs and `verify_ssl=False` items are the high-severity gates to verify.

## Sources

### Primary (HIGH confidence)
- `proxmoxer` Tasks docs — `Tasks.blocking_status(prox, task_id, timeout=300, polling_interval=0.01)` → dict with `exitstatus`; `'OK'` on success, `None` on timeout. https://proxmoxer.github.io/docs/latest/tools/tasks/ (verified 2026-06-10)
- `proxmoxer` basic usage — `ProxmoxAPI(host, user, token_name, token_value, verify_ssl=<ca_path>)`; method-chaining (`nodes(n).lxc(v).clone.post(...)`, `.config.put(net0=...)`, `.status.start.post()`, `.delete()`, `cluster.nextid.get()`); POST returns the UPID. https://proxmoxer.github.io/docs/latest/basic_usage/ (verified 2026-06-10)
- PyPI version checks (2026-06-10): proxmoxer 2.3.0, respx 0.23.1, httpx 0.28.1, aiosqlite 0.22.1, fastapi 0.136.3 — all current stable.
- Frozen Phase-0 contracts (read 2026-06-10): `api/compute/provider.py`, `fakeProvider.py`, `proxmoxProvider.py` (skeleton), `api/db/provider.py`, `sqliteProvider.py`, `migrations/001_init.sql`, `api/models/*`, `api/config.py`, `api/main.py`, `api/lib/envelope.py`.
- ADRs: ADR-0002 (pull-at-boot), ADR-0003 (ACL scoping → clone adds VMID to pool), ADR-0004 (static-IP-from-VMID), ADR-0005 (`--full` clone). `docs/adr/`.
- `.planning/research/{SUMMARY,ARCHITECTURE,PITFALLS,STACK,PROXMOX-PRIMING}.md` (SC-1..SC-13, saga + compensation, 15 pitfalls, version pins, host-prime facts).
- `docs/ci-cd-and-testing.md` §4.2–4.6 (test tiers: real SQLite, mocked Proxmox, stub ttyd, FakeComputeProvider e2e).

### Secondary (MEDIUM confidence)
- proxmoxer is `requests`-based and synchronous; `verify_ssl` forwards to `requests` `verify` (accepts a CA path). https://github.com/proxmoxer/proxmoxer , https://github.com/proxmoxer/proxmoxer/issues/65
- Proxmox `GET /nodes/{node}/status` returns `mem`/`maxmem` (bytes); fraction = mem/maxmem. https://pve.proxmox.com/wiki/Proxmox_VE_API
- FastAPI security headers via `BaseHTTPMiddleware`; CORS must be outermost and non-`*`. https://fastapi.tiangolo.com/advanced/middleware/ , https://github.com/fastapi/fastapi/discussions/8548
- Structured logging: stdlib JSON formatter vs structlog tradeoffs. https://apitally.io/blog/fastapi-logging-guide

### Tertiary (LOW confidence)
- None load-bearing. The git-credential issuance mechanism (A3) is explicitly an operator decision, not asserted as a verified pattern.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new deps; all versions re-verified on PyPI; APIs confirmed against proxmoxer docs.
- Architecture (saga / state machine / VMID reservation): HIGH — directly encoded by the frozen ABC + SC-1..SC-12 + four ADRs; the Fake provider's failure-injection hook is purpose-built for the compensation tests.
- Pitfalls: HIGH — Proxmox UPID/VMID semantics, the proxmoxer-sync-in-async hazard, and the respx-vs-responses transport split are all verified.
- Bootconfig credential mechanism: MEDIUM — contract shape is locked (ADR-0002); the concrete issuer needs operator confirmation (A3).

**Research date:** 2026-06-10
**Valid until:** 2026-07-10 (stable stack; proxmoxer/FastAPI move slowly — 30 days)
