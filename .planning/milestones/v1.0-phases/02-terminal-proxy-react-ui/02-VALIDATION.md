---
phase: 2
slug: terminal-proxy-react-ui
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-10
---

<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Phase 2 — Validation Strategy

> CI proves the WS proxy against a **protocol-accurate stub ttyd**, the React UI via vitest + MSW, and the full journey via Playwright over the FakeComputeProvider. Real ttyd `tty` handshake against a real worker is the dev-homelab smoke gate (deferred).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Backend** | pytest + pytest-asyncio (WS proxy) — `api/tests/integration/` + a `websockets.serve` stub-ttyd fixture |
| **Frontend** | vitest 4 + Testing Library + MSW (`ui/`); mock `WebSocket` + fetch |
| **E2E** | Playwright over `BURROW_COMPUTE=fake` + the stub ttyd |
| **Quick run** | `cd api && uv run pytest -q` · `cd ui && npm run test` |
| **Full suite** | api pytest + `cd ui && npm run test && npx tsc --noEmit && npx biome ci` + `npx playwright test` |

---

## Sampling Rate

- **Per task commit:** the touched tier (`uv run pytest tests/integration/test_terminal_proxy.py -x` or `cd ui && npm run test -- <file>`) + ruff/mypy (api) or tsc/biome (ui)
- **Per wave:** api pytest + ui vitest + tsc + biome green
- **Before verify:** full suite incl. Playwright e2e; real-ttyd = homelab smoke (deferred)

---

## Per-Req Verification Map

| Req | Behavior | Test Type | Command | Status |
|-----|----------|-----------|---------|--------|
| TERM-01, TERM-02 | WS bridge negotiates `tty` subprotocol, relays frames opaquely (text vs binary preserved — `.encode()` regression FAILS) | integration | `pytest tests/integration/test_terminal_proxy.py -x` | ⬜ W0 |
| TERM-03 | Logs connect/disconnect; typed error frame when ttyd unreachable; rejects non-running | integration | same | ⬜ W0 |
| TERM-04 | FIRST_COMPLETED + cancel teardown; no half-open leak / FD growth | integration | same | ⬜ W0 |
| TERM-05 | xterm renders, FitAddon fits/reflows on resize (not stuck 80x24) | unit (vitest) | `cd ui && npm run test -- TerminalPanel` | ⬜ W0 |
| TERM-06 | Auto-reconnect jittered backoff + reconnecting overlay; stops on error/destroyed | unit (vitest) | `cd ui && npm run test -- useTerminal` | ⬜ W0 |
| TERM-07 | Clean unmount: WS closed, xterm disposed, ResizeObserver disconnected | unit (vitest) | same | ⬜ W0 |
| UI-01 | Sidebar lists workspaces with live polled status chips | integration (MSW) | `cd ui && npm run test -- WorkspaceList` | ⬜ W0 |
| UI-02 | Mosaic open/split(H/V)/drag/resize; layoutStore reconciles vs live list | unit (vitest) | `cd ui && npm run test -- layoutStore` | ⬜ W0 |
| UI-03 | New Workspace modal: form → POST → staged boot-progress → opens panel | integration (MSW) | `cd ui && npm run test -- NewWorkspaceModal` | ⬜ W0 |
| UI-04 | Status bar: running/stopped counts, uptime, node capacity (`GET /api/v1/nodes`) | unit (vitest) + integration | `cd ui && npm run test -- StatusBar` | ⬜ W0 |
| UI-05 | Reconnect a running workspace's live terminal after refresh (no scrollback) | integration (MSW) | `cd ui && npm run test -- restore` | ⬜ W0 |
| all | Full create→terminal→split→detach→reconnect→terminate journey | e2e (Playwright) | `cd ui && npx playwright test` | ⬜ W0 |
| TERM (real-infra) | Real ttyd `tty` handshake + live claude TUI | manual / homelab | dev-homelab smoke | ⬜ deferred |

---

## Wave 0 Requirements

- [ ] Backend: `api/tests/integration/test_terminal_proxy.py` + a protocol-accurate `stub_ttyd` fixture (`websockets.serve`, negotiates `tty`, requires JSON init, echoes `'0'`-prefixed) — NOT a bare echo
- [ ] Bump+lock `websockets` to the STACK.md pin
- [ ] Frontend: vitest + Testing Library + MSW + Playwright dev deps; `ui/src/**/*.test.tsx`; `ui/tests/e2e/`; `playwright.config.ts`; MSW handlers for `/api/v1`
- [ ] A small `GET /api/v1/nodes` endpoint (reuses `getNodeMemory`) for UI-04 capacity

---

## Manual-Only Verifications (dev-homelab — deferred)

| Behavior | Req | Why Manual | Test |
|----------|-----|------------|------|
| Real ttyd `tty` handshake; live `claude` TUI echoes input; resize works | TERM-01/05 | Real worker + ttyd | Open a real workspace terminal; type, resize, confirm |
| Persistent ttyd survives tab close (detach) | UI-05 | Real session | Close tab, reopen, same session |

> Deferred per the operator's full-autonomous choice (no Proxmox/worker reachable). `human_needed`, not phase-blocking.

---

## Security Domain (ASVS L1)

- **WS proxy SSRF guard:** bridge ONLY to the workspace's own `lxc_ip` (never an arbitrary host); reject non-running workspaces (close code); **CSWSH `Origin` check** on the WS upgrade (LAN origin) as defense-in-depth.
- No auth added (v1 LAN-only no-auth — ignore the design prompt's "auth-gated" phrasing, A6).
- No secrets in frames/logs; the proxy is an opaque relay (no payload inspection/logging of terminal content).
- No external CDN fonts/icons (self-host woff2 + inline SVG — CSP-friendly, per UI-SPEC).

---

## Validation Sign-Off

- [ ] Every CI-provable req has an `<automated>` verify or Wave 0 dependency
- [ ] Stub ttyd is protocol-accurate (a `.encode()` regression FAILS CI — not hidden by a bare echo)
- [ ] `nyquist_compliant: true`

**Approval:** pending
