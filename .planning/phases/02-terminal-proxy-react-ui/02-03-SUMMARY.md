<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 02-terminal-proxy-react-ui
plan: 03
subsystem: ui
tags: [xterm, websocket, ttyd, terminal, reconnect, fit-addon, resize-observer, tanstack-query, react, tdd, mvp]

# Dependency graph
requires:
  - phase: 02-terminal-proxy-react-ui (plan 01)
    provides: "the /ws/workspaces/{id}/terminal WS bridge contract (opaque tty relay, 1008 pre-accept reject, {type:error,code:LXC_NOT_READY} frame) the hook connects to"
  - phase: 02-terminal-proxy-react-ui (plan 02)
    provides: "the typed envelope client api<T>(), camelCase Workspace/TerminalState types, the verified ttyd frame builders (initFrame/inputFrame/resizeFrame + ServerCommand opcodes), the four-theme @theme token sheet, and the MSW /api/v1 harness"
provides:
  - "useTerminal(workspaceId, status, options) — the xterm.js + WebSocket + FitAddon + ResizeObserver + jittered-reconnect lifecycle hook returning {containerRef, status, reconnectAttempts, reattach} (TERM-05/06/07)"
  - "TerminalPanel — the mounting panel (36px header + .term body) with connecting/reconnecting/error overlays per the UI-SPEC contract"
  - "useWorkspaces — TanStack Query list poll (refetchInterval 3000) + create/stop/start/destroy mutations + useInvalidateWorkspaces (Pitfall-4 reconciliation)"
  - "one-panel App MVP shell rendering a live terminal for the first running workspace"
  - "reusable test doubles: mock WebSocket, mock xterm Terminal/FitAddon, mock ResizeObserver (importable by later UI plans)"
affects: [02-04, 02-05, 02-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "useTerminal owns the whole terminal lifecycle in one effect with ref-held resources (term/fit/socket/observer/timer) so teardown is idempotent under StrictMode double-mount (no leaks, TERM-07)"
    - "Jittered exponential backoff (min(30000, 500*2^n)+random()*250, cap 5, reset on onopen) behind a visible reconnecting overlay; stop-on-terminal rule on close 1008 / LXC_NOT_READY frame (no retry) (TERM-06)"
    - "Debounced ResizeObserver fit (only when visible & non-zero) that drives the ttyd '1'+JSON resize frame so the TUI reflows (never stuck 80x24) (TERM-05)"
    - "ttyd frames sent as a fresh-ArrayBuffer copy to satisfy the TS6 BufferSource generic (Uint8Array widened over ArrayBufferLike)"
    - "Terminal-event reconciliation decoupled via an onTerminalEvent callback the panel wires to queryClient.invalidateQueries(['workspaces']) — the hook stays provider-free and unit-testable (Pitfall 4)"
    - "xterm + FitAddon + ResizeObserver mocked in vitest (jsdom can't lay out xterm) so the hook/component logic is proven over a controlled WebSocket"

key-files:
  created:
    - ui/src/hooks/useTerminal.ts
    - ui/src/hooks/useWorkspaces.ts
    - ui/src/components/TerminalPanel.tsx
    - ui/src/hooks/useTerminal.test.tsx
    - ui/src/hooks/useWorkspaces.test.tsx
    - ui/src/components/TerminalPanel.test.tsx
    - ui/tests/helpers/mockWebSocket.ts
    - ui/tests/helpers/mockXterm.ts
    - ui/tests/helpers/resizeObserver.ts
  modified:
    - ui/src/App.tsx

key-decisions:
  - "App stayed at ui/src/App.tsx (not the plan's ui/src/components/App.tsx) so the existing main.tsx import of ./App keeps working — moving it would orphan the entry point. Rule 3 blocking adjustment."
  - "useTerminal exposes reattach() (additive to the planned {containerRef, status, reconnectAttempts}) to back the overlay's Reattach/Retry buttons the UI-SPEC requires."
  - "Terminal→list reconciliation is wired via an onTerminalEvent callback rather than calling useQueryClient inside useTerminal, keeping the hook usable in tests without a QueryClientProvider."
  - "xterm/FitAddon/ResizeObserver are mocked in tests (jsdom has no real layout); the WebSocket is a controllable double — render/echo/fit/reconnect/dispose are all CI-provable without real infra."

patterns-established:
  - "Reusable mock WebSocket + mock xterm + mock ResizeObserver helpers under ui/tests/helpers/ that later panel/terminal tests import"
  - "Single-effect, ref-held resource lifecycle with an idempotent teardown proven flat over 50 mount/unmount cycles"

requirements-completed: [TERM-05, TERM-06, TERM-07]
requirements-partial: [UI-01]

# Metrics
duration: 16min
completed: 2026-06-10
---

# Phase 2 Plan 03: MVP Terminal Vertical Slice Summary

**The MVP slice: a real xterm.js terminal that mounts on a `TerminalPanel`, connects through the Wave-1 `/ws/workspaces/{id}/terminal` bridge, echoes typed input over the verified ttyd frames, fits/reflows on resize, auto-reconnects with jittered backoff behind the spec reconnecting overlay (stopping on 1008 / LXC_NOT_READY), and disposes cleanly with no leaks — plus the shared `useWorkspaces` poll and a one-panel `App` shell. TERM-05/06/07 done; UI-01 poll foundation in place.**

## Performance

- **Duration:** ~16 min
- **Completed:** 2026-06-10
- **Tasks:** 3 (Tasks 2 + 3 TDD)
- **Files:** 9 created, 1 modified

## Accomplishments

- **`useTerminal` (TERM-05/06/07)** — one hook owning the xterm.js + WebSocket + FitAddon + ResizeObserver lifecycle. On a running workspace it opens xterm on the div ref, fits, connects the bridge (`binaryType="arraybuffer"`), sends the `initFrame` on open, strips the leading `'0'` OUTPUT opcode and writes the rest, and sends an `inputFrame` (`'0'`+data) on typed data. A debounced `ResizeObserver` fits only when visible/non-zero and sends the `resizeFrame` (`'1'`+JSON) so the TUI reflows (never stuck 80×24). An unexpected close schedules a reconnect with jittered exponential backoff (`min(30000, 500*2^n)+random()*250`, cap 5, reset on reopen) driving `connecting→open→reconnecting→error` + `reconnectAttempts`; it does NOT retry on close `1008` or an `LXC_NOT_READY` error frame (status `error`). Teardown clears the timer, disconnects the observer, closes the socket, and disposes the addon + terminal — idempotent under StrictMode double-mount.
- **`TerminalPanel`** — the 36px header (drag grip, name, branch chip, gold model label, split/detach/terminate inline-SVG icon buttons wired to optional no-op props) over a `.term` body div bound to `containerRef`, token-styled. Renders the three UI-SPEC overlays per `status`: `connecting` (spinner + "Connecting…"), `reconnecting` (gold-top spinner + verbatim `reconnecting… attempt {n} / 5` + `Reattach`, `role="status" aria-live="polite"`), `error` (non-spinning `--err` glyph + `Session unavailable. {reason}.` + `Retry`, `role="alert" aria-live="assertive"`).
- **`useWorkspaces` (UI-01 poll)** — TanStack Query list poll (`refetchInterval` 3000) + `create/stop/start/destroy` mutations that invalidate `['workspaces']`, plus `useInvalidateWorkspaces` the panel wires to its `onTerminalEvent` so a terminal error/close refetches the list (Pitfall-4 reconciliation).
- **One-panel `App` shell** — `useWorkspaces` finds the first running workspace and renders its `TerminalPanel` (with the terminal-event invalidation wired); an empty-state otherwise. The real Mosaic tiling is Wave 3.
- **Reusable test doubles** — a controllable mock `WebSocket` (captures sent frames, `emitOpen/emitMessage/emitOutput/emitClose/emitError`, honors `arraybuffer`), a mock xterm `Terminal`/`FitAddon` (records write/onData/fit/dispose + live counts), and a mock `ResizeObserver` (live-count for the leak assertion) — importable by later UI plans.

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED):** failing happy-path tests + mock WS/xterm/ResizeObserver helpers — `35948b4` (test)
2. **Task 2 (GREEN):** useTerminal core + TerminalPanel + one-panel App — `ea58fc4` (feat)
3. **Task 3:** harden — fit/reflow, jittered reconnect + overlays, clean dispose, useWorkspaces poll — `fd59d68` (feat)

**Plan metadata:** committed with this SUMMARY + STATE/ROADMAP/REQUIREMENTS updates (docs).

## Files Created/Modified

- `ui/src/hooks/useTerminal.ts` — xterm + WS + FitAddon + ResizeObserver + jittered-reconnect lifecycle hook
- `ui/src/hooks/useWorkspaces.ts` — TanStack Query list poll + create/stop/start/destroy mutations + useInvalidateWorkspaces
- `ui/src/components/TerminalPanel.tsx` — mounting panel + header + connecting/reconnecting/error overlays
- `ui/src/App.tsx` — one-panel MVP shell (first-running-workspace terminal)
- `ui/src/hooks/useTerminal.test.tsx` — happy-path + fit + reconnect + stop-on-terminal + dispose (50-cycle leak) tests
- `ui/src/hooks/useWorkspaces.test.tsx` — MSW list poll + refetchInterval + invalidation tests
- `ui/src/components/TerminalPanel.test.tsx` — mount/connect/echo/type + connecting/reconnecting/error overlay tests
- `ui/tests/helpers/mockWebSocket.ts` / `mockXterm.ts` / `resizeObserver.ts` — reusable test doubles

## Decisions Made

- **App kept at `ui/src/App.tsx`** (not the plan's `components/App.tsx`) so `main.tsx`'s `./App` import keeps resolving — a Rule-3 blocking adjustment, documented as a deviation.
- **`reattach()` added to `UseTerminalResult`** (additive) to back the overlay Reattach/Retry buttons the UI-SPEC mandates.
- **Terminal→list reconciliation via an `onTerminalEvent` callback** instead of calling `useQueryClient` inside the hook — keeps `useTerminal` provider-free and unit-testable; the panel/App owns the invalidation.
- **xterm/FitAddon/ResizeObserver mocked in tests** — jsdom can't lay out xterm; the WebSocket double makes render/echo/fit/reconnect/dispose CI-provable with zero real infra (the real ttyd/live-claude echo is the deferred dev-homelab smoke).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] App authored at `ui/src/App.tsx`, not the plan's `ui/src/components/App.tsx`**
- **Found during:** Task 2
- **Issue:** The plan's `files_modified` listed `ui/src/components/App.tsx`, but the app entry (`ui/src/main.tsx`) imports `./App` from `ui/src/App.tsx` (the existing placeholder). Creating a divergent `components/App.tsx` would orphan the real entry point and leave the placeholder rendering.
- **Fix:** Rewrote the existing `ui/src/App.tsx` into the one-panel shell; `main.tsx` continues to import `./App` unchanged.
- **Files modified:** ui/src/App.tsx
- **Commit:** ea58fc4 (Task 2)

**2. [Rule 3 - Blocking] `Object.defineProperty` to install the mock WebSocket/ResizeObserver globals**
- **Found during:** Task 2 (first GREEN test run)
- **Issue:** jsdom defines `WebSocket` as a read-only accessor, so `globalThis.WebSocket = MockWebSocket` threw `Cannot assign to read only property`.
- **Fix:** Install both mocks via `Object.defineProperty(globalThis, name, { configurable, writable, value })`.
- **Files modified:** ui/tests/helpers/mockWebSocket.ts, ui/tests/helpers/resizeObserver.ts
- **Commit:** ea58fc4 (Task 2)

**3. [Rule 1 - Bug] TS6 `Uint8Array<ArrayBufferLike>` vs `BufferSource` on `socket.send`**
- **Found during:** Task 2 (tsc)
- **Issue:** TypeScript 6's lib widens `Uint8Array` over `ArrayBufferLike` (which may be `SharedArrayBuffer`), so passing a raw ttyd frame to `socket.send()` failed the `BufferSource` parameter type.
- **Fix:** A `sendFrame` helper copies the frame bytes into a fresh `Uint8Array` and sends its `.buffer` (a plain `ArrayBuffer`); the mock WebSocket normalizes ArrayBuffer→Uint8Array so byte assertions are unchanged.
- **Files modified:** ui/src/hooks/useTerminal.ts, ui/tests/helpers/mockWebSocket.ts
- **Commit:** ea58fc4 (Task 2)

**4. [Rule 1 - Bug] Task-1 init assertion hardcoded `columns: 80` despite a pre-connect fit**
- **Found during:** Task 2 (GREEN)
- **Issue:** The hook fits before connecting, so the init frame reflects the fitted grid (the whole point of TERM-05 — not stuck 80×24). The RED assertion's literal `columns: 80` was wrong for correct GREEN behavior.
- **Fix:** Assert the init shape — `AuthToken: ""` + numeric `columns`/`rows` — rather than a stuck dimension.
- **Files modified:** ui/src/hooks/useTerminal.test.tsx
- **Commit:** ea58fc4 (Task 2)

---

**Total deviations:** 4 auto-fixed (2 blocking, 2 bug). No scope creep — each made the slice correct or the plan's own verification pass.

## Known Stubs

- **One-panel `App` shell** — renders a single `TerminalPanel` for the first running workspace; the full top-bar / sidebar / react-mosaic grid / status-bar shell is Waves 3-4 (02-04/05). Documented scope, not a hidden stub.
- **Panel icon buttons (split/detach/terminate)** — wired to optional no-op props; Wave 3/4 connects them to `layoutStore`/the destroy mutation. Documented in the plan.
- **`useWorkspaces` mutations (create/stop/start/destroy)** — implemented and list-invalidating, but not yet wired to UI (the modal/sidebar that consume them land in 02-05). Not stubs — fully functional hooks awaiting their callers.

## Validation

Full UI gate green (Windows, npm):

- `npx vitest run` — **32 passed** (11 baseline + 21 new across useTerminal/useWorkspaces/TerminalPanel).
- `npx vitest run src/hooks src/components` — 21 passed (the plan's scoped command).
- `npx tsc --noEmit` — clean.
- `npx biome ci .` — 24 files, no fixes.
- `npm run build` — built (informational >500 kB chunk note; code-splitting deferred, out of scope).
- `uvx --with charset-normalizer reuse lint` — compliant (195/195; SPDX on every new tsx/ts).

Behaviors proven over the mocked WebSocket + xterm: mount → connect → init → echo OUTPUT → type inputFrame; fit-on-resize reflows + sends a resize frame; drop → reconnecting overlay with the attempt counter + Reattach, attempt reset on reopen; no retry on close 1008 / LXC_NOT_READY → error overlay + Retry; unmount disposes flat over 50 cycles; useWorkspaces polls the seeded list + invalidation refetches.

## User Setup Required

None — no external service configuration required (v1 is LAN-only no-auth). The real ttyd `tty` handshake + a live claude TUI echo/resize against a real worker is the deferred dev-homelab smoke gate (`human_needed`, not phase-blocking); the vitest suite proves the hook/component logic over a mocked WebSocket.

## Next Phase Readiness

- `useTerminal`/`TerminalPanel` are the panel Wave 3 (02-04) drops into react-mosaic tiles; `useWorkspaces` is the shared list/mutation surface the sidebar (UI-01 rows), the New Workspace modal (UI-03), and the status bar (UI-04) consume in 02-05.
- The reusable test doubles (mock WebSocket/xterm/ResizeObserver) are importable by the Mosaic + sidebar tests.
- UI-01 is partial: the polling foundation (`useWorkspaces`) is done; the sidebar rows that render it land in 02-05. TERM-05/06/07 are complete.

## Self-Check: PASSED

(see appended self-check below)

---
*Phase: 02-terminal-proxy-react-ui*
*Completed: 2026-06-10*
