<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

---
phase: 02-terminal-proxy-react-ui
verified: 2026-06-10T18:50:00Z
status: human_needed
score: 5/5 must-haves verified (CI-provable); real-infra acceptance deferred to dev-homelab smoke
overrides_applied: 0
human_verification:
  - test: "Open a real workspace terminal against a live ttyd on a real Proxmox worker; type a `claude` command."
    expected: "The live Claude Code TUI renders, reflows to the panel size (not stuck at 80x24), and input/output round-trips through the real `tty` handshake + resize framing."
    why_human: "The real ttyd/live-claude handshake + resize framing needs a routable 10.99.0.x worker and a booted golden template — not reachable in CI. CI proves the bridge against a protocol-accurate stub ttyd."
  - test: "Refresh the browser while a workspace is running and a terminal is attached to a real worker."
    expected: "The UI reconnects to the SAME live `claude` session (no fresh process, no scrollback restore in v1); the Mosaic layout reconciles to the live workspace list."
    why_human: "Live-PTY reattach correctness can only be confirmed against a real persistent ttyd session on a worker; CI verifies the reconnect/reconcile logic against the Fake provider + stub ttyd."
  - test: "Run the Tier-3 Playwright e2e in CI/locally: `cd ui && npx playwright test` over the Fake provider + standalone stub ttyd."
    expected: "The full create→echo→split→detach→reconnect→terminate journey passes."
    why_human: "Playwright requires a browser runtime + the running stub-ttyd e2e stack; not executed in this static verification pass. The spec file exists and is substantive; needs a real run to confirm green."
---

# Phase 2: Terminal Proxy + React UI Verification Report

**Phase Goal:** The operator opens, tiles, and interacts with live Claude Code terminals in the browser, with auto-reconnect, and a still-running workspace's terminal reattaches after a page refresh.
**Verified:** 2026-06-10T18:50:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | WS bridge negotiates ttyd `tty` subprotocol, relays frames opaquely both ways preserving text-vs-binary, tears down cleanly (no FD growth), emits typed error frame when ttyd unreachable | VERIFIED | `api/routers/terminal.py`: upstream `connect(subprotocols=[Subprotocol("tty")])`; `pump_down` uses `send_text`/`send_bytes` by `isinstance(frame, str)` — NEVER `.encode()` (SC-7); `asyncio.wait(FIRST_COMPLETED)` + cancel + `ping_interval=20` keepalive; `_safe_send_error` emits `{"type":"error","code":"LXC_NOT_READY"}`. Integration tier (9 tests) incl. `test_preserves_text_frame` (a `.encode()` regression FAILS it), `test_teardown_no_halfopen` (asserts `live==0`), `test_error_frame_when_ttyd_unreachable`. Stub is protocol-accurate (shared `handle_ttyd_connection`), not a bare echo. |
| 2 | Terminal renders via xterm.js; input/resize adapter drives a real TUI (fits/reflows, not 80x24); panel unmounts cleanly (WS closed, terminal disposed, ResizeObserver disconnected) | VERIFIED (CI) / human (real claude) | `ui/src/hooks/useTerminal.ts`: xterm `Terminal`+`FitAddon`, `safeFit()` guards zero-width (Pitfall 3), `term.onData`→`inputFrame` (`'0'` prefix), `resizeFrame` (`'1'`+JSON), `ResizeObserver`→`safeFit`; cleanup disposes term+fit, disconnects observer, closes socket, clears timer. `lib/ttyd.ts` frame builders match SC-7. Real `claude` TUI correctness → human. |
| 3 | Terminals tile in react-mosaic (open/split/drag/resize); sidebar lists workspaces with live polled status; New Workspace modal collects name/repo/branch/node + live boot-progress; status bar shows running/stopped counts, uptime, node capacity | VERIFIED | react-mosaic-component **6.2.0** pinned; `store/layoutStore.ts` (tree open/split/close/reconcile, persist); `WorkspaceLayout.tsx` binds `<Mosaic value/onChange>`; `WorkspaceList.tsx` (228px sidebar, `useWorkspaces` ~3s poll, status dots, creating-pulse); `NewWorkspaceModal.tsx` (name/repo/branch/node from `useNodes`, 4-step cosmetic boot-progress, server-error surface); `StatusBar.tsx` (running/stopped/error counts, uptime timer, peak node mem). All wired in `App.tsx`. |
| 4 | Transient disconnect auto-reconnects with jittered backoff behind a visible overlay; stops (terminal error) on error/destroyed; never thunders the API across panels | VERIFIED | `useTerminal.ts`: `backoffDelay` jittered exponential (cap 5, MAX 30s), `scheduleReconnect`→`setState("reconnecting")`; `TerminalPanel.tsx` reconnecting overlay w/ `attempt N / 5` + Reattach, error overlay + Retry; `POLICY_VIOLATION (1008)` and `status !== "running"` stop retrying. No-thunder: `useWorkspaces`/`useNodes` use a single shared TanStack Query cache (one poll per key), so N panels never each fetch. |
| 5 | After refresh, UI reconnects to same live `claude` session of a still-running workspace (no fresh process, no scrollback v1); persisted Mosaic layout reconciles against live workspace list | VERIFIED (CI) / human (live session) | `layoutStore.reconcile` + `WorkspaceLayout` `useEffect` on `useWorkspaces` success drops gone leaves, retargets active; persisted via zustand `persist`/`partialize` (`mosaicNode`+`activeWorkspaceId` only, status stays in Query — Pitfall 11). `useTerminal` reconnect attaches to live PTY (no scrollback). `tests/integration/restore.test.tsx` covers reconcile. Live-PTY reattach → human. |

**Score:** 5/5 truths verified for the CI-provable surface; truths 2 & 5 carry a real-infra remainder routed to human.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `api/routers/terminal.py` | Opaque tty WS bridge | VERIFIED | SC-7 relay, FIRST_COMPLETED teardown, typed error, SSRF/CSWSH/access gates |
| `api/routers/nodes.py` | `GET /api/v1/nodes` capacity (UI-04) | VERIFIED | Real fraction + threshold + over flag, degrade-not-500 |
| `ui/src/hooks/useTerminal.ts` | xterm+WS+Fit+Observer lifecycle, reconnect/dispose | VERIFIED | Wired into TerminalPanel |
| `ui/src/lib/ttyd.ts` | tty frame builders/opcodes | VERIFIED | init/input(`'0'`)/resize(`'1'`) |
| `ui/src/store/layoutStore.ts` | Mosaic tree + persist + reconcile | VERIFIED | Wired into WorkspaceLayout |
| `ui/src/components/{WorkspaceLayout,TerminalPanel,WorkspaceList,NewWorkspaceModal,StatusBar,Navbar}.tsx` | UI surfaces per 02-UI-SPEC | VERIFIED | All imported + rendered in App.tsx |
| `ui/src/hooks/{useWorkspaces,useNodes}.ts` | Live polled Query | VERIFIED | `refetchInterval: 3000`, shared cache |
| `api/tests/integration/test_terminal_proxy.py` | Bridge vs protocol-accurate stub | VERIFIED | 9 tests, SC-7 regression-proof |
| `ui/tests/e2e/terminal.spec.ts` | Playwright journey | VERIFIED (exists, substantive) | create→echo→split→detach→reconnect→terminate; needs a real run (human) |

### Key Link Verification

| From | To | Via | Status |
|------|----|----|--------|
| useTerminal | `/ws/workspaces/{id}/terminal` | `new WebSocket(...)` + init/input/resize frames | WIRED |
| TerminalPanel | useTerminal | hook call + status→overlays + detach/reattach | WIRED |
| WorkspaceLayout | layoutStore + useWorkspaces | `<Mosaic value/onChange>` + reconcile effect | WIRED |
| WorkspaceList/StatusBar/NewWorkspaceModal | useWorkspaces/useNodes | TanStack Query (shared cache) | WIRED |
| App | all surfaces | import + render | WIRED |

### Behavioral Spot-Checks / Probe Execution

| Check | Command | Result | Status |
|-------|---------|--------|--------|
| Backend suite | `uv run pytest -q` | 127 passed | PASS |
| UI unit/integration | `npm run test` | 81 passed (12 files) | PASS |
| Typecheck | `npx tsc --noEmit` | exit 0 | PASS |
| Format/lint | `npx biome ci .` | 41 files, no errors | PASS |
| SPDX/REUSE | `reuse lint` | 220/220 compliant | PASS |
| Playwright e2e | `npx playwright test` | not run (needs browser+stack) | SKIP → human |

### Requirements Coverage

TERM-01..07 (bridge negotiate/relay/teardown/error + xterm render/input/reconnect) and UI-01..05 (sidebar, mosaic tiling, modal, capacity, restore) are all backed by the verified artifacts above. UI-04 backend half (`/api/v1/nodes`) verified via `test_nodes.py`.

### Anti-Patterns Found

None. No TODO/FIXME/XXX/TBD/HACK/PLACEHOLDER in phase files. No stub returns; all rendered data flows from real Query/store sources. The NewWorkspaceModal 4-step "boot progress" is an explicitly-documented COSMETIC animation over a synchronous create (not a fake API claim) with a noted v1.x deferral — intentional, not a stub.

### Human Verification Required

1. **Real ttyd/live-claude handshake** — open a terminal against a booted worker; confirm the live `claude` TUI renders + reflows. (Real-infra; CI uses a protocol-accurate stub.)
2. **Live-session reattach after refresh** — refresh and confirm the same PTY reattaches (no fresh process).
3. **Playwright e2e run** — execute `npx playwright test` to confirm the journey spec passes green in a browser.

### Gaps Summary

No gaps. Every CI-provable success criterion is verified against the codebase: the WS proxy is a genuine opaque, type-preserving relay (SC-7 enforced by a regression-proof integration test), teardown is FIRST_COMPLETED + cancel + keepalive, useTerminal owns reconnect/dispose, react-mosaic 6.2.0 tiling + restore-after-refresh reconcile are wired, and all UI surfaces match the UI-SPEC and assemble in App.tsx. All five gates pass (pytest 127, vitest 81, tsc, biome, reuse). The only items outstanding require real Proxmox + a booted golden template (the live `tty` handshake/resize correctness and live-session reattach) plus an actual Playwright run — per the ROADMAP infra note these are dev-homelab smoke-gate items, classified `human_needed`, NOT failures.

---

_Verified: 2026-06-10T18:50:00Z_
_Verifier: Claude (gsd-verifier)_
