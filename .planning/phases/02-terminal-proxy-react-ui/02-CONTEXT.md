<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Phase 2: Terminal Proxy + React UI - Context

**Gathered:** 2026-06-10
**Status:** Ready for planning
**Mode:** Auto (autonomous) — grey areas pre-decided by the SC corrections, the Phase-0/1 contracts, STACK.md, and the committed design handoff. No new grey-area prompts.

<domain>
## Phase Boundary

Phase 2 makes workspaces interactive in the browser: the **backend WebSocket terminal proxy** (browser ↔ FastAPI ↔ the worker's ttyd) and the **tiling React UI**. In scope: the `tty`-subprotocol-aware WS bridge (TERM-01..04), the xterm.js terminal panel with fit/reconnect/dispose (TERM-05..07), the react-mosaic tiling layout (UI-02), the workspace sidebar with live status (UI-01), the New Workspace modal with boot-progress (UI-03), the status bar (UI-04), and reconnect-after-refresh to a live session (UI-05). Out of scope: the event-drawer (UI-06 → Phase 4), the worker pull-step (Phase 3), reaper/auto-stop/release (Phase 4).

Requirements owned: TERM-01, TERM-02, TERM-03, TERM-04, TERM-05, TERM-06, TERM-07, UI-01, UI-02, UI-03, UI-04, UI-05.
</domain>

<decisions>
## Implementation Decisions

### Backend WS terminal proxy (TERM-01..04 — SC-7, SC-10)
- A FastAPI WebSocket route `/ws/workspaces/{id}/terminal`: accept the browser WS, open the upstream ttyd WS with the **`tty` subprotocol negotiated** (`subprotocols=["tty"]`), and **relay frames opaquely both directions preserving text-vs-binary** — do NOT `.encode()` text frames (SC-7 fixes the spec §6.4 corruption bug). ttyd's framing (input `'0'`-prefix, resize `'1'`+JSON) passes through untouched from the xterm adapter.
- Upstream leg uses the `websockets` client lib (FastAPI has no WS client); browser leg is native Starlette WS.
- **Teardown** (SC-10): bridge the two directions with `asyncio.wait(FIRST_COMPLETED)` + cancel the loser; no half-open leak, no FD growth. Log `terminal.connected`/`terminal.disconnected` events; emit a typed `{"type":"error","code":"LXC_NOT_READY"}` frame when ttyd is unreachable, and close only running workspaces (reject non-running with a close code).

### xterm.js terminal panel (TERM-05..07)
- `@xterm/xterm` 6 + `@xterm/addon-fit`; mount on a div ref, open the WS, `FitAddon` fits/reflows on container resize (ResizeObserver), the input/resize adapter drives a real claude TUI (not stuck 80x24). **Auto-reconnect with jittered backoff + a visible reconnecting overlay** (TERM-06); stop retrying on `error`/`destroyed`. **Unmount cleanly** (TERM-07): close WS, dispose terminal, disconnect ResizeObserver.

### Tiling layout (UI-02) + state
- `react-mosaic-component` **6.2.0** (React-19 compatible — NOT the 7.0.0-beta on `latest`). A Zustand `layoutStore` holds the Mosaic tree + active workspace; open/split(H/V)/drag/resize; persist the tree and **reconcile it against the live workspace list** on load (drop panels for gone workspaces).

### UI surfaces (UI-01/03/04/05)
- Sidebar (UI-01): TanStack Query polls `GET /api/v1/workspaces`; live status chips (creating/running/stopped/error).
- New Workspace modal (UI-03): name/repo/branch/node form → `POST /api/v1/workspaces`; shows live boot-progress states; opens the panel on success.
- Status bar (UI-04): running/stopped counts, session uptime, node capacity.
- Restore-after-refresh (UI-05): on load, reconnect the terminal of a still-`running` workspace to its **live** session — **no fresh process, no scrollback restore in v1** (documented limitation; full scrollback is v2/WSX-03).

### Stack (STACK.md pins; ADR-0008)
- Vite 8, React 19, TypeScript 6, Tailwind v4 via `@tailwindcss/vite` (no `tailwind.config.ts`), `@biomejs/biome` 2, Zustand 5, `@tanstack/react-query` 5, `@xterm/xterm` 6 + `@xterm/addon-fit`, `react-mosaic-component` 6.2.0. Tests: vitest 4 + Testing Library, MSW (mock `/api/v1`), Playwright (e2e over the FakeComputeProvider). A typed `client.ts` fetch wrapper unwraps the `data`/`meta`/`error` envelope.

### Design
- Honor the committed design handoff: `docs/design/burrow-ui-mockup.html`, `docs/design/burrow-ui-design-prompt.md`, and `design/Burrow-handoff/burrow/project/` (mockup + `_ds` colors/type tokens). The UI-SPEC (generated next) is the binding visual contract.

### Claude's Discretion
- Component file layout under `ui/src/` (follow tech-spec §4.1: components/, hooks/, store/, api/, types/), the exact backoff curve, and the stub-ttyd test double's shape are at Claude's discretion within the above.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- Backend (Phase 1): `api/main.py` factory (register the WS route + extend CORS for WS), `api/routers/*`, `api/services/workspaceService.py` (getWorkspace/status), `api/db`/`api/compute` providers, the envelope. `FakeComputeProvider` + the stub-ttyd test pattern make the proxy + UI e2e-testable with zero real infra.
- Frontend (Phase 0): minimal `ui/` scaffold (Vite 8 / TS 6 / Biome 2 configs + package.json + lockfile) — Phase 2 builds the real app on it.

### Established Patterns (CLAUDE.md — non-negotiable)
- `/api/v1` REST + `/ws/*` WebSocket; standard envelope; provider seams abstract; SPDX on every file; structured logging; security headers; LAN-only no-auth; Conventional Commits; failing-first tests.

### Integration Points
- The WS route bridges to ttyd at the worker's static IP (from VMID); the UI's `useTerminal` hook owns the xterm+WS lifecycle; `useWorkspaces` owns the TanStack Query list+mutations; `layoutStore` owns the Mosaic tree.
</code_context>

<specifics>
## Specific Ideas

The `tty` subprotocol bridge is the crux (SC-7): the spec's raw-passthrough-with-`.encode()` produces a dead terminal. Negotiate `subprotocols=["tty"]` and relay opaquely. The CI stub-ttyd MUST be protocol-accurate (the `tty` framing), not a bare echo, or it hides the bug (Pitfall). Real terminal correctness against real ttyd is the dev-homelab smoke gate.
</specifics>

<deferred>
## Deferred Ideas

- Real ttyd `tty` handshake + a live claude TUI against a real worker → dev-homelab smoke gate (no Proxmox/worker reachable from this box) — `human_needed`, not phase-blocking.
- Event-log activity drawer (UI-06) → Phase 4. Full terminal scrollback restore → v2 (WSX-03).
</deferred>
