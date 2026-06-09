<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Architecture Research

**Domain:** Self-hosted control plane for ephemeral Claude Code worker LXCs (FastAPI + SQLite + Proxmox + WebSocket terminal proxy)
**Researched:** 2026-06-09
**Confidence:** HIGH (validated against tech-spec, CI/CD spec, PROJECT.md, and current Proxmox / proxmoxer / ttyd / FastAPI sources)

> **Scope note.** This is a *validation and deepening* pass on `docs/tech-spec.md`, not a redesign.
> The spec's component split, provider seams, and create-saga are sound. This document confirms
> the boundaries, fills in the failure/compensation paths the spec leaves implicit, and flags
> three places where the spec's happy-path pseudocode collides with how Proxmox LXC actually
> behaves (cloud-init, DHCP IP discovery, ttyd subprotocol framing). Those are called out as
> **SPEC GAP** and need an ADR or open-item resolution before the relevant phase.

---

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Browser (any device on the LAN)                                          │
│  React 19 UI · xterm.js · react-mosaic · TanStack Query · Zustand         │
└───────────────┬──────────────────────────────────┬───────────────────────┘
                │ HTTP /api, /                      │ WS /ws/.../terminal
                ▼                                   ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  nginx (control-plane host, :80)   — pure reverse proxy / static server   │
│   /        → /opt/burrow/ui/dist (Vite static build, SPA fallback)        │
│   /api/    → 127.0.0.1:8000  (FastAPI)                                     │
│   /ws/     → 127.0.0.1:8000  (Upgrade + Connection:upgrade, 3600s timeout)│
└───────────────┬──────────────────────────────────────────────────────────┘
                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  FastAPI control plane (uvicorn :8000)                                    │
│  ┌────────────────────────┐  ┌──────────────────────────────────────────┐ │
│  │ routers/               │  │ services/                                 │ │
│  │  workspaces.py (CRUD)  │─▶│  WorkspaceService  (saga orchestrator)    │ │
│  │  terminal.py   (WS)    │  │     │  depends only on abstractions       │ │
│  │  health.py             │  │     ├─▶ ComputeProvider (abstract)        │ │
│  └────────────────────────┘  │     │     └─ ProxmoxComputeProvider       │ │
│                              │     │         (proxmoxer)        ─────────┼─┼──▶ Proxmox API
│                              │     └─▶ DbProvider (abstract)             │ │   (clone/start/
│                              │           └─ SqliteProvider (aiosqlite) ─┼─┼──▶ SQLite /data/
│                              │           └─ PostgresProvider (stub)      │ │    burrow.db
│                              └──────────────────────────────────────────┘ │
│   terminal.py WS proxy ───────────────────────────────────────────────────┼──▶ ttyd :7681
└──────────────────────────────────────────────────────────────────────────┘    (per worker,
                                                                                  bound to the
                                                                                  worker's IP)
                ┌──────────────────────────────────────────────┐
                │  Worker LXCs (VMID pool, ephemeral)           │
                │  cloned from golden template (e.g. VMID 9000) │
                │   Ubuntu 24.04 · Node 22 · claude-code        │
                │   burrow-worker.service → burrow-boot.sh      │
                │   ttyd :7681  →  (rtk) claude                 │
                └──────────────────────────────────────────────┘
```

The control plane is a **modular monolith**: one FastAPI process, clear internal seams, no
network hops between layers except the two real external systems (Proxmox API, worker ttyd).
For a single-operator homelab this is correct: KISS, no message bus, no extra services to run.

### Component Responsibilities

| Component | Owns / Responsible for | May know about | Must NOT know about |
|-----------|------------------------|----------------|---------------------|
| **nginx** | TLS-less LAN entry, static UI, reverse-proxy `/api` + `/ws` (WS upgrade, long read timeout), security headers | Upstream is `127.0.0.1:8000`; the `/ws` upgrade dance | Workspaces, Proxmox, the DB — it is dumb plumbing |
| **routers/workspaces.py** | HTTP shape: parse/validate `WorkspaceCreate`, wrap responses in `data`/`meta`/`error`, map exceptions → error codes/status | `WorkspaceService`, Pydantic models | Proxmox/proxmoxer, SQL, VMID math — never imports a provider impl |
| **routers/terminal.py** | WS lifecycle, the browser↔ttyd bidirectional bridge, connect/disconnect events, error frames | `DbProvider` (lookup workspace + log events), `websockets` client | How the LXC was created; capacity logic |
| **routers/health.py** | Liveness + dependency probe (`db: ok`, `proxmox: ok`) | Both providers' health calls | Business rules |
| **WorkspaceService** | The **create/stop/start/destroy sagas**, state-machine enforcement, capacity guard, VMID allocation policy, userdata assembly, compensation/cleanup | `ComputeProvider` + `DbProvider` **abstractions only** | `proxmoxer` types, `aiosqlite`, SQL strings, ttyd framing |
| **ComputeProvider** (abstract) | The compute contract: `clone / start / stop / destroy / status / getIp / nextVmId / nodeMemoryUsage / injectBootConfig` | Nothing above it | Workspaces, DB rows, HTTP |
| **ProxmoxComputeProvider** | proxmoxer calls, **UPID task waiting**, IP discovery, capacity query, env injection mechanism | Proxmox cluster topology, proxmoxer | Workspace semantics, event log, HTTP envelope |
| **DbProvider** (abstract) | Persistence contract: workspace CRUD, soft-delete, `logEvent` | Nothing above it | Proxmox, HTTP, compute |
| **SqliteProvider** | `aiosqlite`, migrations, snake_case↔camelCase mapping, soft-delete filtering | SQLite/SQL | Proxmox, HTTP |
| **templateService** | Read template registry (`templates` table), resolve `pluginSet`→template VMID | DbProvider, settings | Cloning mechanics (that's compute) |

**The load-bearing rule (from CLAUDE.md + PROJECT.md):** `WorkspaceService` imports *only*
`ComputeProvider` and `DbProvider`. Grep test for the seam: `proxmoxer`, `aiosqlite`, `httpx`,
and `ProxmoxAPI` must appear **only** under `api/db/` and `api/services/proxmox*` / the provider
impls — never in `workspaceService.py`, routers, or models. See "Provider Seam Leakage Audit".

---

## Recommended Project Structure

The spec's §4.1 tree is good. One **adjustment for the seam** and the test seams:

```
api/
├── main.py                      # app factory: DI wiring, middleware, envelope, security headers
├── config.py                    # pydantic-settings (env)
├── routers/
│   ├── workspaces.py            # /api/v1/workspaces CRUD  (HTTP only)
│   ├── terminal.py              # /ws/workspaces/{id}/terminal  (WS bridge)
│   └── health.py
├── services/
│   ├── workspaceService.py      # saga orchestrator — abstractions ONLY
│   └── templateService.py       # template registry resolution
├── compute/                     # NEW: lift compute behind a named seam (mirrors db/)
│   ├── provider.py              # ComputeProvider ABC   (was implied by spec §3.2)
│   ├── proxmoxProvider.py       # proxmoxer impl  (was services/proxmoxService.py)
│   └── fakeProvider.py          # FakeComputeProvider — in-memory, for e2e (ci-cd §4.4)
├── db/
│   ├── provider.py              # DbProvider ABC
│   ├── sqliteProvider.py
│   ├── postgresProvider.py      # stub behind the seam
│   └── migrations/001_init.sql
├── models/                      # Pydantic: snake_case DB ↔ camelCase JSON
│   ├── workspace.py
│   └── event.py
└── tests/
    ├── unit/                    # Tier 1: service logic, doubles for both providers
    └── integration/            # Tier 2: real SQLite, mocked Proxmox HTTP, stub ttyd
```

### Structure Rationale

- **`compute/` as a sibling of `db/`** (vs the spec's `services/proxmoxService.py`): the spec
  *names* a `ComputeProvider` seam (§3.2) but its code sketch instantiates `ProxmoxService`
  directly inside `WorkspaceService`. Promoting compute to a first-class provider package — ABC +
  `proxmoxProvider` + `fakeProvider` — makes the seam symmetric with the DB seam and gives the
  e2e tier its `FakeComputeProvider` a natural home. This is the single most important structural
  change to keep the spec's own promise ("compute is the only swappable seam besides the DB").
- **`fakeProvider.py` lives in app code, not tests**, because ci-cd §4.4 wires it into the
  *shipped* app via `docker-compose.e2e.yml` (selected by env, e.g. `BURROW_COMPUTE=fake`). It is
  a real implementation of the contract, just in-memory.
- **routers thin, services thick**: routers do envelope/validation only so the state machine and
  saga live in one testable place (Tier-1 covers it with no network).

---

## Architectural Patterns

### Pattern 1: Orchestration Saga with Explicit Compensation

**What:** `createWorkspace` is a multi-step distributed transaction across two external systems
(Proxmox + DB) with no shared rollback. Model it as a saga: each forward step has a known
compensating action, and a failure at step *N* runs compensations for steps *N..1* in reverse.

**When to use:** Any time you mutate Proxmox state and DB state in the same operation. All four
lifecycle operations (create/start/stop/destroy) are sagas; create is the dangerous one.

**Trade-offs:** More code than a happy-path `try/except`, but it is the difference between
"failed create leaves an orphaned VMID burning RAM and a phantom DB row" and "failed create
leaves the system exactly as it was." For a homelab with a finite VMID pool, leaks are fatal
over time.

**Canonical create saga (validated + corrected):**

```
STEP                              FORWARD                          COMPENSATION (on later failure)
0  capacity guard      nodeMemoryUsage(node) ≤ 0.80          (none — read only)
1  allocate VMID       nextVmId() → reserve                  release reservation
2  DB pending row      createWorkspace(status=creating)      mark status=error (NOT delete — keep audit)
3  clone template      clone(tmpl→vmid) + WAIT UPID OK       destroy(vmid)  [partial-clone teardown]
4  inject boot env     injectBootConfig(vmid, userdata)      (covered by step-3 destroy)
5  start LXC           start(vmid) + WAIT UPID OK            stop(vmid) then destroy(vmid)
6  resolve IP          waitForIp(vmid) → lxcIp               stop+destroy(vmid)
7  health: ttyd up     waitForTtyd(lxcIp:7681)               stop+destroy(vmid)
8  mark running        updateWorkspace(status=running)       —
```

Two ordering corrections vs the spec's §6.2 sketch:

1. **Write the DB `creating` row BEFORE the clone (step 2 before 3), and persist the VMID on it
   immediately.** The spec clones first (step 3) then writes the row (step 5). If the process
   crashes between clone and row-write, the VMID is orphaned with *no DB record to find it by* —
   unrecoverable without a Proxmox-side sweep. Recording the reserved VMID first makes every
   subsequent failure recoverable by a reaper that reads `status=creating/error` rows.
2. **Every Proxmox mutation must wait on its UPID task** (`Tasks.blocking_status` /
   `nodes(node).tasks(upid).status` until `status==stopped && exitstatus==OK`). The spec's
   `cloneLxc`/`startLxc` return a task id but the saga treats them as synchronous. Clone of a 30 GB
   rootfs is *not* instant; starting `start` or `getIp` before clone completes will fail. Wrap each
   compute mutation so the provider blocks until the task resolves (with its own timeout) and
   raises a typed error on non-OK exit. (HIGH confidence — `proxmoxer.tools.Tasks.blocking_status`.)

### Pattern 2: Idempotency + Reservation for VMID Allocation

**What:** `nextVmId()` scanning the pool for the first free id is a **TOCTOU race** under any
concurrency (two creates pick the same id) and leaks ids on crash. Make allocation safe by:
(a) a process-level `asyncio.Lock` around allocate+clone-submit so two in-flight creates can't pick
the same id, and (b) treating the DB `creating` row as the reservation record so a crashed create
is visible.

**When to use:** Always — even single-operator UIs fire parallel creates (double-click, two tabs).

**Idempotency key:** Accept an optional client-supplied `idempotencyKey` on `POST /workspaces`;
if a row with that key exists, return it instead of cloning again. Cheap insurance against
retried POSTs creating duplicate LXCs.

```python
async with self._allocLock:                  # serialize the racy window only
    used = {w.vmid for w in await self.db.listWorkspaces()}      # DB-side reservations
    used |= set(self.compute.usedVmIds())                       # Proxmox-side truth
    vmid = next(i for i in range(POOL_START, POOL_END + 1) if i not in used)
    ws = await self.db.createWorkspace({...vmid, "status": "creating"})  # reserve in DB
# lock released — slow clone runs outside the critical section
```

Union the DB's known VMIDs with Proxmox's actual VMIDs so a row the reaper hasn't cleaned yet
*and* a Proxmox leak both count as "used." Single source of truth at allocation time = the
intersection of both systems, biased toward "occupied."

### Pattern 3: Provider Seam (Dependency Inversion) via FastAPI DI

**What:** `WorkspaceService(compute: ComputeProvider, db: DbProvider)` — constructor injection of
abstractions; concrete impls chosen once at app startup from env and provided via FastAPI
`Depends`. Swapping SQLite→Postgres or Proxmox→Fake is a one-line wiring change, never a service
edit.

**When to use:** This is the spec's central architectural promise (additive hosted path). It is
also what makes CI hermetic — see "Integration Points."

**Trade-offs:** Two extra ABCs and a DI module. Worth it: the e2e tier *depends* on being able to
substitute `FakeComputeProvider`, and the whole "hosted path is additive not a rewrite" claim
rests on nothing Proxmox/SQLite-specific leaking past these two interfaces.

```python
# main.py — wiring (the ONLY place impls are named)
def getCompute() -> ComputeProvider:
    return FakeComputeProvider() if settings.compute == "fake" else ProxmoxComputeProvider(settings)
def getDb() -> DbProvider:
    return PostgresProvider(settings) if settings.dbKind == "postgres" else SqliteProvider(settings)
```

### Pattern 4: Bidirectional WebSocket Bridge with Subprotocol Pass-Through

**What:** `terminal.py` accepts the browser WS, dials the worker's ttyd WS, and pumps frames both
ways with two coroutines under `asyncio.gather`, cancelling both when either side closes.

**Critical correction (SPEC GAP):** ttyd speaks a **custom `tty` WebSocket subprotocol**, not raw
bytes. The client must offer `Sec-WebSocket-Protocol: tty`; the first client→server frame is a
JSON `{"AuthToken": "..."}` (the browser's xterm sends this), and thereafter frames are
**opcode-prefixed** (`'0'`=input, `'1'`/`'2'`=resize JSON, server→client `'0'`=output,
`'1'`=set-title, `'2'`=set-prefs). The proxy must therefore:

- request the `tty` subprotocol on the upstream `websockets.connect(..., subprotocols=["tty"])`,
- bridge frames **opaquely** (do not parse or re-encode opcodes — pass the raw frame through),
- preserve **frame type** (binary stays binary, text stays text). The spec's `ttydToClient`
  does `msg.encode()` on text frames, silently turning a ttyd text control frame into a binary
  one. Bridge `str`→`send_text` and `bytes`→`send_bytes` to keep the subprotocol intact.

**Lifecycle + failure frames:**

| Event | Action |
|-------|--------|
| workspace not found / not `running` | `close(1008)` before accept (policy violation) |
| upstream ttyd unreachable | accept, then `send_json({"type":"error","code":"LXC_NOT_READY"})`, internal reconnect (3× / 2s) per spec §5.2, then `close` |
| browser closes | cancel ttyd→client pump, close upstream, `logEvent(terminal.disconnected)` |
| ttyd closes (e.g. `--once` after detach) | cancel client→ttyd pump, `logEvent(terminal.disconnected)`, close browser WS with normal code |
| mid-stream upstream drop | attempt internal reconnect; on exhaustion emit error frame + close |

```python
async with websockets.connect(ttydUrl, subprotocols=["tty"]) as ttyd:
    await db.logEvent(workspaceId, "terminal.connected", {})
    async def up():    # browser → ttyd
        async for m in ws.iter_bytes(): await ttyd.send(m)
    async def down():  # ttyd → browser, preserve frame type
        async for m in ttyd:
            await (ws.send_text(m) if isinstance(m, str) else ws.send_bytes(m))
    done, pending = await asyncio.wait(
        {asyncio.create_task(up()), asyncio.create_task(down())},
        return_when=asyncio.FIRST_COMPLETED)
    for t in pending: t.cancel()      # one side closed → tear the other down
```

`asyncio.wait(FIRST_COMPLETED)` + cancel is safer than the spec's bare `gather`: `gather`
keeps both coroutines alive until *both* finish, so a dead browser leaves the ttyd pump hanging.

---

## Data Flow

### Create-Workspace Flow (happy path)

```
NewWorkspaceModal ──POST /api/v1/workspaces──▶ workspaces.py ──▶ WorkspaceService.create
                                                                        │
   capacity guard ─▶ allocate VMID (locked) ─▶ DB row(creating) ◀───────┘
        │                                           │
   clone(WAIT UPID) ─▶ injectBootConfig ─▶ start(WAIT UPID) ─▶ waitForIp ─▶ waitForTtyd
        │                                                                        │
        └──────────────────────────────── DB row(running) ◀─────────────────────┘
                                                │
UI: TanStack Query poll list  ◀── status: creating → running
   then layoutStore.openPanel(id) ─▶ TerminalPanel ─▶ WS /ws/workspaces/{id}/terminal
```

The create POST is **long-running** (clone + boot + health can be 30–90 s). Two valid shapes:
- **Synchronous POST** (spec's choice): the request blocks until `running`/`error`. Simple; the
  modal shows progress text. Needs an nginx/uvicorn read timeout > worst-case boot and a server
  timeout that triggers compensation. Acceptable for single-operator.
- **Async POST + poll** (recommended if boot times grow): POST returns `202` with the `creating`
  row immediately; the saga runs in a background task; the UI polls `GET /workspaces/{id}` for
  status. Decouples HTTP timeout from boot time and survives a closed modal. Either works behind
  the same envelope; pick synchronous for v1, note the migration path.

### Terminal Stream Flow

```
xterm.js ─bytes─▶ browser WS ─▶ nginx (/ws upgrade) ─▶ terminal.py ─frame─▶ ttyd:7681 ─▶ (rtk) claude
   ▲                                                        │
   └──────────────── output frames (preserve text/binary) ◀─┘
```

### State Management (UI)

```
TanStack Query (server state: workspace list/status, events)   ── polling, cache, mutations
Zustand layoutStore (client state: mosaic tree, activeWorkspaceId)  ── panel layout only
```

Keep server truth in TanStack Query, view-only layout in Zustand. Do not mirror workspace status
into Zustand — it drifts.

### Boot-Config Injection (SPEC GAP — mechanism must change for LXC)

The spec's `setCloudInitUserdata` assumes cloud-init userdata injection. **Proxmox LXC has no
native cloud-init** (`cicustom` is QEMU/VM-only; PVE cloud-init manipulation is unavailable for
containers — HIGH confidence). The env vars `burrow-boot.sh` reads (`CONFIG_REPO`, `PROJECT_REPO`,
etc.) must reach the worker by a container-valid mechanism. Options, recommendation first:

1. **`pct exec` to write `/etc/burrow/worker.env` after clone, before start** (or write to the
   container rootfs path on the host while stopped). `burrow-worker.service` does
   `EnvironmentFile=/etc/burrow/worker.env`. Simple, no template surgery. *Recommended.*
2. **`pct push` a generated env file** into the stopped container's filesystem.
3. **Per-VMID hookscript** (`pct set --hookscript`) that materializes env at `pre-start`.

The `ComputeProvider` contract should expose `injectBootConfig(vmid, env: dict)` and hide which
mechanism is used. This keeps `WorkspaceService` honest (it just calls `injectBootConfig`) and
lets the Fake provider no-op it. **Action: resolve with an ADR before Phase 1; it changes the
`ProxmoxComputeProvider` surface, not the saga.**

---

## Scaling Considerations

This is a single-operator homelab tool; "scale" = concurrent workspaces on finite homelab RAM,
not user count.

| Scale | Architecture posture |
|-------|----------------------|
| 1–10 workspaces (target) | Monolith FastAPI, SQLite, sync POST. No changes needed. The capacity guard (node RAM > 80% → refuse) is the real limiter, not software. |
| 10–30 workspaces | Move create to async POST + background task (timeouts decouple from boot). Add a periodic **reaper** for orphaned `creating`/`error` rows and Proxmox VMIDs with no DB row. Watch SQLite write contention on the event log (batch / WAL mode). |
| Multi-node / multi-user (hosted path) | The provider seams pay off: Postgres `DbProvider` + RLS, `ComputeProvider` for containers/serverless, auth middleware. Additive per spec §13 — no v1 rewrite. |

### Scaling Priorities

1. **First bottleneck: host RAM, not code.** Each worker reserves ~4 GB. The capacity guard is
   load-bearing; make it per-target-node and honest (read live `nodeMemoryUsage`).
2. **Second: orphaned-resource accumulation.** Without a reaper, every failed/crashed create
   slowly exhausts the VMID pool and RAM. The reaper (Phase 4 / hardening) is not optional at
   any real usage.
3. **Third: SQLite event-log writes** under many simultaneous terminals logging connect/disconnect
   churn. Enable WAL, keep events append-only, index `workspaceId`.

---

## Anti-Patterns

### Anti-Pattern 1: Leaking proxmoxer/aiosqlite types past the seam

**What people do:** Return raw proxmoxer dicts or `aiosqlite.Row` objects up into
`WorkspaceService`/routers; pass a `ProxmoxAPI` handle around.
**Why it's wrong:** It silently couples business logic to Proxmox/SQLite and breaks the "hosted
path is additive" promise — the Fake/Postgres providers can't satisfy a leaked concrete type, so
e2e and the hosted path both die.
**Do this instead:** Providers return **Pydantic models / plain typed dataclasses only**. The grep
audit below is a CI-able guard.

### Anti-Pattern 2: Happy-path saga with a bare try/except

**What people do:** Clone → start → poll, wrapped in one `try`, and on error just set
`status=error` and return.
**Why it's wrong:** The half-built LXC keeps running, holding RAM and a VMID forever. Over a week
of homelab use the pool fills and creates start failing with "no free VMID" for no visible reason.
**Do this instead:** Per-step compensation (Pattern 1). On any failure after clone, run
stop+destroy for the VMID; mark the row `error` (keep it for audit), never silently drop it.

### Anti-Pattern 3: Treating Proxmox mutations as synchronous

**What people do:** Call `clone` then immediately `start`/`getIp`.
**Why it's wrong:** Clone/start return a UPID *task*; the operation is still running. The next call
races a not-yet-cloned container and fails intermittently — the worst kind of bug.
**Do this instead:** Block on the UPID (`Tasks.blocking_status`, `exitstatus==OK`) inside the
provider before returning. Surface task failure as a typed `ComputeError`.

### Anti-Pattern 4: Parsing/normalizing ttyd frames in the proxy

**What people do:** Decode ttyd opcodes, re-encode, or coerce text→bytes in the bridge.
**Why it's wrong:** ttyd's `tty` subprotocol is opcode-framed; re-encoding corrupts resize/title
control frames and can desync the terminal. The spec's `msg.encode()` on text frames is exactly
this bug.
**Do this instead:** Negotiate `subprotocols=["tty"]` upstream and pass frames through opaquely,
preserving text-vs-binary type.

### Anti-Pattern 5: DHCP + API IP discovery for unprivileged LXC

**What people do:** Boot the worker on DHCP and poll `GET /nodes/{node}/lxc/{vmid}/interfaces`
for the address (the spec's `getLxcIp`).
**Why it's wrong:** Unprivileged LXC has no guest agent, and the interfaces endpoint is
unreliable/empty for DHCP-assigned addresses (well-documented limitation). `getLxcIp` can hang or
return nothing, stalling the saga at step 6.
**Do this instead (recommended, matches spec Appendix B.1):** **Static IP pool aligned to the VMID
range** (VMID 2xx → `10.a.b.2xx`). The control plane *computes* the IP from the VMID — no polling,
no agent, deterministic, and the nginx/WS upstream is known before the container even boots. Set
the static address at clone via `pct set net0 ip=.../...,gw=...`. Promote this from "open question"
to a decided ADR.

---

## Integration Points

### External Services

| Service | Integration Pattern | Gotchas (verified) |
|---------|---------------------|--------------------|
| **Proxmox API** | `proxmoxer` (HTTPS, API token `burrow@pve`, least-priv, `verify_ssl` per env) behind `ProxmoxComputeProvider` | Mutations are async UPID tasks — must wait. No LXC cloud-init. DHCP IP discovery unreliable. CT-template clone defaults to *linked* clone (shares base disk) — for ephemeral independent workers use `--full` so destroy fully frees space. |
| **Worker ttyd** | `websockets` client WS, `subprotocol=tty`, bound to worker IP:7681 | Opcode-framed subprotocol; first client frame is `{AuthToken}`; preserve frame types. `--once` exits ttyd on client disconnect → "close tab kills session" (open question §B.2: decide detach vs terminate). |
| **cc-worker-config repo** | git clone at worker boot (`burrow-boot.sh`), not a control-plane dependency | Needs git auth in the worker (deploy key/token via injected env). Boot-time pull = always-latest but non-reproducible (open question §B.4). |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| router ↔ WorkspaceService | direct async calls, Pydantic in/out | routers never touch providers |
| WorkspaceService ↔ ComputeProvider | abstract method calls | the swap seam; Fake plugs in here for e2e |
| WorkspaceService ↔ DbProvider | abstract method calls | the swap seam; SQLite now, Postgres later |
| terminal.py ↔ DbProvider | lookup + `logEvent` | WS router reads workspace.lxcIp/status, logs events |
| terminal.py ↔ ttyd | `websockets` client | the only place that knows the ttyd wire format |

### Provider Seam Leakage Audit (CI-able)

A passing seam means these symbols appear **only** in the listed files:

| Symbol | Allowed ONLY in | Red flag if found in |
|--------|-----------------|----------------------|
| `proxmoxer`, `ProxmoxAPI`, `Tasks.blocking_status` | `api/compute/proxmoxProvider.py` | `workspaceService.py`, any router, `models/` |
| `aiosqlite`, raw SQL strings | `api/db/sqliteProvider.py`, `migrations/` | services, routers, models |
| `websockets`, ttyd opcodes | `api/routers/terminal.py` | services |
| `httpx` (ttyd health) | provider impls only | `workspaceService.py` business logic |

Add a lint/test that greps for these (cheap, deterministic, catches the most likely regression).

---

## Build Order / Dependency Graph

The spec's Phase 0–4 ordering is sound. This refines it into a dependency-aware build order with
the **seams that unblock hermetic CI** called out. The key insight: **build both provider
abstractions and the Fake/stub seams first**, so every later layer is testable without Proxmox.

```
                    ┌──────────────────────────────────────────────┐
                    │ 0. Contracts + seams (UNBLOCKS EVERYTHING)    │
                    │   models (Workspace/Event), DbProvider ABC,   │
                    │   ComputeProvider ABC, FakeComputeProvider,   │
                    │   response envelope, config, app factory      │
                    └───────────────┬──────────────────────────────┘
            ┌───────────────────────┼───────────────────────────────┐
            ▼                       ▼                                ▼
  ┌───────────────────┐   ┌──────────────────────┐      ┌────────────────────────┐
  │ 1. DB layer       │   │ 2. WorkspaceService   │      │ 3. WS terminal proxy   │
  │  SqliteProvider   │   │  saga + state machine │      │  bridge + stub ttyd    │
  │  migrations       │──▶│  capacity, VMID alloc │      │  (echo WS) for tests   │
  │  (real, Tier-2)   │   │  compensation paths   │      │                        │
  └───────────────────┘   │  (Fake compute → Tier1│      └───────────┬────────────┘
                          │   + Tier2, NO Proxmox)│                  │
                          └───────────┬───────────┘                  │
                                      ▼                              │
                          ┌───────────────────────┐                 │
                          │ 4. HTTP routers + envelope, /health     │
                          │    full /api/v1 CRUD over Fake compute  │◀┘
                          └───────────┬───────────┘
                                      ▼
                          ┌───────────────────────┐    ── everything above is HERMETIC ──
                          │ 5. ProxmoxComputeProvider (real proxmoxer)             │
                          │    UPID waits, static-IP set, injectBootConfig,        │
                          │    capacity query  — validated in DEV env, mocked in CI│
                          └───────────┬───────────┘
                                      ▼
                          ┌───────────────────────┐
                          │ 6. React UI: layoutStore → WorkspaceList → TerminalPanel
                          │    → WorkspaceLayout → NewWorkspaceModal → StatusBar    │
                          │    (MSW-mocked API in Tier-2; Playwright e2e in Tier-3) │
                          └───────────┬───────────┘
                                      ▼
                          ┌───────────────────────┐
                          │ 7. Golden template + burrow-boot.sh (cc-worker-config) │
                          │    + real Proxmox end-to-end (DEV only, never CI)      │
                          └───────────┬───────────┘
                                      ▼
                          ┌───────────────────────┐
                          │ 8. Hardening: reaper, auto-stop idle, restore/reconnect,│
                          │    structured logging, capacity tuning                  │
                          └───────────────────────┘
```

**Where the hermetic-CI seams plug in (ci-cd §4.3–4.4):**
- **`FakeComputeProvider`** substitutes for `ProxmoxComputeProvider` at the `ComputeProvider`
  seam — selected by env (`BURROW_COMPUTE=fake`). It lets steps 2, 4, and the whole e2e tier run
  with **zero Proxmox**. Build it in step 0 alongside the ABC, not later.
- **Stub ttyd** (tiny local WS echo honoring the `tty` subprotocol) substitutes for the worker's
  ttyd at the `terminal.py ↔ ttyd` boundary. It powers Tier-2 WS-proxy tests and the Tier-3 e2e
  "echo terminal." Build it in step 3.
- **Real SQLite** is used as-is in Tier-2 (no stub) — it exercises `DbProvider` + migrations for
  real (ci-cd §4.3).
- **Mocked Proxmox HTTP** (`respx`/`responses`) covers the `ProxmoxComputeProvider` in Tier-2
  without a node; the **real** provider is only exercised in the dev environment (step 7).

**Ordering rationale:**
- **Seams before consumers (0 first):** the entire backend can be built and CI-green before a
  single real Proxmox call exists. This is what makes the "infra dependency" constraint
  (PROJECT.md: control plane can't be booted from a dev workstation) survivable.
- **Service before routers (2 before 4):** the saga/state-machine is the risk; isolate and unit
  test it over the Fake provider before HTTP shape is added.
- **Backend before UI (≤5 before 6):** UI needs the `/api/v1` contract + envelope to mock against
  (MSW) and to e2e against (real api + Fake compute).
- **Real Proxmox + template last (5, 7):** these are the only steps that *need* the homelab and
  can't be CI-verified; defer them so they don't block the testable 80%.

---

## SPEC GAPS — resolve before the relevant phase (surface, don't implement around)

| # | Gap | Spec says | Reality (confidence) | Resolution |
|---|-----|-----------|----------------------|------------|
| 1 | **LXC has no cloud-init** | `setCloudInitUserdata(...)` injects env | `cicustom`/cloud-init is QEMU-only; unavailable for LXC (HIGH) | ADR: `injectBootConfig` via `pct exec`/`pct push` to `/etc/burrow/worker.env`; hide behind ComputeProvider. Phase 1. |
| 2 | **DHCP IP discovery unreliable** | `getLxcIp` polls interfaces API | Unprivileged LXC has no agent; interfaces endpoint flaky for DHCP (HIGH) | ADR: static IP pool computed from VMID, set at clone via `pct set net0`. Promotes Appendix B.1. Phase 1. |
| 3 | **ttyd subprotocol framing** | bridge raw bytes, `msg.encode()` on text | ttyd uses `tty` subprotocol, opcode frames, `{AuthToken}` first frame (HIGH) | Negotiate `subprotocols=["tty"]`, pass frames opaquely, preserve text/binary. Phase 1 (WS proxy). |
| 4 | **Saga ordering + UPID waits** | clone before DB row; mutations treated sync | clone is async UPID task; row-first is recoverable (HIGH) | Write `creating` row + VMID before clone; block on UPID per mutation; per-step compensation. Phase 1. |
| 5 | **Linked vs full clone** | "clone template LXC" (unspecified) | CT-template clone defaults to *linked* (shares base disk) (MEDIUM) | Use `--full` for independent ephemeral workers so destroy frees space; or accept linked + document. Phase 0/1. |
| 6 | **`--once` UX** | ttyd `--once` exits on disconnect | Closing a tab kills the Claude session (HIGH) | Decide detach-vs-terminate (open question §B.2). Affects WS proxy + state machine. Phase 2/4. |
| 7 | **No reaper in v1 phases** | implied by "ephemeral" | Orphaned VMIDs/rows accumulate without one (HIGH) | Add orphan reaper (creating/error rows + Proxmox VMIDs w/o row). Phase 4 hardening. |

---

## Sources

- Burrow `docs/tech-spec.md` (§3 architecture, §5 API, §6 backend, §7 data model, §9 template, §10 control plane, Appendix B) — authoritative internal spec.
- Burrow `docs/ci-cd-and-testing.md` (§4.3–4.4 test tiers, FakeComputeProvider + stub-ttyd seams) — authoritative internal spec.
- Burrow `.planning/PROJECT.md` (provider-seam decisions, constraints, open questions).
- [proxmoxer Tasks tools — `Tasks.blocking_status` (UPID polling, `exitstatus==OK`)](https://proxmoxer.github.io/docs/latest/tools/tasks/) — HIGH.
- [proxmoxer basic usage](https://proxmoxer.github.io/docs/latest/basic_usage/) — HIGH.
- [Proxmox `pct(1)` — clone, `--full`, linked-clone default for CT templates](https://pve.proxmox.com/pve-docs/pct.1.html) — HIGH.
- [Proxmox Cloud-Init Support wiki (cloud-init is QEMU/`qm`-only; not LXC)](https://pve.proxmox.com/wiki/Cloud-Init_Support) — HIGH.
- [Proxmox forum — cloud-init + LXC limitations / workarounds](https://forum.proxmox.com/threads/q-how-best-to-work-with-cloud-init-and-lxc.119126/) — MEDIUM.
- [Telmate proxmox provider issue #1453 — LXC DHCP IP not exposed via interfaces API](https://github.com/Telmate/terraform-provider-proxmox/issues/1453) — MEDIUM (multiple corroborating forum threads).
- [Proxmox forum — access LXC IP programmatically (`pct exec hostname -I` workaround)](https://forum.proxmox.com/threads/access-lxc-ip-programmatically.38050/) — MEDIUM.
- [ttyd protocol.c (opcode framing: input `'0'`, resize, set-title/prefs)](https://github.com/tsl0922/ttyd/blob/main/src/protocol.c) — HIGH.
- [ttyd terminal client (first frame `{AuthToken}`, `tty` subprotocol)](https://github.com/tsl0922/ttyd/blob/main/html/src/components/terminal/index.tsx) — HIGH.
- [ttyd project / docs (Libwebsockets, WS server)](https://github.com/tsl0922/ttyd) — HIGH.
- [FastAPI WebSockets reference (`iter_bytes`/`send_bytes`/`send_text`)](https://fastapi.tiangolo.com/reference/websockets/) — HIGH.

---
*Architecture research for: self-hosted ephemeral Claude Code worker manager (Burrow control plane)*
*Researched: 2026-06-09*
