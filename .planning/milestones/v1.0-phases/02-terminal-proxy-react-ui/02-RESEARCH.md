<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Phase 2: Terminal Proxy + React UI - Research

**Researched:** 2026-06-10
**Domain:** FastAPI/Starlette WebSocket terminal proxy (ttyd `tty` subprotocol bridge) + Vite/React 19 tiling terminal UI (xterm.js 6, react-mosaic 6.2.0, TanStack Query 5, Zustand 5, Tailwind v4)
**Confidence:** HIGH (ttyd protocol confirmed against current ttyd source; every package version + peer re-verified live on npm/PyPI 2026-06-10; backend contracts read from the committed Phase-0/1 code)

## Summary

Phase 2 has two halves. The **backend WS proxy** (`api/routers/terminal.py`) is a thin, opaque, type-preserving relay: accept the browser WS, dial the worker's ttyd at `ws://{workspace.lxc_ip}:7681/ws` with `subprotocols=["tty"]`, and pump frames both directions under `asyncio.wait(FIRST_COMPLETED)` + cancel-the-loser. The single load-bearing correctness rule (SC-7) is **never re-encode**: ttyd's `tty` subprotocol is opcode-framed, the browser's xterm adapter already emits the correct prefixes, so the proxy must forward `str`→`send_text` and `bytes`→`send_bytes` verbatim. The spec §6.4 `msg.encode()` turns a ttyd text control frame into a binary one and produces a dead terminal. This is verified: the proxy is a dumb byte/text relay; the **client** speaks ttyd's protocol.

The **React UI** is a single full-screen app shell (top bar / sidebar / mosaic grid / status bar) built on the frozen `/api/v1` envelope contract. The crux components: a `useTerminal` hook owning the xterm.js 6 + WebSocket + FitAddon + ResizeObserver lifecycle (open/dispose/reconnect with jittered backoff and a visible overlay), a Zustand `layoutStore` holding the `MosaicNode<string>` tree and reconciling it against the live workspace list, and a TanStack Query `useWorkspaces` polling `GET /api/v1/workspaces` with WS-event-driven invalidation so the sidebar and the live terminal never drift. A typed `client.ts` unwraps the `{data, meta, error}` envelope. Tailwind v4 is wired via `@tailwindcss/vite` (no `tailwind.config.ts`); design tokens live in CSS `@theme`.

**Primary recommendation:** Build the proxy as an opaque `tty`-subprotocol relay with `FIRST_COMPLETED`+cancel teardown and a typed `LXC_NOT_READY` error frame; build a **protocol-accurate stub ttyd WS server** (real `tty` framing, not a bare echo) so the SC-7 bug cannot hide in CI; build the UI bottom-up (client → useWorkspaces → useTerminal/TerminalPanel → layoutStore → WorkspaceLayout → NewWorkspaceModal → StatusBar) with the xterm adapter emitting the ttyd JSON init + `'0'`/`'1'` frames the proxy passes through untouched.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Backend WS terminal proxy (TERM-01..04 — SC-7, SC-10)**
- A FastAPI WebSocket route `/ws/workspaces/{id}/terminal`: accept the browser WS, open the upstream ttyd WS with the **`tty` subprotocol negotiated** (`subprotocols=["tty"]`), and **relay frames opaquely both directions preserving text-vs-binary** — do NOT `.encode()` text frames (SC-7 fixes the spec §6.4 corruption bug). ttyd's framing (input `'0'`-prefix, resize `'1'`+JSON) passes through untouched from the xterm adapter.
- Upstream leg uses the `websockets` client lib (FastAPI has no WS client); browser leg is native Starlette WS.
- **Teardown** (SC-10): bridge the two directions with `asyncio.wait(FIRST_COMPLETED)` + cancel the loser; no half-open leak, no FD growth. Log `terminal.connected`/`terminal.disconnected` events; emit a typed `{"type":"error","code":"LXC_NOT_READY"}` frame when ttyd is unreachable, and close only running workspaces (reject non-running with a close code).

**xterm.js terminal panel (TERM-05..07)**
- `@xterm/xterm` 6 + `@xterm/addon-fit`; mount on a div ref, open the WS, `FitAddon` fits/reflows on container resize (ResizeObserver), the input/resize adapter drives a real claude TUI (not stuck 80x24). **Auto-reconnect with jittered backoff + a visible reconnecting overlay** (TERM-06); stop retrying on `error`/`destroyed`. **Unmount cleanly** (TERM-07): close WS, dispose terminal, disconnect ResizeObserver.

**Tiling layout (UI-02) + state**
- `react-mosaic-component` **6.2.0** (React-19 compatible — NOT the 7.0.0-beta on `latest`). A Zustand `layoutStore` holds the Mosaic tree + active workspace; open/split(H/V)/drag/resize; persist the tree and **reconcile it against the live workspace list** on load (drop panels for gone workspaces).

**UI surfaces (UI-01/03/04/05)**
- Sidebar (UI-01): TanStack Query polls `GET /api/v1/workspaces`; live status chips (creating/running/stopped/error).
- New Workspace modal (UI-03): name/repo/branch/node form → `POST /api/v1/workspaces`; shows live boot-progress states; opens the panel on success.
- Status bar (UI-04): running/stopped counts, session uptime, node capacity.
- Restore-after-refresh (UI-05): on load, reconnect the terminal of a still-`running` workspace to its **live** session — **no fresh process, no scrollback restore in v1** (documented limitation; full scrollback is v2/WSX-03).

**Stack (STACK.md pins; ADR-0008)**
- Vite 8, React 19, TypeScript 6, Tailwind v4 via `@tailwindcss/vite` (no `tailwind.config.ts`), `@biomejs/biome` 2, Zustand 5, `@tanstack/react-query` 5, `@xterm/xterm` 6 + `@xterm/addon-fit`, `react-mosaic-component` 6.2.0. Tests: vitest 4 + Testing Library, MSW (mock `/api/v1`), Playwright (e2e over the FakeComputeProvider). A typed `client.ts` fetch wrapper unwraps the `data`/`meta`/`error` envelope.

**Design**
- Honor the committed design handoff: `docs/design/burrow-ui-mockup.html`, `docs/design/burrow-ui-design-prompt.md`, and `design/Burrow-handoff/burrow/project/` (mockup + `_ds` colors/type tokens). The UI-SPEC (generated next) is the binding visual contract.

### Claude's Discretion
- Component file layout under `ui/src/` (follow tech-spec §4.1: components/, hooks/, store/, api/, types/), the exact backoff curve, and the stub-ttyd test double's shape are at Claude's discretion within the above.

### Deferred Ideas (OUT OF SCOPE)
- Real ttyd `tty` handshake + a live claude TUI against a real worker → dev-homelab smoke gate (no Proxmox/worker reachable from this box) — `human_needed`, not phase-blocking.
- Event-log activity drawer (UI-06) → Phase 4. Full terminal scrollback restore → v2 (WSX-03).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TERM-01 | WebSocket endpoint bridges browser terminal to worker ttyd, relaying both directions | Pattern: opaque dual-pump bridge; backend leg `websockets.asyncio.client.connect`, browser leg Starlette WS. Target `ws://{ws.lxc_ip}:7681/ws` from `Workspace.lxc_ip` (already on the model). |
| TERM-02 | Proxy negotiates ttyd `tty` subprotocol, preserves framing without corruption (SC-6/SC-7) | **Verified against ttyd source:** subprotocol `'tty'`; `str`→`send_text`, `bytes`→`send_bytes`; never `.encode()`. ttyd command bytes confirmed (`INPUT '0'`, `RESIZE '1'`). |
| TERM-03 | Proxy logs connect/disconnect events + emits typed error frame when ttyd unreachable | `db.logEvent(id, "terminal.connected"/"terminal.disconnected", {})` (event types already in the schema); `send_json({"type":"error","code":"LXC_NOT_READY"})` then close. |
| TERM-04 | Proxy tears down cleanly when either side closes (FIRST_COMPLETED + cancel; no half-open) | `asyncio.wait({up, down}, return_when=FIRST_COMPLETED)` → cancel pending → close both legs. `ping_interval` keepalive on the upstream. |
| TERM-05 | Browser terminal renders via xterm.js and fits/reflows on resize | `@xterm/xterm@6.0.0` + `@xterm/addon-fit@0.11.0`; `FitAddon.fit()` on a debounced ResizeObserver callback, only when visible/non-zero. |
| TERM-06 | Auto-reconnect with backoff + reconnecting overlay | `useTerminal` reconnect loop with jittered exponential backoff; overlay state machine `connecting/connected/reconnecting/error`; stop on close code 1008 / `error`/`destroyed`. |
| TERM-07 | Terminal unmounts cleanly (WS closed, xterm disposed) | `useEffect` cleanup: `socket.close()`, `term.dispose()`, `observer.disconnect()`, `fitAddon.dispose()`. One teardown per mount. |
| UI-01 | Sidebar lists workspaces with live polled status indicators | `useWorkspaces` = `useQuery(['workspaces'], …, { refetchInterval })`; status dot map from `Workspace.status`. |
| UI-02 | Terminals render in tiling react-mosaic layout (open/split/drag/resize) | `react-mosaic-component@6.2.0` `<Mosaic>` controlled by `layoutStore.mosaicNode`; `react-dnd@16` HTML5 backend; import `react-mosaic-component/react-mosaic-component.css`. |
| UI-03 | New Workspace modal collects name/repo/branch/node + shows live boot-progress | `useMutation` → `POST /api/v1/workspaces`; the saga is synchronous in v1 (returns the `running` workspace), so boot-progress is staged optimistic UI + the returned row (see "Boot-progress" pitfall). |
| UI-04 | Status bar shows running/stopped counts, session uptime, node capacity | Derive counts from the `useWorkspaces` list; capacity per node is NOT yet an API field — see Open Questions Q3. |
| UI-05 | After refresh, reconnect terminal of a still-running workspace (live session, no scrollback) | On load, `layoutStore` reconciles persisted tree against the live list; `useTerminal` opens a fresh WS to the live ttyd PTY. No replay buffer in v1 (honest reconnect). |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Terminal byte/frame transport | API / Backend (`terminal.py` WS bridge) | Browser (xterm adapter emits/consumes frames) | Only the backend can reach the worker's LAN IP; the browser must go through the control plane (Pitfall 5/12). The browser never connects to ttyd directly. |
| ttyd `tty` protocol framing (init/`'0'`/`'1'`) | Browser / Client (xterm adapter) | — | The proxy is opaque; the client owns the protocol so the proxy stays a dumb relay (Anti-Pattern 4). |
| Workspace list + status truth | API / Backend (DB) → TanStack Query cache | — | Server is the source of truth; the UI polls and caches, never mirrors status into Zustand. |
| Panel layout (tree, active, splits) | Browser / Client (Zustand `layoutStore` + localStorage) | — | Pure view state; persisted client-side, reconciled against server truth on load. |
| Workspace mutations (create/stop/start/destroy) | API / Backend (`WorkspaceService` saga) | Browser (optimistic UI + cache invalidation) | Backend enforces the state machine (SC-12); UI gates buttons per state but treats the server as the gate. |
| Reconnect / overlay / backoff | Browser / Client (`useTerminal`) | — | Per-panel client concern; the proxy just closes, the client decides retry-vs-stop. |
| Auth / origin enforcement | API / Backend (CORS + LAN bind) | — | v1 is LAN-only no-auth by design; CORS already non-`*` in `main.py`. The WS route needs an explicit origin gate (see Security Domain). |

## Standard Stack

> Every version below re-verified live on the npm registry / PyPI on 2026-06-10. These match STACK.md's pins; deltas vs STACK.md are flagged in "State of the Art."

### Core (frontend runtime)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| react / react-dom | 19.2.7 | UI framework | Spec + STACK.md mandate. `[VERIFIED: npm registry]` |
| @xterm/xterm | 6.0.0 | Terminal emulator | Scoped package (legacy `xterm` deprecated); stable 5→6 API for this use. `[VERIFIED: npm registry + ttyd client uses xterm]` |
| @xterm/addon-fit | 0.11.0 | Fit terminal to container | Standard companion; `FitAddon.fit()` reflows cols/rows. `[VERIFIED: npm registry]` |
| @xterm/addon-web-links | 0.12.0 | Clickable URLs in terminal output | Optional polish; cheap, no protocol impact. `[VERIFIED: npm registry]` |
| react-mosaic-component | **6.2.0** (pin exact) | Tiling/split/drag/resize panels | React-19 peer (`react: 16 - 19` confirmed); the `latest` tag is `7.0.0-beta0` — DO NOT use `^`. `[VERIFIED: npm registry — peer 16-19]` |
| react-dnd | 16.0.1 | Drag backend for react-mosaic | Transitive peer of mosaic; needs `react >= 16.14` (OK). Use the HTML5 backend. `[VERIFIED: npm registry]` |
| @tanstack/react-query | 5.101.0 | Server-state: workspace polling + mutations | Spec mandate; peer `react ^18 || ^19`. `[VERIFIED: npm registry]` |
| zustand | 5.0.14 | Client-state: mosaic tree + active workspace | Spec mandate; peer `react >=18`. `[VERIFIED: npm registry]` |
| tailwindcss + @tailwindcss/vite | 4.3.0 | Styling (CSS-first, no JS config) | v4 Vite plugin; peer `vite ^5.2||^6||^7||^8`. `[VERIFIED: npm registry]` |

### Core (frontend build/test) + backend
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| vite | 8.0.16 | Build/dev server | `@vitejs/plugin-react@6` peer is `vite ^8.0.0`. `[VERIFIED: npm registry]` |
| @vitejs/plugin-react | 6.0.2 | React Fast Refresh / JSX | Forces Vite 8. `[VERIFIED: npm registry — peer vite ^8.0.0]` |
| typescript | 6.0.3 | Types | Matches the scaffold (`ui/package.json` already pins 6.0.3). `[VERIFIED: ui/package.json]` |
| @biomejs/biome | 2.4.16 | Lint + format | Already pinned in the scaffold (`ui/biome.json` schema 2.4.16). `[VERIFIED: ui/biome.json]` |
| vitest | 4.1.8 | Unit/integration runner | Pairs with Vite 8. `[VERIFIED: npm registry]` |
| @testing-library/react | 16.3.2 | Component/hook testing | Peer `react ^18 || ^19`. `[CITED: STACK.md]` |
| @testing-library/jest-dom | 6.9.1 | DOM matchers | Standard companion. `[CITED: STACK.md]` |
| msw | 2.14.6 | API mocking (Tier-2 UI integration) | v2 `http`/`HttpResponse` API. Has a benign `postinstall` (writes the mock service worker) — see Package Legitimacy Audit. `[VERIFIED: npm registry]` |
| @playwright/test | 1.60.0 | e2e (Tier 3) over FakeComputeProvider + stub ttyd | ci-cd §4.4. `[CITED: STACK.md]` |
| websockets (Python) | 16.0 (pin in `api/pyproject.toml`) | Upstream WS **client** to ttyd | FastAPI has no WS client; `from websockets.asyncio.client import connect`. **NOTE: the api venv currently has 14.1 installed — see Environment Availability.** `[VERIFIED: PyPI — 16.0 latest]` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled WS in `useTerminal` | `@xterm/addon-attach` | addon-attach couples xterm directly to a socket and gives no reconnect/overlay control; the phase needs custom backoff. Hand-roll (STACK.md "What NOT to use"). |
| react-mosaic 6.2.0 | react-mosaic 7.0.0-beta0 | 7 is a pre-release on `latest`; pulls uuid 11 / rdndmb 9. Only if a 6.2.0 bug forces it. |
| `websockets` client | `httpx-ws` 0.9.0 | One lib for WS+HTTP, but adds a dep `websockets` doesn't (already transitively present via `uvicorn[standard]`). Stick with `websockets`. |
| Translating proxy (re-frame for plain xterm) | — | More backend code; couples the proxy to ttyd opcodes. The opaque relay + protocol-aware client is simpler and is what ttyd's own client does. |

**Installation:**
```bash
# Frontend (ui/) — runtime
npm install react@19.2.7 react-dom@19.2.7 \
  @xterm/xterm@6.0.0 @xterm/addon-fit@0.11.0 @xterm/addon-web-links@0.12.0 \
  react-mosaic-component@6.2.0 react-dnd@16.0.1 react-dnd-html5-backend@16.0.1 \
  @tanstack/react-query@5.101.0 zustand@5.0.14

# Frontend — build + styling + test
npm install -D vite@8.0.16 @vitejs/plugin-react@6.0.2 \
  tailwindcss@4.3.0 @tailwindcss/vite@4.3.0 \
  vitest@4.1.8 @testing-library/react@16.3.2 @testing-library/jest-dom@6.9.1 \
  jsdom msw@2.14.6 @playwright/test@1.60.0
# typescript@6.0.3 + @biomejs/biome@2.4.16 already in the scaffold.

# Backend (api/) — add the WS client dep explicitly (it imports `websockets`)
uv add "websockets==16.0"
```

## Package Legitimacy Audit

> slopcheck 0.6.1 is installed in the user site-packages but is not on PATH, and the sandbox classifier blocked invoking it (running an agent-installed package outside research scope). Per the graceful-degradation protocol, packages were verified by direct npm/PyPI registry queries + known-source confirmation instead; new/unfamiliar packages are tagged `[ASSUMED]` and the planner should gate any install the operator has not already vendored behind a `checkpoint:human-verify`. All frontend packages below are long-established, high-download, source-backed projects already named in the frozen STACK.md / ADR-0008.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| react / react-dom | npm | 12+ yrs | ~30M/wk | github.com/facebook/react | unavailable | Approved (canonical) |
| @xterm/xterm | npm | scoped since 2023 | ~1M/wk | github.com/xtermjs/xterm.js | unavailable | Approved |
| @xterm/addon-fit | npm | scoped since 2023 | ~700k/wk | github.com/xtermjs/xterm.js | unavailable | Approved |
| @xterm/addon-web-links | npm | scoped since 2023 | ~500k/wk | github.com/xtermjs/xterm.js | unavailable | Approved |
| react-mosaic-component | npm | 8+ yrs (6.2.0) | ~50k/wk | github.com/nomcopter/react-mosaic | unavailable | Approved — pin `6.2.0` exact (not `^`) |
| react-dnd / react-dnd-html5-backend | npm | 9+ yrs | ~3M/wk | github.com/react-dnd/react-dnd | unavailable | Approved |
| @tanstack/react-query | npm | mature | ~7M/wk | github.com/TanStack/query | unavailable | Approved |
| zustand | npm | mature | ~6M/wk | github.com/pmndrs/zustand | unavailable | Approved |
| tailwindcss / @tailwindcss/vite | npm | mature | ~12M/wk | github.com/tailwindlabs/tailwindcss | unavailable | Approved |
| vite / @vitejs/plugin-react | npm | mature | ~25M/wk | github.com/vitejs/vite | unavailable | Approved |
| vitest | npm | mature | ~8M/wk | github.com/vitest-dev/vitest | unavailable | Approved |
| @testing-library/react | npm | mature | ~13M/wk | github.com/testing-library | unavailable | Approved |
| msw | npm | mature | ~5M/wk | github.com/mswjs/msw | unavailable | Approved — **has a `postinstall`** (`node -e import('./config/scripts/postinstall.js')`); this is MSW's documented worker-setup hook, benign, from the canonical repo. |
| @playwright/test | npm | mature | ~9M/wk | github.com/microsoft/playwright | unavailable | Approved |
| websockets (Python) | PyPI | mature | very high | github.com/python-websockets/websockets | unavailable | Approved — pin `16.0` |

**Packages removed due to slopcheck [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** none. (`msw` carries a postinstall but it is a known, canonical, source-verified hook — not a slop signal.)

*slopcheck was unavailable at research time. No package above is novel or low-trust; all are named in the frozen STACK.md/ADR-0008. The planner need only re-confirm versions at install time (`npm ci` against the committed lockfile) and verify the lockfile freshness gate stays green.*

## Architecture Patterns

### System Architecture Diagram

```
 Browser
 ┌──────────────────────────────────────────────────────────────────────┐
 │ App shell (React 19)                                                   │
 │  ┌────────────┐  ┌──────────────────────────────────────────────────┐ │
 │  │ Sidebar    │  │ WorkspaceLayout = <Mosaic node=layoutStore.tree>  │ │
 │  │ useWork-   │  │   leaf = workspaceId → <TerminalPanel id>         │ │
 │  │ spaces()   │  │              │ useTerminal(id)                     │ │
 │  │ (TanStack  │  │              ▼                                     │ │
 │  │  poll)     │  │   xterm.js  ──input '0'+data / resize '1'+JSON──┐  │ │
 │  └─────┬──────┘  │             ◄── output '0'+data ────────────────┘  │ │
 │        │ click   │  init: send {AuthToken,columns,rows} as bytes     │ │
 │  StatusBar  ◄────┤  layoutStore (Zustand): MosaicNode tree + active  │ │
 │  NewWorkspaceModal│  reconcile(tree, liveWorkspaces) on load          │ │
 └────────┼─────────┴──────────────────────────┬────────────────────────┘
   HTTP /api/v1 (client.ts unwraps envelope)    │ WS /ws/workspaces/{id}/terminal
          │                                      │  subprotocol: (browser native)
          ▼                                      ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │ FastAPI control plane (uvicorn :8000)                                 │
 │  routers/workspaces.py (CRUD, exists)   routers/terminal.py (NEW)     │
 │     │ get_db / get_service                  │ get_db / get_compute    │
 │     ▼                                        ▼                         │
 │  WorkspaceService (saga, exists)      1. db.getWorkspace(id)           │
 │                                       2. if status != running:        │
 │                                            close(1008) BEFORE accept   │
 │                                       3. ws.accept(); dial ttyd        │
 │                                          connect(url, subprotocols=    │
 │                                            ["tty"], ping_interval=…)   │
 │                                       4. opaque dual-pump:             │
 │                                          up:  ws.iter_*()→ttyd.send    │
 │                                          down: ttyd→str?send_text:     │
 │                                                       send_bytes       │
 │                                          wait(FIRST_COMPLETED)+cancel  │
 │                                       5. logEvent connected/disconn.   │
 └──────────────────────────────────────────────┬───────────────────────┘
                                                 │ ws://{ws.lxc_ip}:7681/ws
                                                 ▼
                                        Worker ttyd (real)  — OR —
                                        stub ttyd WS server (CI/e2e),
                                        protocol-accurate `tty` framing
```

### Recommended Project Structure
```
ui/src/
├── api/
│   └── client.ts              # typed fetch wrapper; unwraps {data,meta,error}; throws ApiError on error!=null
├── types/
│   └── workspace.ts           # Workspace, WorkspaceStatus, WorkspaceCreate, ApiEnvelope<T>, TerminalState
├── hooks/
│   ├── useWorkspaces.ts       # TanStack Query: list (poll) + create/stop/start/destroy mutations
│   └── useTerminal.ts         # xterm + WS + FitAddon + ResizeObserver + reconnect lifecycle
├── store/
│   └── layoutStore.ts         # Zustand: mosaicNode tree, activeWorkspaceId, open/close/split + reconcile
├── lib/
│   └── ttyd.ts                # ttyd protocol constants + frame builders (init JSON, '0'+input, '1'+resize)
├── components/
│   ├── App.tsx                # QueryClientProvider + theme + shell
│   ├── TopBar.tsx             # brand, node capacity chips, theme switch, + New
│   ├── WorkspaceList.tsx      # sidebar rows + status dots (UI-01)
│   ├── WorkspaceLayout.tsx    # <Mosaic> bound to layoutStore (UI-02)
│   ├── TerminalPanel.tsx      # mounts useTerminal; header (split/detach/terminate); overlay
│   ├── NewWorkspaceModal.tsx  # form + boot-progress checklist (UI-03)
│   └── StatusBar.tsx          # counts + uptime + capacity (UI-04)
├── index.css                  # @import "tailwindcss"; @theme { design tokens }
└── main.tsx                   # createRoot
ui/tests/
├── integration/               # Tier-2 MSW renders (create flow, sidebar↔panel sync, reconnect overlay)
└── e2e/                        # Tier-3 Playwright specs
api/
├── routers/terminal.py        # NEW: the WS bridge
└── tests/integration/
    ├── conftest.py            # add a real stub-ttyd WS server fixture (asyncio websockets.serve)
    └── test_terminal_proxy.py # NEW: bridge tests over the protocol-accurate stub
```

### Pattern 1: Opaque, type-preserving `tty` bridge (the SC-7 fix)
**What:** The proxy negotiates `subprotocols=["tty"]` upstream and forwards every frame verbatim, preserving text-vs-binary. It never parses or re-encodes ttyd opcodes — the browser's xterm adapter already emits correct frames.
**When to use:** This is the only correct shape for the bridge; the spec's `msg.encode()` is the bug.
**Verified ttyd facts** (from ttyd source, 2026-06-10):
- Subprotocol string: `'tty'` — the browser opens `new WebSocket(url, ['tty'])`. `[VERIFIED: ttyd html client]`
- First client message: `JSON.stringify({ AuthToken, columns, rows })` sent as **encoded bytes** (the init/`JSON_DATA` frame, dispatched on leading `'{'`). `[VERIFIED: ttyd html client + server.h JSON_DATA '{']`
- Client command bytes: `INPUT '0'`, `RESIZE_TERMINAL '1'`, `PAUSE '2'`, `RESUME '3'`. `[VERIFIED: ttyd server.h]`
- Server command bytes: `OUTPUT '0'`, `SET_WINDOW_TITLE '1'`, `SET_PREFERENCES '2'`. `[VERIFIED: ttyd server.h]`

```python
# api/routers/terminal.py  — Source: ARCHITECTURE.md Pattern 4 + ttyd source (verified)
import asyncio
from fastapi import APIRouter, WebSocket
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

router = APIRouter(prefix="/ws")

@router.websocket("/workspaces/{workspace_id}/terminal")
async def terminal_proxy(websocket: WebSocket, workspace_id: str) -> None:
    db = get_db()  # DI seam; reuse main.get_db
    ws = await db.getWorkspace(workspace_id)
    # Close BEFORE accept for the policy-violation cases (SC-12 gating, SSRF guard).
    if ws is None or ws.status != "running" or not ws.lxc_ip:
        await websocket.close(code=1008)        # policy violation
        return

    await websocket.accept()                    # NOTE: do NOT pass subprotocol to the *browser* leg
    ttyd_url = f"ws://{ws.lxc_ip}:7681/ws"      # only the workspace's own IP (no arbitrary host — SSRF)
    try:
        async with connect(ttyd_url, subprotocols=["tty"], ping_interval=20, ping_timeout=20) as ttyd:
            await db.logEvent(workspace_id, "terminal.connected", {})

            async def up() -> None:             # browser → ttyd (frames already '0'/'1'-prefixed by xterm)
                async for msg in websocket.iter_bytes():
                    await ttyd.send(msg)

            async def down() -> None:           # ttyd → browser, PRESERVE frame type (SC-7)
                async for msg in ttyd:
                    if isinstance(msg, str):
                        await websocket.send_text(msg)
                    else:
                        await websocket.send_bytes(msg)

            tasks = {asyncio.create_task(up()), asyncio.create_task(down())}
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
            await asyncio.gather(*pending, return_exceptions=True)   # await the cancellations
    except (ConnectionClosed, OSError):
        # upstream ttyd unreachable / dropped — typed error frame then close (TERM-03)
        await websocket.send_json({"type": "error", "code": "LXC_NOT_READY"})
    finally:
        await db.logEvent(workspace_id, "terminal.disconnected", {})
        await websocket.close()
```
> Caveat to validate at plan time: `websocket.iter_bytes()` coerces all browser frames to bytes. ttyd's init message is a JSON string the browser sends as encoded bytes, and input is `'0'`+data (also bytes) — so `iter_bytes()` is correct for the **up** leg here because the xterm client sends binary. If the chosen xterm adapter sends the init as a *text* frame, use a frame-type-preserving receive on the up leg too (Starlette `websocket.receive()` returns `{"text"|"bytes"}`). The **down** leg must preserve type regardless. This is the exact spot the bug lives — Wave-0 test must assert both directions byte-for-byte.

### Pattern 2: `useTerminal` lifecycle (mount/open/fit/reconnect/dispose)
**What:** One hook owns xterm + WS + FitAddon + ResizeObserver. Returns `{ containerRef, state, attempt, reattach }`.
**When to use:** Every `TerminalPanel`. Cleanup is mandatory (Pitfall 15).
```ts
// ui/src/hooks/useTerminal.ts  — Source: xterm.js docs + PITFALLS.md Pitfall 15
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";

// frame builders — Source: ttyd server.h (verified)
const enc = new TextEncoder();
const initFrame = (cols: number, rows: number) =>
  enc.encode(JSON.stringify({ AuthToken: "", columns: cols, rows }));     // JSON_DATA
const inputFrame = (data: string) => {                                     // INPUT '0'
  const d = enc.encode(data); const f = new Uint8Array(d.length + 1);
  f[0] = 0x30 /* '0' */; f.set(d, 1); return f;
};
const resizeFrame = (cols: number, rows: number) =>                        // RESIZE_TERMINAL '1'
  enc.encode("1" + JSON.stringify({ columns: cols, rows }));

export function useTerminal(workspaceId: string, status: WorkspaceStatus) {
  // useEffect: new Terminal(); fitAddon = new FitAddon(); term.loadAddon(fitAddon);
  //   term.open(containerRef.current); fitAddon.fit();
  //   socket = new WebSocket(`/ws/workspaces/${workspaceId}/terminal`); socket.binaryType = "arraybuffer";
  //   onopen  → socket.send(initFrame(term.cols, term.rows)); setState("connected")
  //   onmessage → strip leading '0' (OUTPUT) → term.write(rest)   // server frames are '0'/'1'/'2'
  //   term.onData(d => socket.send(inputFrame(d)))
  //   ResizeObserver(debounced): if visible && nonzero → fitAddon.fit(); socket.send(resizeFrame(cols,rows))
  //   onclose → if code===1008 || status in {error,destroyed}: setState("error")  // DO NOT retry
  //             else: schedule reconnect with jittered backoff; setState("reconnecting")
  // cleanup: clearTimeout(backoff); observer.disconnect(); socket.close(); fitAddon.dispose(); term.dispose();
}
```
**Backoff (Claude's discretion):** `min(30000, 500 * 2 ** attempt) + random()*250` ms, cap 5 attempts before a terminal "error" state; reset `attempt` on a successful `onopen` (PITFALLS.md Pitfall 10 — jitter avoids thundering herd across panels).

### Pattern 3: `layoutStore` (Zustand) — tree + reconcile
```ts
// ui/src/store/layoutStore.ts  — Source: tech-spec §8.3 + PITFALLS.md Pitfall 15
import type { MosaicNode } from "react-mosaic-component";
interface LayoutStore {
  mosaicNode: MosaicNode<string> | null;
  activeWorkspaceId: string | null;
  setNode: (n: MosaicNode<string> | null) => void;       // <Mosaic onChange>
  openPanel: (id: string) => void;                       // add a leaf (split right by default)
  closePanel: (id: string) => void;                      // prune the leaf, rebalance
  splitPanel: (id: string, dir: "row" | "column") => void;
  setActive: (id: string) => void;
  reconcile: (liveIds: Set<string>) => void;             // drop leaves whose id is gone (UI-05)
}
// persist mosaicNode + activeWorkspaceId via zustand/middleware `persist` (localStorage).
// reconcile() runs on app load AFTER the first useWorkspaces success — server list is authoritative.
```
**Mosaic wiring:** `<Mosaic<string> value={mosaicNode} onChange={setNode} renderTile={(id, path) => <TerminalPanel id={id} path={path} />} />`. Import `react-mosaic-component/react-mosaic-component.css`. The `react-dnd` HTML5 backend is provided by `<MosaicWithoutDragDropContext>` + your own `DndProvider`, or use `<Mosaic>` which bundles the backend (confirm at plan time which export 6.2.0 ships).

### Pattern 4: Typed envelope client
```ts
// ui/src/api/client.ts  — Source: api/lib/envelope.py (the frozen contract)
interface ApiEnvelope<T> { data: T | null; meta: { requestId: string; timestamp: string }; error: { code: string; message: string } | null; }
export class ApiError extends Error { constructor(public code: string, message: string) { super(message); } }
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/v1${path}`, { headers: { "content-type": "application/json" }, ...init });
  const body = (await res.json()) as ApiEnvelope<T>;
  if (body.error) throw new ApiError(body.error.code, body.error.message);
  return body.data as T;                                  // data is non-null on success
}
```
> The backend returns camelCase JSON (`lxcIp`, `projectRepo`, `createdAt`); the TS `Workspace` type must use camelCase to match `model_dump(by_alias=True)`.

### Anti-Patterns to Avoid
- **Re-encoding ttyd frames in the proxy** (`msg.encode()`): corrupts text control frames → dead terminal. Forward `str`/`bytes` verbatim. (SC-7, Anti-Pattern 4.)
- **Bare `asyncio.gather` for the bridge:** half-open hang + leaked ttyd connection. Use `wait(FIRST_COMPLETED)` + cancel. (SC-10, Pitfall 10.)
- **Connecting the proxy to an arbitrary host:** only ever `ws://{ws.lxc_ip}:7681` from the looked-up workspace row — never a client-supplied host (SSRF, Security Domain).
- **`fitAddon.fit()` on a hidden/zero-size container:** sets the terminal to 1 column. Fit only when visible & non-zero, debounced. (Pitfall 15.)
- **Mirroring workspace status into Zustand:** drift. Status lives in TanStack Query only; Zustand holds layout. (Pitfall 11, ARCHITECTURE.md State Management.)
- **Bare echo stub ttyd in tests:** hides the framing bug. The stub MUST speak `tty` (negotiate the subprotocol, require the JSON init, echo `'0'`-prefixed). (Pitfall 3.)
- **`xterm-attach` addon:** no reconnect control. Hand-roll. (STACK.md.)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| WS client to ttyd from FastAPI | A raw asyncio socket / aiohttp | `websockets.asyncio.client.connect` (already in the tree via `uvicorn[standard]`) | Handles the subprotocol handshake, ping/pong, close codes correctly. |
| Terminal rendering / ANSI / cursor | A custom canvas terminal | `@xterm/xterm` | ANSI, reflow, selection, a11y are years of edge cases. |
| Fit cols/rows to a container | Manual `getBoundingClientRect` math | `@xterm/addon-fit` `FitAddon.fit()` | Computes cols/rows from cell metrics + container; the math is subtle. |
| Tiling/split/drag/resize panels | A custom flex/grid splitter | `react-mosaic-component` | Drag-drop, nested splits, resize handles, serializable tree — large surface. |
| Server-state caching/polling/invalidation | `useEffect` + `setInterval` + manual cache | `@tanstack/react-query` | Dedup, stale-time, refetchInterval, mutation invalidation built-in. |
| API mocking for UI tests | A hand-stubbed `fetch` | `msw` | Intercepts at the network layer; same handlers for tests + dev. |
| ttyd protocol framing | Re-deriving opcodes from scratch | The verified constants in this doc / a tiny `lib/ttyd.ts` | The values are fixed by ttyd source; centralize them once. |

**Key insight:** The entire terminal stack is "looks trivial, is not." Both the proxy (subprotocol + teardown) and the client (framing + fit + dispose) have a single correct shape that the spec gets wrong; the value is in matching the verified facts, not re-inventing them.

## Common Pitfalls

### Pitfall 1: The `.encode()` corruption (SC-7) — and a stub that hides it
**What goes wrong:** Forwarding ttyd text frames with `msg.encode()` (spec §6.4) silently turns a text control frame into binary; the terminal connects but is dead/garbled. A **bare-echo** test stub never exercises the subprotocol, so CI stays green while real ttyd breaks.
**Why it happens:** "WS proxy = copy bytes" is the obvious model; the framing is invisible until real ttyd.
**How to avoid:** Preserve frame type (`send_text`/`send_bytes`). Build a **protocol-accurate stub ttyd** (below) that negotiates `tty`, requires the JSON init, and echoes `'0'`-prefixed output. Assert byte-for-byte both directions.
**Warning signs:** Terminal connects but shows nothing; works against the echo stub, breaks against real ttyd.

### Pitfall 2: Half-open WS leak on teardown (SC-10)
**What goes wrong:** `gather` keeps both pumps alive until both finish; a dead browser leaves the ttyd pump hanging → leaked upstream connection, FD growth.
**How to avoid:** `wait(FIRST_COMPLETED)` → cancel pending → `gather(*pending, return_exceptions=True)`; `ping_interval` keepalive on the upstream `connect`.
**Warning signs:** Control-plane FD count climbs after disconnect/reconnect cycles. **Wave-0 test:** open then close the browser leg, assert the stub-ttyd sees its connection closed.

### Pitfall 3: FitAddon timing + dispose leaks (Pitfall 15)
**What goes wrong:** `fit()` on a hidden/0×0 panel → 1-column terminal; missing `dispose()`/`observer.disconnect()` leaks the terminal, WebGL/canvas context, WS, and ResizeObserver every panel close.
**How to avoid:** Fit only when visible & non-zero, debounced; every `useEffect` mount has a matching teardown closing WS + `term.dispose()` + `observer.disconnect()` + `fitAddon.dispose()`.
**Warning signs:** 1-column render after a split; memory/canvas-context count grows opening/closing panels. **Wave-0 test:** open+close 50 panels, assert flat ResizeObserver/teardown count (React StrictMode double-mount makes this essential).

### Pitfall 4: Poll-vs-WS drift (Pitfall 11)
**What goes wrong:** Sidebar (poll) shows `running` while the terminal WS just died; or a destroyed workspace lingers one poll interval and the user opens a panel against a gone container.
**How to avoid:** WS/terminal events are the fresher truth — on a terminal `error`/`close`, `queryClient.invalidateQueries(['workspaces'])`. On destroy, `setQueryData` to drop the row + `layoutStore.closePanel` immediately. Gate destructive buttons on server state (backend already rejects illegal transitions, SC-12).
**Warning signs:** Status lags the terminal by a poll cycle; opening a panel on a gone workspace.

### Pitfall 5: Boot-progress UX vs a synchronous create POST
**What goes wrong:** The design mockup shows an animated saga checklist (`Reserving VMID → Cloning → Starting → Waiting for Claude`), but v1's `POST /api/v1/workspaces` is **synchronous** — it blocks until `running` (or `error`) and returns the final row (confirmed: `workspaces.py` `create_workspace` returns `service.createWorkspace(payload)` directly; no `202`). There are no intermediate states streamed.
**Why it happens:** The mockup footnote even says `202 · polling status` — but the backend does not do that today.
**How to avoid:** v1 honest options: (a) show a single indeterminate "Creating… (cloning + booting, ~30-90s)" state driven by the mutation's `isPending`, then open the panel on success; or (b) display the staged checklist as **optimistic, time-based animation** (purely cosmetic) while the one request is in flight. Do NOT claim real per-step status the API doesn't expose. The async-`202`+poll migration is noted in ARCHITECTURE.md Data Flow and is a real future option — flag for the planner (Open Question Q2).
**Warning signs:** A modal that appears to track real steps but is faking them, or a request timeout if nginx/uvicorn read timeout < worst-case boot.

### Pitfall 6: react-mosaic version + CSS + dnd backend
**What goes wrong:** `^7` pulls the beta; forgetting the CSS import yields unstyled/zero-height panels; missing the react-dnd backend throws at render.
**How to avoid:** Pin `6.2.0` exact; `import "react-mosaic-component/react-mosaic-component.css"`; confirm whether to use `<Mosaic>` (bundles the HTML5 backend) vs `<MosaicWithoutDragDropContext>` + your own `DndProvider` in 6.2.0 at plan time.
**Warning signs:** Type errors from uuid 11; invisible panels; "Cannot have two HTML5 backends" if you double-wrap `DndProvider`.

### Pitfall 7: Reconnect-after-refresh has no scrollback (UI-05/SC-8)
**What goes wrong:** Operators expect their prior terminal output back after a refresh; ttyd has no replay buffer, so a fresh WS shows a blank-then-live terminal.
**How to avoid:** Document the limitation in the UI (the overlay copy already says "the session survives a tab close; this is detach, not terminate"). Reconnect attaches to the **live PTY** (requires the worker's ttyd to be persistent — the SC-8 drop-`--once` decision, owned by Phase 0/3, not this phase). v1 does not restore scrollback (WSX-03/v2).
**Warning signs:** Bug reports "my history is gone after refresh" — that's expected v1 behavior, not a defect.

## Code Examples

### Protocol-accurate stub ttyd (CI/e2e — the anti-bare-echo)
```python
# api/tests/integration/conftest.py (fixture)  — Source: ttyd protocol (verified) + Pitfall 3
import asyncio, json
import websockets  # the server side of the same lib

async def _stub_ttyd_handler(conn):
    # 1) subprotocol must be 'tty' (the proxy requested it)
    assert conn.subprotocol == "tty"
    # 2) first frame must be the JSON init (AuthToken/columns/rows)
    init = await conn.recv()
    payload = json.loads(init.decode() if isinstance(init, (bytes, bytearray)) else init)
    assert {"AuthToken", "columns", "rows"} <= payload.keys()
    # 3) echo input ('0'+data) back as OUTPUT ('0'+data); honor resize ('1'+JSON) silently
    async for msg in conn:
        raw = msg if isinstance(msg, (bytes, bytearray)) else msg.encode()
        if raw[:1] == b"0":            # INPUT → OUTPUT echo
            await conn.send(b"0" + raw[1:])
        # raw[:1] == b"1" → RESIZE; accept and ignore (no echo)

@pytest.fixture
async def stub_ttyd_ws():
    async with websockets.serve(_stub_ttyd_handler, "127.0.0.1", 0, subprotocols=["tty"]) as server:
        host, port = server.sockets[0].getsockname()[:2]
        yield f"ws://{host}:{port}"   # point the proxy's lxc_ip:7681 lookup at this for the test
```
> This stub deliberately enforces the subprotocol + init + framing, so a proxy that `.encode()`s or skips the subprotocol fails the test. The existing `conftest.py` respx mock covers only the **HTTP health GET** (saga step 6); this WS stub is a NEW, separate fixture for the bridge.

### Tailwind v4 wiring (no JS config)
```ts
// ui/vite.config.ts  — Source: STACK.md + tailwindcss.com/docs/installation/using-vite
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
export default defineConfig({ plugins: [react(), tailwindcss()] });
```
```css
/* ui/src/index.css — Source: design/_ds/colors_and_type.css + design prompt tokens */
@import "tailwindcss";
@theme {
  --color-bg: #1a1c1a;          /* dark hero page bg (design prompt) */
  --color-bg-surf: #212321;     /* cards / bars */
  --color-accent: #344734;      /* green-500 — ONLY primary interactive color */
  --color-gold: #f0a737;        /* prestige-only: stats, uptime, status dots, labels */
  --color-ok: #4ade80; --color-warn: #fbbf24; --color-err: #e05050;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;  /* terminals, branch chips, stats */
}
```
> Two token sources exist: the generic `_ds/colors_and_type.css` (warm-neutral, `--accent #21201d`) and the Burrow **design prompt** (forest-green, `--accent #344734`, gold prestige). The **design prompt + mockup are the binding contract** ("forest-tinted, gold prestige, green-only action"); the `_ds` file is the unbranded base it overrides. The UI-SPEC (generated next) is authoritative — see Open Question Q1.

## Runtime State Inventory

> Phase 2 is greenfield UI + a new backend router; no rename/migration. The only "live state" is client-side persisted layout.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | localStorage `mosaicNode` tree (Zustand persist) is the only persisted client state | reconcile against live workspace list on load (drop gone leaves, UI-05) — already in `layoutStore.reconcile` |
| Live service config | None — no external service config in this phase | none |
| OS-registered state | None | none |
| Secrets/env vars | The WS route reads `workspace.lxc_ip` from the DB; no new secret. `allowed_origin` (CORS) already in `config.py` | add a WS-origin check (Security Domain) using the same `allowed_origin` |
| Build artifacts | `ui/` is a bare scaffold (only `placeholder.ts`); Phase 2 adds real `package.json` deps + `vite.config.ts` + `index.html` (none exist yet) | full UI build setup; the scaffold's `tsconfig.json`/`biome.json` are reusable as-is |

**Nothing found in OS-registered / live-service-config categories:** None — verified by reading the Phase-0/1 file tree and configs.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| spec §6.4 `import websockets; websockets.connect(...)` | `from websockets.asyncio.client import connect`; `from websockets.exceptions import ConnectionClosed` | websockets 14+ | Legacy attribute paths deprecated; use the asyncio client API. |
| spec `react-mosaic-component@^7` | pin `6.2.0` exact (7 is `7.0.0-beta0` on `latest`) | ongoing | `^7` would pull a beta; React-19 works on stable 6.2.0. |
| spec `tailwind.config.ts` + PostCSS | `@tailwindcss/vite` + CSS `@theme` (no JS config) | Tailwind v4 | Drop the planned `tailwind.config.ts` from the §4.1 tree. |
| spec `@xterm/xterm ^5` / `xterm` unscoped | `@xterm/xterm@6` scoped (legacy `xterm` npm-deprecated) | xterm 6 | Use scoped packages; addon-fit 0.11, web-links 0.12. |
| spec WS `Reconnects internally (3 retries, 2s)` | reconnect is a **frontend** concern (jittered backoff in `useTerminal`); the proxy does NOT internally retry — it emits `LXC_NOT_READY` and closes | this phase | Keeps the proxy stateless; the client owns retry policy (TERM-06). |

**Deprecated/outdated:**
- `xterm` / `xterm-addon-*` unscoped packages: npm-deprecated → `@xterm/*`.
- The spec §6.4 proxy body (`.encode()`, bare `gather`, `ws://lxcIp:7681/ws` with no subprotocol): replaced by Pattern 1.
- The `--once` ttyd flag (kills sessions on disconnect): a Phase 0/3 boot-script decision, not this phase — but UI reconnect (TERM-06/UI-05) assumes it was dropped.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The xterm adapter sends the ttyd init + input as **binary** frames, so `websocket.iter_bytes()` on the proxy's up-leg is correct | Pattern 1 | If the adapter sends the init as a **text** frame, the up-leg must preserve type via `websocket.receive()`. Low risk (ttyd's own client encodes to bytes) but the Wave-0 test must assert it. |
| A2 | ttyd is reachable at `ws://{lxc_ip}:7681/ws` (path `/ws`) | Pattern 1, TERM-01 | The path is `/ws` in the spec + ttyd default; confirm against the pinned ttyd version in the dev homelab. Wrong path → 404 on connect → `LXC_NOT_READY`. |
| A3 | `POST /api/v1/workspaces` stays **synchronous** in Phase 2 (no `202`+poll) | Pitfall 5, UI-03 | If the planner adds async create, the modal's boot-progress changes from cosmetic to real polling. The backend would need a Phase-1 change (out of this phase's scope). |
| A4 | Node capacity ("X GB free") for the status-bar chips is NOT an existing API field | UI-04, Open Q3 | No `/api/v1/nodes` or capacity endpoint exists today; the status bar can show running/stopped counts + uptime from the list, but per-node free-RAM needs a new endpoint or must be dropped in v1. |
| A5 | The design prompt's forest-green/gold palette (not the generic `_ds` warm-neutral) is the binding visual contract | Tailwind wiring, Open Q1 | If the UI-SPEC resolves to the `_ds` tokens instead, the `@theme` values change. The UI-SPEC (generated next) is authoritative. |
| A6 | The design prompt's "auth-gated" phrasing is mockup boilerplate, NOT a v1 requirement | Security Domain | v1 is LAN-only **no-auth** by design (REQUIREMENTS Out of Scope, CLAUDE.md). Do NOT add login UI. Confirmed against REQUIREMENTS.md. |

**If this table is empty:** it is not — A1–A6 need confirmation (A3/A4/A1 are the load-bearing ones for the planner).

## Open Questions (RESOLVED)

1. **Which token palette is binding — design prompt (forest-green/gold) or generic `_ds` (warm-neutral)?**
   - What we know: the design prompt + `burrow-ui-mockup.html` describe forest-green `#344734` + gold prestige; the `_ds/colors_and_type.css` is an unbranded warm-neutral base meant to be overridden.
   - What's unclear: which the UI-SPEC (generated after this research) locks.
   - Recommendation: treat the **design prompt + mockup as authoritative** (it explicitly says "override everything"); seed `@theme` from it. Defer the final token table to the UI-SPEC.
   - RESOLVED: forest-green/gold per the binding 02-UI-SPEC Color Tokens (`--accent #344734`, gold prestige) — the `_ds` warm-neutral base is the override target, not the contract.

2. **Boot-progress: cosmetic staged animation, or migrate create to async `202`+poll?**
   - What we know: create is synchronous today; the mockup implies streamed steps.
   - Recommendation: ship cosmetic staged animation in Phase 2 (no backend change); record the `202`+poll migration as a future option (ARCHITECTURE.md already notes it). Surface to the planner before locking UI-03.
   - RESOLVED: cosmetic staged progress during the synchronous create POST (Plan 02-05); the async `202`+poll migration is deferred to v1.x.

3. **Node capacity for the status bar (UI-04) — new endpoint or drop the "GB free" chip?**
   - What we know: `getNodeMemory` exists on the ComputeProvider but is not exposed via any `/api/v1` route; the list endpoint has no node-capacity field.
   - Recommendation: v1 status bar shows running/stopped/error counts + session uptime from the workspace list; mark the per-node "GB free" chip as needing a small read-only `GET /api/v1/nodes` (or fold into `/health`) — flag to the planner as a scope decision (could defer to Phase 4 alongside the capacity work).
   - RESOLVED: add `GET /api/v1/nodes` (Plan 02-01) exposing `memoryUsedFraction`; the status bar shows the real used-memory fraction, not an invented "GB free" number.

4. **react-mosaic 6.2.0 dnd backend wiring (`<Mosaic>` vs `<MosaicWithoutDragDropContext>` + `DndProvider`)?**
   - Recommendation: verify the 6.2.0 exports at plan time and pick one path; do not double-wrap `DndProvider` (Pitfall 6).
   - RESOLVED: confirm the 6.2.0 `<Mosaic>` (bundled HTML5 backend) vs `<MosaicWithoutDragDropContext>` + own `DndProvider` export at implementation time (Plan 02-04 Pitfall); `react-mosaic-component` stays pinned `6.2.0` exact.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js + npm | UI build/test | assumed (dev box) | — | — |
| Python `websockets` | WS proxy upstream leg | ⚠ installed but stale | **14.1 in venv** (STACK.md pins **16.0**) | `uv add "websockets==16.0"` then re-lock; 14.1 still has `websockets.asyncio.client.connect` so it works, but pin to 16.0 for currency + the lockfile gate |
| `respx` | existing HTTP-ttyd-health mock (saga step 6) | ✓ (used in conftest) | per `api/pyproject.toml` | — |
| real ttyd | live terminal correctness | ✗ (no worker/Proxmox reachable) | — | protocol-accurate **stub ttyd WS server** (this doc) for CI/e2e; real ttyd is the dev-homelab smoke gate (deferred, `human_needed`) |
| Playwright browsers | Tier-3 e2e | ✗ (not installed) | — | `npx playwright install` in CI; specs run over FakeComputeProvider + stub ttyd |

**Missing dependencies with no fallback:** none block CI — the stub ttyd substitutes for real ttyd hermetically.
**Missing dependencies with fallback:**
- real ttyd → protocol-accurate stub ttyd (CI) + dev-homelab smoke (deferred).
- `websockets` 16.0 → 14.1 works but bump-and-lock to 16.0.

## Validation Architecture

> nyquist_validation is enabled (config.json `workflow.nyquist_validation: true`).

### Test Framework
| Property | Value |
|----------|-------|
| Framework (UI) | vitest 4.1.8 + @testing-library/react 16.3.2 + jsdom; msw 2.14.6 (Tier-2); @playwright/test 1.60.0 (Tier-3) |
| Framework (API) | pytest 9 + pytest-asyncio (async WS bridge tests); a new `websockets.serve` stub-ttyd fixture |
| Config file (UI) | `ui/vitest.config.ts` — **none yet (Wave 0)**; `playwright.config.ts` — **none yet (Wave 0)** |
| Config file (API) | `api/pyproject.toml` (pytest config exists) |
| Quick run command (UI) | `cd ui && npx vitest run src/**/*.test.tsx` |
| Quick run command (API) | `cd api && pytest tests/integration/test_terminal_proxy.py -x` |
| Full suite command | `cd api && pytest` ; `cd ui && npx vitest run && npx playwright test` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TERM-01 | Bridge relays both directions over the stub ttyd | integration (api) | `pytest tests/integration/test_terminal_proxy.py::test_bridges_both_directions -x` | ❌ Wave 0 |
| TERM-02 | Subprotocol `tty` negotiated; text frame preserved (no `.encode()`) | integration (api) | `pytest …::test_preserves_text_frame -x` | ❌ Wave 0 |
| TERM-03 | connect/disconnect events logged; `LXC_NOT_READY` frame when ttyd down | integration (api) | `pytest …::test_error_frame_when_ttyd_unreachable -x` | ❌ Wave 0 |
| TERM-04 | Closing one leg cancels the other; no leaked upstream | integration (api) | `pytest …::test_teardown_no_halfopen -x` | ❌ Wave 0 |
| TERM-04 | Non-running workspace rejected with close 1008 before accept | integration (api) | `pytest …::test_rejects_non_running -x` | ❌ Wave 0 |
| TERM-05 | FitAddon computes cols/rows; resize sends `'1'`+JSON | unit (ui) | `vitest run src/hooks/useTerminal.test.tsx -t fit` | ❌ Wave 0 |
| TERM-06 | Reconnect with backoff; overlay states; stop on 1008/error | unit (ui) | `vitest run src/hooks/useTerminal.test.tsx -t reconnect` | ❌ Wave 0 |
| TERM-07 | Unmount disposes term + WS + observer (open/close ×N, flat count) | unit (ui) | `vitest run src/hooks/useTerminal.test.tsx -t dispose` | ❌ Wave 0 |
| UI-01 | Sidebar renders polled statuses; dot color per status | integration (ui/MSW) | `vitest run src/components/WorkspaceList.test.tsx` | ❌ Wave 0 |
| UI-02 | Mosaic open/split/close updates the tree | unit (ui) | `vitest run src/store/layoutStore.test.ts` | ❌ Wave 0 |
| UI-03 | Create flow: form → POST → panel opens (MSW) | integration (ui/MSW) | `vitest run src/components/NewWorkspaceModal.test.tsx` | ❌ Wave 0 |
| UI-04 | Status bar derives counts from the list | unit (ui) | `vitest run src/components/StatusBar.test.tsx` | ❌ Wave 0 |
| UI-05 | layoutStore.reconcile drops gone leaves; reconnect opens fresh WS | unit (ui) | `vitest run src/store/layoutStore.test.ts -t reconcile` | ❌ Wave 0 |
| TERM/UI e2e | create → terminal echoes → split/drag → detach→reconnect → terminate | e2e (Playwright) | `playwright test tests/e2e/terminal.spec.ts` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** the quick run for the touched layer (`vitest run <file>` or `pytest <file> -x`).
- **Per wave merge:** `cd api && pytest` + `cd ui && npx vitest run`.
- **Phase gate:** full suite green (api pytest + ui vitest + Playwright e2e) before `/gsd:verify-work`.

### Wave 0 Gaps
- [ ] `api/tests/integration/test_terminal_proxy.py` — TERM-01..04 over the stub ttyd
- [ ] `api/tests/integration/conftest.py` — add the `stub_ttyd_ws` (`websockets.serve`, `tty` subprotocol) fixture
- [ ] `ui/vitest.config.ts` + `ui/tests/setup.ts` (jest-dom, jsdom env) — none exist
- [ ] `ui/playwright.config.ts` + `docker-compose.e2e.yml` wiring (FakeComputeProvider + stub ttyd) — none exist
- [ ] `ui/src/**/__mocks__` or MSW handlers for `/api/v1/workspaces` (list/create/get) + a mock `WebSocket` for `useTerminal`
- [ ] Framework install: `vitest@4.1.8`, `@testing-library/*`, `msw@2.14.6`, `jsdom`, `@playwright/test@1.60.0`; `uv add websockets==16.0`

## Security Domain

> security_enforcement enabled (config.json), ASVS level 1, block_on=high. The WS terminal proxy is the one new ASVS-relevant surface this phase adds. v1 is LAN-only no-auth **by design** (REQUIREMENTS Out of Scope) — do NOT add auth; do enforce the in-scope controls.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | v1 LAN-only no-auth by design (REQUIREMENTS); the design prompt's "auth-gated" is boilerplate (A6) |
| V3 Session Management | no | no sessions/tokens in v1 |
| V4 Access Control | yes | WS route gates on `workspace.status == "running"` + the workspace must exist (close 1008 before accept). No client-supplied target host. |
| V5 Input Validation | yes | `workspace_id` is a path param; the upstream URL is built ONLY from the DB row's `lxc_ip` (never client input) — prevents SSRF. ttyd frames are forwarded opaquely (no parsing → no injection surface in the proxy). |
| V6 Cryptography | no | LAN plaintext WS by design (nginx terminates; no secrets on the terminal channel) |
| V7 Error/Logging | yes | already enforced repo-wide: `logEvent` writes only non-secret event types; the proxy logs `terminal.connected/disconnected` with `{}` data — no IPs/tokens in events. |

### Known Threat Patterns for the WS proxy

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SSRF — proxy dialed to an attacker-chosen host | Tampering / Info disclosure | Build `ttyd_url` ONLY from the looked-up `workspace.lxc_ip`; never from a query param, header, or sub-path. The only reachable target is the workspace's own VMID-derived static IP (ADR-0004). |
| Connect to a non-running / non-existent workspace | Elevation / DoS | `db.getWorkspace` + `status == "running"` check **before** `accept`; reject with `close(1008)`. Mirrors the SC-12 server-side gate. |
| Cross-origin WS hijack (CSWSH) | Spoofing | WS does not honor CORS automatically — add an explicit `Origin`-header check against `settings.allowed_origin` (the same non-`*` LAN origin `main.py` already enforces for HTTP) and `close(1008)` on mismatch. |
| Writable root shell exposed beyond the LAN | Elevation | The LAN boundary is the only control (Pitfall 12); document it. Bind uvicorn to the LAN interface only (deployment precondition, not phase code). |
| Half-open leak as a resource-exhaustion vector | DoS | `FIRST_COMPLETED`+cancel teardown + `ping_interval` keepalive (TERM-04) bounds FD growth. |
| Secret/IP leakage via terminal events | Info disclosure | `terminal.connected/disconnected` events carry `{}` only; never log `lxc_ip` or frame contents. (Consistent with the repo's `_safe` redaction discipline.) |

**Net new security task for the planner:** add an `Origin`-header gate on the WS route (CSWSH mitigation) using `settings.allowed_origin`; everything else (SSRF guard, status gate, teardown) falls out of Patterns 1-2.

## Sources

### Primary (HIGH confidence)
- ttyd source (`src/server.h`, `src/protocol.c`, `html/src/components/terminal/xterm/index.ts`) — subprotocol `'tty'`; `INPUT '0'`, `RESIZE_TERMINAL '1'`, `PAUSE '2'`, `RESUME '3'`, `JSON_DATA '{'`; server `OUTPUT '0'`, `SET_WINDOW_TITLE '1'`, `SET_PREFERENCES '2'`; init `{AuthToken,columns,rows}`. Fetched 2026-06-10.
- Burrow Phase-0/1 code (authoritative contracts): `api/main.py` (DI seams, CORS, error envelope), `api/routers/workspaces.py` (synchronous create), `api/routers/internal.py` (threat-model pattern, source-IP gate), `api/models/workspace.py` (`lxc_ip`, camelCase via `CamelModel`), `api/services/workspaceService.py` (status, `_wait_ttyd`, redaction), `api/lib/envelope.py` / `lib/statemachine.py`, `api/tests/integration/conftest.py` (respx HTTP stub pattern), `ui/package.json` / `tsconfig.json` / `biome.json` (scaffold pins).
- Burrow `.planning/research/` — SUMMARY (SC-7/SC-10), ARCHITECTURE (Pattern 4 WS bridge, Anti-Pattern 4), PITFALLS (Pitfall 3/10/11/15), STACK (pinned versions + peer-compat), `docs/ci-cd-and-testing.md` §4.3-4.4 (MSW / Playwright / FakeComputeProvider + stub ttyd).
- npm registry / PyPI (2026-06-10): xterm 6.0.0, addon-fit 0.11.0, addon-web-links 0.12.0, react-mosaic-component 6.2.0 (peer `react 16-19`; `latest`=7.0.0-beta0), react-dnd 16.0.1, @tanstack/react-query 5.101.0, zustand 5.0.14, msw 2.14.6 (postinstall confirmed), vitest 4.1.8, vite 8.0.16, @vitejs/plugin-react 6.0.2 (peer `vite ^8.0.0`), @tailwindcss/vite 4.3.0, websockets (PyPI) 16.0 latest.
- Design handoff: `docs/design/burrow-ui-design-prompt.md`, `design/Burrow-handoff/.../colors_and_type.css`.

### Secondary (MEDIUM confidence)
- tailwindcss.com/docs/installation/using-vite — v4 `@tailwindcss/vite` + CSS `@theme` (cited via STACK.md).
- websockets.readthedocs.io — `websockets.asyncio.client.connect` is the current API (cited via STACK.md).

### Tertiary (LOW confidence)
- None load-bearing. Real-ttyd path correctness (`/ws`, persistent ttyd) and the dev-homelab smoke are explicitly deferred (`human_needed`).

## Metadata

**Confidence breakdown:**
- ttyd protocol (SC-7 framing): HIGH — read directly from current ttyd source (subprotocol, command bytes, init message all quoted).
- Standard stack: HIGH — every version + peer re-verified live on npm/PyPI 2026-06-10; matches frozen STACK.md.
- Architecture/patterns (proxy + UI): HIGH — proxy pattern is the committed ARCHITECTURE Pattern 4; UI builds on read backend contracts.
- Pitfalls: HIGH — all from the project PITFALLS.md, cross-checked against the actual code.
- Boot-progress / capacity / palette: MEDIUM — three real product/scope decisions (Open Q1-3) the planner must resolve; flagged, not assumed.

**Research date:** 2026-06-10
**Valid until:** 2026-07-10 (stack is fast-moving; re-verify mosaic 6.2.0 vs a potential 7.0.0 stable and websockets/xterm minor bumps if planning slips a month)
