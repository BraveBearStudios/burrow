<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Burrow — Claude Code Workspace Manager
## Technical Specification v0.1 (Working Draft)

**Status:** Pre-release / greenfield. Self-host v1 target.  
**Stack:** FastAPI (Python 3.12), Vite + React, SQLite (self-host) / Postgres (optional hosted), Proxmox LXC  

---

## 1. Problem Statement

Running multiple Claude Code sessions requires either bogging down local hardware or hand-stitching tmux, SSH, and process managers. No existing open-source tool delivers all three of:

1. Browser-accessible multi-session terminal UI (tabs, side-by-side panels)
2. Ephemeral backend lifecycle management (spin up on demand, destroy when done)
3. Standardized plugin distribution (every workspace gets identical tooling from a single config source)

Existing analogues tend to be either heavyweight cloud-IDE platforms or commercial tools that gate the agent features that matter. Burrow keeps the critical path on infrastructure you fully own and self-host.

---

## 2. Design Principles

1. **Browser-first.** All access via HTTP from any device on the LAN. Zero local resource overhead on the workstation you browse from.
2. **Ephemeral by default.** Workspaces are cloned from a golden template LXC, live while active, gone when destroyed. No snowflake state.
3. **Reproducible.** Every workspace boots from the same plugin manifest + CLAUDE.md pulled fresh from the worker-config repo. Plugin drift is impossible.
4. **Ownable.** No closed or commercial dependency in the critical path. Proxmox (AGPL), FastAPI (MIT), React (MIT), xterm.js (MIT), ttyd (MIT), SQLite (public domain).
5. **Pluggable.** Self-host now; an optional hosted/multi-tenant path is additive, not a rewrite. The database and compute providers are the only swappable seams.

---

## 3. Architecture Overview

### 3.1 Self-host Mode (v1)

Names like `burrow.lan`, `node1`/`node2`, and the VMID ranges below are
illustrative — substitute your own hostnames and topology.

```
Browser (any workstation on the LAN)
  └── http://burrow.lan  (nginx on the control-plane host)
        ├── /            React UI (Vite static build)
        ├── /api/*       FastAPI backend (proxied :8000)
        └── /ws/*        WebSocket terminal proxy (proxied to ttyd in worker LXCs)

Control Plane: a dedicated LXC/host
  ├── FastAPI (uvicorn, :8000)
  │     ├── Workspace CRUD
  │     ├── Proxmox API integration (proxmoxer)
  │     └── WebSocket terminal proxy (per-workspace WS bridge to ttyd)
  ├── Vite build (served by nginx)
  ├── SQLite (/data/burrow.db)
  └── systemd: burrow.service, nginx

Worker LXCs: VMID pool (e.g. 200-299), any Proxmox node, ephemeral
  Each cloned from Template LXC (e.g. VMID 9000)
  ├── Ubuntu 24.04 LTS
  ├── Node.js 22 + @anthropic-ai/claude-code
  ├── plugin set (configurable; see §11)
  ├── CLAUDE.md pulled from the worker-config repo on boot
  ├── Project repo git-cloned on boot
  └── ttyd (:7681, bound localhost, shells into claude)
```

### 3.2 Optional hosted / multi-tenant path (future)

Swap points only. No architectural rework required. The backend abstracts its
database behind a `DbProvider` (see Section 6.3) and its compute behind a
`ComputeProvider`, so moving from a single-user self-host deployment to a
multi-tenant hosted one is additive:

| Layer | v1 (self-host) | Hosted (future) |
|---|---|---|
| Database | SQLite | Managed Postgres |
| Auth | None (LAN-only) | External identity provider, JWT |
| Backend compute | Proxmox LXC | Containers / serverless |
| Worker backend | Proxmox LXC | Managed container instances |
| Secrets | `.env` file + GUI-managed encrypted store (Fernet, ADR-0015) | External secrets manager / KMS (`KmsSecretKeyProvider` seam) |
| Multi-tenancy | Single user | Per-user FK on all rows, row-level security |

Implementing a Postgres `DbProvider` and an auth middleware is the bulk of the
work; nothing in the v1 architecture has to be rewritten.

---

## 4. Repository Structure

### 4.1 Main Repo: `burrow`

```
burrow/
├── api/                         # FastAPI backend (Python 3.12)
│   ├── main.py                  # App factory, CORS, middleware, router registration
│   ├── config.py                # Settings (pydantic-settings, reads from env)
│   ├── routers/
│   │   ├── workspaces.py        # /api/workspaces CRUD
│   │   ├── terminal.py          # /ws/workspaces/{id}/terminal WebSocket
│   │   └── health.py            # /health
│   ├── services/
│   │   ├── workspaceService.py  # Business logic: create/stop/destroy workspace
│   │   ├── proxmoxService.py    # Proxmox API wrapper (proxmoxer)
│   │   └── templateService.py  # Golden template management
│   ├── db/
│   │   ├── provider.py          # DbProvider abstract base class
│   │   ├── sqliteProvider.py    # SQLite impl (homelab)
│   │   ├── postgresProvider.py  # Postgres impl (hosted, stub in v1)
│   │   └── migrations/
│   │       └── 001_init.sql
│   ├── models/
│   │   ├── workspace.py         # Pydantic models: Workspace, WorkspaceCreate, WorkspaceStatus
│   │   └── event.py             # WorkspaceEvent model
│   └── requirements.txt
│
├── ui/                          # Vite + React frontend (TypeScript)
│   ├── src/
│   │   ├── components/
│   │   │   ├── WorkspaceLayout.tsx    # React Mosaic drag-drop panel manager
│   │   │   ├── TerminalPanel.tsx      # xterm.js + WebSocket terminal
│   │   │   ├── WorkspaceList.tsx      # Left sidebar: workspace list + status
│   │   │   ├── NewWorkspaceModal.tsx  # Create workspace form
│   │   │   └── StatusBar.tsx         # Bottom bar: counts, uptime, session stats
│   │   ├── hooks/
│   │   │   ├── useWorkspaces.ts      # TanStack Query: workspace list + mutations
│   │   │   └── useTerminal.ts        # xterm.js lifecycle + WebSocket management
│   │   ├── store/
│   │   │   └── layoutStore.ts        # Zustand: Mosaic panel tree, active workspace
│   │   ├── api/
│   │   │   └── client.ts             # Typed fetch wrapper for /api/*
│   │   ├── types/
│   │   │   └── workspace.ts          # Workspace, WorkspaceStatus, TerminalEvent types
│   │   └── App.tsx
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   └── biome.json
│
├── docs/
│   └── adr/
│       └── ADR-0001-sqlite-first.md  # Document SQLite choice + Postgres migration path
│
├── scripts/
│   └── dev.sh                   # Start FastAPI + Vite dev servers together
│
├── Dockerfile.api               # Multi-stage FastAPI production build
├── Dockerfile.ui                # Multi-stage Vite build (output: static files)
├── docker-compose.dev.yml       # Local dev: api + ui hot-reload
├── .github/workflows/           # CI/CD — see docs/ci-cd-and-testing.md
├── .env.example                 # Template for required env vars (never commit .env)
└── CLAUDE.md                    # This repo's Claude Code context
```

> Container build, test tiers, scanning, signing, and GHCR publishing are
> specified separately in [`ci-cd-and-testing.md`](ci-cd-and-testing.md).

### 4.2 Worker-config Repo: `cc-worker-config`

A separate repo that holds the worker configuration each workspace pulls at boot.
Suggested structure:

```
cc-worker-config/
├── lxc/
│   ├── control-plane/           # Control plane host spec
│   └── worker-template/         # Golden template LXC spec
│       ├── create-template.sh   # Run on Proxmox host: creates VMID 9000
│       └── provision-template.sh # Run inside template CT: installs all software
│
├── plugins/                     # plugin distribution
│   ├── manifest.json            # Pinned plugin sources + refs
│   └── <plugin>/
│       └── install.sh           # one dir per configured plugin
│
├── claude/                      # CLAUDE.md master
│   ├── CLAUDE.md                # Master CLAUDE.md, pulled by every worker on boot
│   └── CLAUDE.project.md        # Template for per-project CLAUDE.md overrides
│
├── systemd/
│   ├── burrow.service           # control plane systemd unit
│   └── burrow-worker.service    # worker boot systemd unit
│
└── nginx/
    └── burrow.conf              # nginx config for the control-plane host
```

---

## 5. API Specification

### 5.1 Response Envelope

All API responses use this standard shape:

```json
{
  "data": { ... },
  "meta": {
    "requestId": "uuid",
    "timestamp": "2026-06-09T12:00:00Z"
  },
  "error": null
}
```

Errors:
```json
{
  "data": null,
  "meta": { "requestId": "uuid", "timestamp": "..." },
  "error": {
    "code": "WORKSPACE_NOT_FOUND",
    "message": "Workspace abc123 does not exist"
  }
}
```

### 5.2 Endpoints

```
GET  /health
     Response: { "status": "ok", "db": "ok", "proxmox": "ok" }
     Auth: none

GET  /api/workspaces
     Response: { "data": [Workspace, ...] }
     Filters: ?status=running|stopped|error

POST /api/workspaces
     Body: { "name": str, "projectRepo": str, "projectBranch": str = "main",
             "pluginSet": str = "default", "node": str = "node1" }
     Response: { "data": Workspace }
     Side effect: clones template LXC, starts it, waits for ttyd health

GET  /api/workspaces/{id}
     Response: { "data": Workspace }

POST /api/workspaces/{id}/stop
     Response: { "data": Workspace }
     Side effect: stops LXC, sets status=stopped, preserves disk state

POST /api/workspaces/{id}/start
     Response: { "data": Workspace }
     Side effect: starts stopped LXC, waits for ttyd health

DELETE /api/workspaces/{id}
     Response: { "data": { "id": str, "destroyed": true } }
     Side effect: stops + destroys LXC, soft-deletes workspace row

GET  /api/workspaces/{id}/events
     Response: { "data": [WorkspaceEvent, ...] }

GET  /api/templates
     Response: { "data": [Template, ...] }

WS   /ws/workspaces/{id}/terminal
     Upgrade: WebSocket
     Proxies binary frames bidirectionally to ttyd in worker LXC
     Reconnects internally on LXC network hiccup (3 retries, 2s backoff)
     Sends { "type": "error", "code": "LXC_NOT_READY" } if ttyd unreachable
```

### 5.3 Workspace State Machine

```
             create
[none] ──────────────> [creating]
                            │
                    ttyd ready (or timeout)
                        │           │
                  [running]      [error]
                        │
               stop ←──┤──→ destroy
                        │           │
                   [stopped]   [destroyed]
                        │
               start ───┘
```

---

## 6. Backend Implementation

### 6.1 Proxmox Service

```python
# api/services/proxmoxService.py
from proxmoxer import ProxmoxAPI
from api.config import settings

class ProxmoxService:
    def __init__(self):
        self.api = ProxmoxAPI(
            settings.proxmoxHost,
            user=settings.proxmoxUser,
            token_name=settings.proxmoxTokenName,
            token_value=settings.proxmoxTokenValue,
            verify_ssl=False
        )

    def cloneLxc(self, templateId: int, newId: int, name: str, node: str) -> dict:
        """Clone template LXC to new VMID."""

    def startLxc(self, node: str, vmId: int) -> dict:
        """Start LXC and return task ID."""

    def stopLxc(self, node: str, vmId: int) -> dict:
        """Stop LXC cleanly."""

    def destroyLxc(self, node: str, vmId: int) -> dict:
        """Stop and destroy LXC. Blocks until task complete."""

    def getLxcStatus(self, node: str, vmId: int) -> dict:
        """Returns Proxmox status dict (status, uptime, mem, cpu)."""

    def getLxcIp(self, node: str, vmId: int) -> str | None:
        """Query network interface for assigned IP (polls until available)."""

    def setCloudInitUserdata(self, node: str, vmId: int, userdata: str) -> None:
        """Inject cloud-init userdata (env vars for burrow-boot.sh)."""

    def getNextVmId(self, poolStart: int = 200, poolEnd: int = 299) -> int:
        """Find next unused VMID in the worker pool range."""

    def getNodeMemoryUsage(self, node: str) -> float:
        """Returns memory utilization 0.0-1.0. Used for capacity guard."""
```

### 6.2 Workspace Service

```python
# api/services/workspaceService.py
import asyncio
import httpx
from api.services.proxmoxService import ProxmoxService
from api.db.provider import DbProvider
from api.models.workspace import Workspace, WorkspaceCreate

TTYD_HEALTH_TIMEOUT = 60       # seconds to wait for ttyd to come up
TTYD_HEALTH_INTERVAL = 2       # seconds between health check attempts
CAPACITY_GUARD_THRESHOLD = 0.80  # block creation if node RAM > 80%

class WorkspaceService:
    def __init__(self, proxmox: ProxmoxService, db: DbProvider):
        self.proxmox = proxmox
        self.db = db

    async def createWorkspace(self, payload: WorkspaceCreate) -> Workspace:
        """Full create flow: capacity check, clone, boot, wait for ttyd, register."""

        # 1. Capacity guard
        usage = self.proxmox.getNodeMemoryUsage(payload.node)
        if usage > CAPACITY_GUARD_THRESHOLD:
            raise CapacityError(f"Node {payload.node} memory at {usage:.0%}, refusing create")

        # 2. Allocate VMID
        vmId = self.proxmox.getNextVmId()

        # 3. Clone template LXC
        self.proxmox.cloneLxc(
            templateId=settings.templateVmId,
            newId=vmId,
            name=payload.name,
            node=payload.node
        )

        # 4. Inject cloud-init env
        userdata = self._buildUserdata(payload)
        self.proxmox.setCloudInitUserdata(payload.node, vmId, userdata)

        # 5. Write pending row to DB
        workspace = await self.db.createWorkspace({
            "name": payload.name,
            "vmid": vmId,
            "node": payload.node,
            "status": "creating",
            "projectRepo": payload.projectRepo,
            "projectBranch": payload.projectBranch,
            "pluginSet": payload.pluginSet,
        })

        # 6. Start LXC
        self.proxmox.startLxc(payload.node, vmId)

        # 7. Wait for IP
        lxcIp = await self._waitForIp(payload.node, vmId)
        await self.db.updateWorkspace(workspace.id, {"lxcIp": lxcIp})

        # 8. Wait for ttyd health check
        await self._waitForTtyd(lxcIp)

        # 9. Mark running
        return await self.db.updateWorkspace(workspace.id, {"status": "running"})

    async def _waitForTtyd(self, lxcIp: str) -> None:
        """Poll ttyd :7681 until responsive or timeout."""
        deadline = asyncio.get_event_loop().time() + TTYD_HEALTH_TIMEOUT
        async with httpx.AsyncClient() as client:
            while asyncio.get_event_loop().time() < deadline:
                try:
                    r = await client.get(f"http://{lxcIp}:7681/", timeout=2)
                    if r.status_code < 500:
                        return
                except (httpx.ConnectError, httpx.TimeoutException):
                    pass
                await asyncio.sleep(TTYD_HEALTH_INTERVAL)
        raise WorkspaceBootError(f"ttyd did not become ready within {TTYD_HEALTH_TIMEOUT}s")

    def _buildUserdata(self, payload: WorkspaceCreate) -> str:
        """Build cloud-init env string for burrow-boot.sh."""
        lines = [
            f"CONFIG_REPO={settings.configRepo}",
            f"CONFIG_BRANCH={settings.configBranch}",
            f"PROJECT_REPO={payload.projectRepo}",
            f"PROJECT_BRANCH={payload.projectBranch}",
        ]
        return "\n".join(lines)
```

### 6.3 Database Provider Abstraction

```python
# api/db/provider.py
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
```

SQLite implementation uses `aiosqlite`. The Postgres implementation (hosted path) uses an async driver such as `asyncpg`. Both implement the same interface. The provider is injected via FastAPI dependency injection.

### 6.4 WebSocket Terminal Proxy

```python
# api/routers/terminal.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import websockets

router = APIRouter()

@router.websocket("/ws/workspaces/{workspaceId}/terminal")
async def terminalProxy(websocket: WebSocket, workspaceId: str, db: DbProvider = Depends(getDb)):
    workspace = await db.getWorkspace(workspaceId)
    if not workspace or workspace.status != "running":
        await websocket.close(code=1008)
        return

    await websocket.accept()
    ttydUrl = f"ws://{workspace.lxcIp}:7681/ws"

    try:
        async with websockets.connect(ttydUrl) as ttyd:
            await db.logEvent(workspaceId, "terminal.connected", {})

            async def clientToTtyd():
                async for msg in websocket.iter_bytes():
                    await ttyd.send(msg)

            async def ttydToClient():
                async for msg in ttyd:
                    await websocket.send_bytes(msg if isinstance(msg, bytes) else msg.encode())

            await asyncio.gather(clientToTtyd(), ttydToClient())

    except (WebSocketDisconnect, websockets.ConnectionClosed):
        await db.logEvent(workspaceId, "terminal.disconnected", {})
    except Exception as e:
        await websocket.send_json({"type": "error", "code": "PROXY_ERROR", "message": str(e)})
        await websocket.close()
```

---

## 7. Data Model

### 7.1 SQLite Schema (homelab)

```sql
-- Migrations: /api/db/migrations/001_init.sql

CREATE TABLE workspaces (
  id            TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  name          TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'creating',
  -- status values: creating | running | stopped | error | destroyed
  vmid          INTEGER,
  node          TEXT NOT NULL DEFAULT 'node1',
  lxcIp         TEXT,
  projectRepo   TEXT NOT NULL,
  projectBranch TEXT NOT NULL DEFAULT 'main',
  pluginSet     TEXT NOT NULL DEFAULT 'default',
  createdAt     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  stoppedAt     TEXT,
  destroyedAt   TEXT,
  deletedAt     TEXT    -- soft delete
);

CREATE TABLE events (
  id            TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  workspaceId   TEXT NOT NULL REFERENCES workspaces(id),
  type          TEXT NOT NULL,
  -- type values: workspace.created|started|stopped|destroyed|terminal.connected|terminal.disconnected|boot.error
  data          TEXT DEFAULT '{}',  -- JSON blob
  createdAt     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE templates (
  id            TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
  name          TEXT NOT NULL UNIQUE,  -- 'default'
  proxmoxTid    INTEGER NOT NULL,      -- Template VMID (9000)
  pluginManifest TEXT DEFAULT '{}',   -- JSON: plugin set definition
  createdAt     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- Seed default template
INSERT INTO templates (name, proxmoxTid) VALUES ('default', 9000);

CREATE INDEX idx_workspaces_status   ON workspaces(status);
CREATE INDEX idx_events_workspaceId  ON events(workspaceId);
```

### 7.2 Postgres Schema (hosted path, stub for reference)

```sql
-- schema: burrow
-- All tables: user_id FK, RLS enabled, soft delete via deletedAt

CREATE TABLE burrow.workspaces (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       text NOT NULL,  -- subject claim from the auth token
  -- ... same columns as SQLite, plus user_id and uuid keys
);

ALTER TABLE burrow.workspaces ENABLE ROW LEVEL SECURITY;

CREATE POLICY "user owns workspace" ON burrow.workspaces
  FOR ALL
  USING (user_id = current_setting('request.jwt.claims', true)::json ->> 'sub')
  WITH CHECK (user_id = current_setting('request.jwt.claims', true)::json ->> 'sub');
```

---

## 8. Frontend Implementation

### 8.1 Key Dependencies

```json
{
  "dependencies": {
    "react": "^19.0.0",
    "@xterm/xterm": "^5.x",
    "@xterm/addon-fit": "^0.10.x",
    "@xterm/addon-web-links": "^0.11.x",
    "react-mosaic-component": "^7.x",
    "@tanstack/react-query": "^5.x",
    "zustand": "^5.x"
  },
  "devDependencies": {
    "vite": "^6.x",
    "typescript": "^5.x",
    "tailwindcss": "^4.x",
    "@biomejs/biome": "^1.x"
  }
}
```

### 8.2 UI Layout

```
┌───────────────────────────────────────────────────────────────┐
│  Burrow  [node1: 3 running / 4GB free]    [+ New Workspace]   │  navbar
├────────┬──────────────────────────────────────────────────────┤
│        │                                                       │
│  [A]   │  ┌────────────────────┬─────────────────────────┐    │
│  run   │  │  ProjectAlpha       │  ProjectBeta            │    │
│        │  │  [terminal]         │  [terminal]             │    │
│  [B]   │  │                     │                         │    │  Mosaic
│  run   │  │                     │                         │    │  panels
│        │  ├────────────────────┴─────────────────────────┤    │
│  [C]   │  │  ProjectGamma                                 │    │
│  stop  │  │  [terminal]                                   │    │
│        │  │                                               │    │
│  [D]   │  └───────────────────────────────────────────────┘   │
│  err   │                                                       │
├────────┴──────────────────────────────────────────────────────┤
│  3 running  |  1 stopped  |  Session uptime: 2h 14m           │  StatusBar
└───────────────────────────────────────────────────────────────┘
```

### 8.3 Component Contracts

**`WorkspaceLayout.tsx`**  
Renders the React Mosaic root. Reads panel tree from Zustand `layoutStore`. Handles split (H/V), drag-and-drop, and resize. Each leaf node in the Mosaic is a workspace ID string, rendered as `TerminalPanel`.

```typescript
// layoutStore.ts
interface LayoutStore {
  mosaicNode: MosaicNode<string> | null   // React Mosaic tree
  activeWorkspaceId: string | null
  openPanel: (workspaceId: string) => void
  closePanel: (workspaceId: string) => void
  splitPanel: (workspaceId: string, direction: 'right' | 'bottom') => void
}
```

**`TerminalPanel.tsx`**  
Mounts xterm.js on a `<div>` ref. Opens WebSocket to `/ws/workspaces/{id}/terminal`. Uses `FitAddon` to fill container on resize. Reconnects on disconnect (exponential backoff, 5 retries, max 30s). Shows a "reconnecting" overlay during backoff. Unmounts cleanly on panel close (closes WebSocket, disposes terminal).

```typescript
interface TerminalPanelProps {
  workspaceId: string
  onClose: () => void
}
```

**`NewWorkspaceModal.tsx`**  
Form fields: workspace name, git repo URL, branch (default: main), node (node1/node2 from API). On submit: POST `/api/workspaces`, shows spinner with status text ("Cloning template... Starting LXC... Waiting for Claude..."), then calls `layoutStore.openPanel(newId)` on success.

**`useTerminal.ts`**  
Hook that owns the xterm.js + WebSocket lifecycle for a given workspace ID. Returns `{ containerRef, status, reconnectAttempts }`.

---

## 9. Golden Template LXC

### 9.1 Spec (e.g. VMID 9000)

```
OS:           Ubuntu 24.04 LTS (CT template: ubuntu-24.04-standard)
vCPU:         2
RAM:          4096 MB
Disk:         30 GB (your storage pool, e.g. local-lvm)
Network:      DHCP on vmbr0
Unprivileged: yes
Features:     nesting=1
```

**This template is never started or used directly. Only cloned.**

### 9.2 `provision-template.sh`

Run inside the template CT once after creation. Installs all software that will be present in every workspace.

```bash
#!/usr/bin/env bash
# cc-worker-config/lxc/worker-template/provision-template.sh
# Run inside template CT (VMID 9000) as root.
set -euo pipefail

# System baseline
apt-get update && apt-get upgrade -y
apt-get install -y git curl build-essential ttyd

# Node.js 22 + Claude Code
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt-get install -y nodejs
npm install -g @anthropic-ai/claude-code

# gsd (spec-driven workflow plugin)
npm install -g get-shit-done-cc

# rtk (60-90% token reduction, Rust CLI proxy)
# Install script from cc-worker-config/plugins/rtk/install.sh
bash /tmp/plugins/rtk/install.sh

# caveman (65% token reduction, minimal language output)
bash /tmp/plugins/caveman/install.sh

# compound-engineering-plugin
bash /tmp/plugins/compound-engineering/install.sh

# Burrow worker boot script + systemd unit
install -m 755 /tmp/burrow-boot.sh /opt/burrow-boot.sh
install -m 644 /tmp/burrow-worker.service /etc/systemd/system/burrow-worker.service
systemctl enable burrow-worker.service

# Pre-create environment file placeholder (overwritten by cloud-init on each clone)
mkdir -p /etc/burrow
touch /etc/burrow/worker.env

# Clean up apt cache
apt-get clean && rm -rf /var/lib/apt/lists/*

echo "Template provisioned OK"
```

### 9.3 `burrow-boot.sh` (runs in each worker LXC on start)

```bash
#!/usr/bin/env bash
# /opt/burrow-boot.sh
# Runs on every workspace boot via burrow-worker.service.
# Environment variables injected by cloud-init from control plane.
set -euo pipefail

CONFIG_REPO="${CONFIG_REPO:?CONFIG_REPO must be set}"
CONFIG_BRANCH="${CONFIG_BRANCH:-main}"
PROJECT_REPO="${PROJECT_REPO:-}"
PROJECT_BRANCH="${PROJECT_BRANCH:-main}"
WORKER_HOME="/root"

log() { echo "[burrow-boot] $*"; }

# Pull latest config from cc-worker-config
log "Pulling config from $CONFIG_REPO ($CONFIG_BRANCH)"
git clone --depth=1 --branch "$CONFIG_BRANCH" "$CONFIG_REPO" /tmp/cc-worker-config

# Install CLAUDE.md
cp /tmp/cc-worker-config/claude/CLAUDE.md "$WORKER_HOME/CLAUDE.md"
log "CLAUDE.md installed"

# Install plugin configs
mkdir -p "$WORKER_HOME/.claude/plugins"
cp -r /tmp/cc-worker-config/plugins/. "$WORKER_HOME/.claude/plugins/"
log "Plugins installed"

# Clone project repo if specified
if [[ -n "$PROJECT_REPO" ]]; then
  log "Cloning project: $PROJECT_REPO ($PROJECT_BRANCH)"
  git clone --branch "$PROJECT_BRANCH" "$PROJECT_REPO" "$WORKER_HOME/project"
fi

# Determine claude command (use rtk proxy if available)
CLAUDE_CMD="claude"
if command -v rtk &>/dev/null; then
  CLAUDE_CMD="rtk claude"
  log "rtk detected, using: rtk claude"
fi

# Start ttyd on :7681, binding the claude shell
# --writable: allow input; --once: exit when client disconnects (workspace done)
log "Starting ttyd with: $CLAUDE_CMD"
exec ttyd \
  --port 7681 \
  --writable \
  --once \
  --interface lo \
  bash -c "cd ${PROJECT_REPO:+$WORKER_HOME/project} && $CLAUDE_CMD"
```

Note: `--once` means ttyd exits when the client disconnects. The workspace status transitions to `stopped` via a polling mechanism in the control plane (Proxmox API detects LXC exited). Workers can also be long-lived if `--once` is removed (configurable per template).

---

## 10. Control Plane Setup

### 10.1 nginx Config

```nginx
# /etc/nginx/sites-available/burrow
server {
    listen 80;
    server_name burrow.lan;

    # Serve React UI (static build)
    location / {
        root /opt/burrow/ui/dist;
        try_files $uri $uri/ /index.html;
    }

    # Proxy FastAPI
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket terminal proxy
    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;   # Keep WS alive for long sessions
        proxy_send_timeout 3600s;
    }
}
```

### 10.2 systemd Service

```ini
# /etc/systemd/system/burrow.service
[Unit]
Description=Burrow Workspace Manager API
After=network-online.target
Wants=network-online.target

[Service]
Type=exec
User=burrow
WorkingDirectory=/opt/burrow/api
EnvironmentFile=/opt/burrow/.env
ExecStart=/opt/burrow/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=burrow

[Install]
WantedBy=multi-user.target
```

### 10.3 `.env.example`

```bash
# Proxmox connection
PROXMOX_HOST=pve1.local
PROXMOX_USER=burrow@pve            # dedicated least-privilege user, NOT root@pam
PROXMOX_TOKEN_NAME=burrow
PROXMOX_TOKEN_VALUE=

# Worker config distribution
CONFIG_REPO=git@github.com:your-org/cc-worker-config.git
CONFIG_BRANCH=main

# LXC settings
TEMPLATE_VMID=9000
WORKER_POOL_START=200
WORKER_POOL_END=299
DEFAULT_NODE=node1

# Database
DATABASE_PATH=/data/burrow.db

# Security (hosted/multi-tenant mode only)
# JWKS_URL=
# ALLOWED_ORIGINS=https://burrow.example.com
```

> See the repo-root `.env.example` for the authoritative template.

---

## 11. Plugin Distribution

### 11.1 `plugins/manifest.json`

```json
{
  "schemaVersion": "1.0.0",
  "plugins": {
    "caveman": {
      "source": "github.com/JuliusBrussee/caveman",
      "ref": "main",
      "type": "claude-plugin",
      "description": "65% token reduction via minimal language output"
    },
    "rtk": {
      "source": "github.com/rtk-ai/rtk",
      "ref": "main",
      "type": "binary",
      "description": "60-90% token reduction, Rust CLI proxy for claude"
    },
    "gsd": {
      "source": "github.com/gsd-build/get-shit-done",
      "ref": "main",
      "type": "npm-global",
      "description": "Spec-driven development workflow plugin"
    },
    "compound-engineering": {
      "source": "github.com/EveryInc/compound-engineering-plugin",
      "ref": "main",
      "type": "claude-plugin",
      "description": "Compound engineering workflow plugin"
    }
  }
}
```

**Plugin type resolution at boot:**
- `claude-plugin`: copied to `~/.claude/plugins/{name}/`
- `binary`: installed to `/usr/local/bin/` (pre-installed in template)
- `npm-global`: installed via npm globally (pre-installed in template)

Binary and npm-global plugins are baked into the golden template at provision time. `claude-plugin` type plugins are always pulled fresh at boot from cc-worker-config to pick up config changes without reprovisioning the template.

---

## 12. Implementation Phases

### Phase 0: Golden Template (target: Week 1)
- [ ] Build template LXC on node1 (VMID 9000) using `create-template.sh`
- [ ] Run `provision-template.sh` inside CT
- [ ] Manually verify: ttyd starts, `claude` launches correctly, rtk wraps it
- [ ] Add template spec to `cc-worker-config/lxc/worker-template/`
- [ ] Commit and tag: `chore: add worker template spec`

### Phase 1: Control Plane API (target: Week 1-2)
- [ ] Provision the control-plane LXC/host
- [ ] Scaffold FastAPI app with SQLite provider
- [ ] Implement ProxmoxService (clone, start, stop, destroy, getIp)
- [ ] Implement WorkspaceService (full create flow with ttyd health poll)
- [ ] Implement WebSocket terminal proxy router
- [ ] Unit tests: WorkspaceService with Proxmox mock, state machine transitions
- [ ] GET /health endpoint confirms db + proxmox connectivity
- [ ] Deploy with systemd, confirm accessible at `http://<control-plane-host>:8000`

### Phase 2: React UI (target: Week 2-3)
- [ ] Scaffold Vite + React + TypeScript project
- [ ] Implement `layoutStore` (Zustand, Mosaic panel tree)
- [ ] `WorkspaceList` sidebar with TanStack Query polling
- [ ] `TerminalPanel` with xterm.js + WebSocket, reconnect logic
- [ ] `WorkspaceLayout` Mosaic panels (split, drag, resize)
- [ ] `NewWorkspaceModal` with boot progress states
- [ ] `StatusBar` with running count + session uptime
- [ ] Build served by nginx on the control-plane host, end-to-end test from a browser on the LAN

### Phase 3: Plugin + Config Pipeline (target: Week 3)
- [ ] Finalize `cc-worker-config/plugins/` structure + `manifest.json`
- [ ] Author master `CLAUDE.md` for workers
- [ ] Harden `burrow-boot.sh`: error trapping, git auth fallback, per-project CLAUDE.md overlay
- [ ] Smoke test: create workspace from known repo, verify CLAUDE.md + all plugins land correctly
- [ ] Add `cc-worker-config` tag: `chore: add burrow worker config`

### Phase 4: Hardening (target: Week 4)
- [ ] Auto-stop idle workspaces: detect ttyd has no active connections > N minutes, set status=stopped
- [ ] Capacity guard: block create if Proxmox node RAM > 80%
- [ ] LXC IP allocation strategy: document predictable IP range vs dynamic + Proxmox API poll
- [ ] Workspace restore: if browser refreshes and workspace still running, reconnect terminal
- [ ] Event log in UI (expandable activity drawer per workspace)
- [ ] Structured JSON logging on FastAPI backend

---

## 13. Hosted / Multi-tenant Path (optional, additive)

The v1 architecture is single-user and LAN-only. Running Burrow as a hosted,
multi-tenant service is an additive effort on top of the provider seams — none of
the v1 code has to be rewritten. The major pieces, all vendor-neutral:

- [ ] Postgres `DbProvider` implementation + multi-tenant schema (see §7.2)
- [ ] Authentication: an identity provider + `requireAuth` middleware on all routes
- [ ] `user_id` FK on all workspace and event rows, row-level security policies applied
- [ ] `ComputeProvider` implementation for a cloud/container backend
- [ ] Secrets moved out of `.env` into an external secrets manager / KMS (partially done: the GUI-managed Fernet credential store lands per ADR-0015; a full external manager / KMS stays hosted-path via the `KmsSecretKeyProvider` seam)
- [ ] Move to managed DNS + HTTPS
- [ ] Observability (error tracking + product analytics) if desired
- [ ] Security/compliance review appropriate to handling other users' data

---

## 14. Claude Code / Worker Pipeline Notes

- `CLAUDE.md` in `cc-worker-config/claude/` is the master context file that all workers pull
- The `burrow` repo itself gets its own `CLAUDE.md` in root, seeded with this spec summary and stack conventions
- The worker plugin set is configurable via the manifest (§11). Token-reduction proxies and
  workflow plugins (e.g. rtk, caveman) are optional add-ons, not requirements — if a wrapper
  command is present the boot script uses it, otherwise it shells into `claude` directly (§9.3)

---

## Appendix A: ADR-0001 — SQLite for Self-host State

**Status:** Accepted  
**Context:** Burrow v1 targets a single-user self-host deployment. No external database dependency is warranted.  
**Decision:** Use SQLite via `aiosqlite` behind the `DbProvider` abstraction for v1. The `DbProvider` interface allows drop-in replacement with Postgres for a hosted path.  
**Consequences:** State lives on the control-plane host's disk. No replication. Acceptable for single-user self-host; unacceptable for a multi-tenant deployment.  
**Revisit trigger:** Hosted/multi-tenant path or a second concurrent user requirement.

## Appendix B: Open Questions (Resolve Before Phase 1 Complete)

1. **LXC IP assignment:** Predictable static IPs per VMID (e.g. VMID 200 = `10.x.y.200` on your subnet) vs DHCP + Proxmox API poll? Static is simpler, DHCP is more flexible. Recommendation: static pool aligned to VMID range.
2. **ttyd `--once` behavior:** With `--once`, ttyd exits when client disconnects. This means closing the browser tab terminates the Claude session. Is that desired, or should sessions persist? May want a "detach" vs "terminate" distinction in the UI.
3. **Worker node selection:** Round-robin between node1 and node2, or let the user pick? Start with manual selection in NewWorkspaceModal, add auto-select logic in Phase 4.
4. **Plugin update cadence:** Pull `cc-worker-config` at boot (always latest) vs snapshot at workspace create time (reproducible). Recommendation: pull at boot for now, add version pinning per workspace when the manifest stabilizes.
