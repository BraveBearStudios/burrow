<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 5
slug: stop-start-controls-drawer-polish
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-14
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from 05-RESEARCH.md "Validation Architecture". The load-bearing fact:
> jsdom cannot evaluate `:focus-visible`, `::-webkit-scrollbar`, `@media` width,
> or computed layout — so V2/V3/V4 each get a **two-tier pair**: a vitest
> CSS-source assertion (rule shipped with the right tokens) + a Playwright
> assertion (live width / focus ring / scrollbar). The repo precedent is
> `ui/tests/tokens.test.ts` (readFileSync source-assert).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework (unit/integration)** | vitest 4.x + @testing-library/react 16 + jest-dom 6 + MSW 2, jsdom env |
| **Framework (e2e)** | @playwright/test 1.60 (Chromium) over `BURROW_COMPUTE=fake` + stub ttyd |
| **Config file** | `ui/vitest.config.ts`, `ui/playwright.config.ts` |
| **Quick run command** | `cd ui && npm test -- <area>` (+ `npm run lint`, `npm run typecheck`) |
| **Full suite command** | `cd ui && npm test && npm run lint && npm run typecheck && npm run build && npm run e2e` |
| **Estimated runtime** | ~25s unit/typecheck/lint; e2e adds ~60-90s (build + Chromium) |

---

## Sampling Rate

- **After every task commit:** Run `cd ui && npm test -- <changed-area>` + `npm run lint` + `npm run typecheck` (the failing-first regression test for that task goes green).
- **After every plan wave:** Run `cd ui && npm test` (full vitest) + `npm run lint` + `npm run typecheck` + `npm run build`.
- **Before phase verification:** Full suite green incl. `npm run e2e` (build `ui/dist` first).
- **Max feedback latency:** ~25 seconds (unit tier).

---

## Per-Requirement Verification Map

> Task IDs are assigned by the planner; this maps each requirement to its proof + tier.
> `jsdom-able?` ❌ means the criterion is NOT unit-testable in jsdom and must be a
> Playwright assertion or a CSS-source assertion — the planner MUST honor this when
> writing acceptance criteria (no live-layout / pseudo-class asserts in vitest).

| Requirement | Behavior | Test Type | Automated Command | jsdom-able? | Status |
|-------------|----------|-----------|-------------------|-------------|--------|
| UI-07 | Stop shown iff `running`; absent for creating/error/destroyed | unit | `npm test -- TerminalPanel` | ✅ | ⬜ pending |
| UI-07 | Stop fires `POST /stop`; disabled+`aria-busy` while pending; no double-fire | unit | `npm test -- TerminalPanel` | ✅ (MSW/spy) | ⬜ pending |
| UI-07 | `stopped` placeholder renders (heading+copy+CTA, `role=status`) instead of overlays | unit | `npm test -- TerminalPanel` | ✅ | ⬜ pending |
| UI-07 | `useTerminal` opens NO socket while stopped; tears down on running→stopped | unit | `npm test -- useTerminal` | ✅ (`MockWebSocket`) | ⬜ pending |
| UI-07 | full stop leg: click Stop → POST → placeholder after poll | e2e | `npm run e2e` | ❌ Playwright | ⬜ pending |
| UI-08 | Start shown iff `stopped`; fires `POST /start`; pending feedback | unit | `npm test -- TerminalPanel` | ✅ | ⬜ pending |
| UI-08 | `useTerminal` reconnects on stopped→running | unit | `npm test -- useTerminal` | ✅ (`MockWebSocket`) | ⬜ pending |
| UI-08 | full start leg: Start from placeholder → POST → terminal remounts | e2e | `npm run e2e` | ❌ Playwright | ⬜ pending |
| UI-09 | `--w-drawer` token + `@media (max-width:375px)` 100vw override present | unit | `npm test -- css-rules` | ❌ source-assert | ⬜ pending |
| UI-09 | `ActivityDrawer` reads `width:var(--w-drawer)` | unit | `npm test -- ActivityDrawer` | ✅ (inline `.style.width`) | ⬜ pending |
| UI-09 | drawer == viewport width (375px) on phone; 360px above | e2e | `npm run e2e` | ❌ Playwright viewport | ⬜ pending |
| UI-10 | global `:focus-visible { outline 2px solid var(--accent-line); offset 2px }` present | unit | `npm test -- css-rules` | ❌ source-assert | ⬜ pending |
| UI-10 | ring paints on keyboard focus across themes | e2e | `npm run e2e` | ❌ Playwright | ⬜ pending |
| UI-11 | `::-webkit-scrollbar*` (thumb `--border-mid`) + Firefox `scrollbar-width/color` present | unit | `npm test -- css-rules` | ❌ source-assert | ⬜ pending |
| UI-11 | styled scrollbar renders on a scroll surface | e2e/visual | `npm run e2e` | ❌ Playwright | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Test-infrastructure gaps that MUST land before (or as the first wave of) feature work — several unit tests hard-depend on them (`onUnhandledRequest:"error"` fails on a missing MSW handler):

- [ ] `ui/tests/msw/handlers.ts` — add `POST /api/v1/workspaces/:id/stop` and `/start` handlers (reuse `envelope()` + the 404 shape). **Required** by every gating/pending/round-trip unit test.
- [ ] `ui/src/components/TerminalPanel.test.tsx` — **does not exist**; create it (UI-07/08 gating, pending, placeholder, double-fire). Needs a `QueryClientProvider` wrapper (the panel mounts the closed `ActivityDrawer` whose `useWorkspaceEvents` needs context — the Plan 04-03 deviation).
- [ ] `ui/src/hooks/useTerminal.test.tsx` — add a `status="stopped"` describe block (no socket; teardown on flip; reconnect on stopped→running). File exists, no stopped coverage today.
- [ ] `ui/src/components/ActivityDrawer.test.tsx` — **does not exist**; add at minimum the `width:var(--w-drawer)` inline-style assert.
- [ ] A CSS-source test for V2/V3/V4 — extend `ui/tests/tokens.test.ts` or add `ui/tests/css-rules.test.ts` reading `src/index.css`; assert `--w-drawer`, the media override, `:focus-visible`, and the scrollbar rules exist with the right tokens.
- [ ] `ui/tests/e2e/stop-start.spec.ts` — **new** e2e spec (create→stop→start) + a UI-09 viewport test (`test.use({ viewport: { width: 375 } })`). Reuse `createWorkspace` + `waitForResponse`.
- [ ] No framework install needed — the full toolchain is present.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real-Proxmox stop→start of a live worker (LXC actually stops/starts, ttyd returns) | UI-07/UI-08 (real-infra half) | CI never touches real Proxmox by design; Fake provider proves the UI contract | Dev-homelab smoke: stop a running workspace, confirm CT stopped + placeholder; Start, confirm CT up + terminal reconnects. Tracked as v1.0 acceptance debt (ACC-01), not a v1.1 gate. |

*All v1.1 UI behaviors have automated verification (unit + e2e over the Fake). The manual row is the real-infra confirmation, deferred.*

---

## Validation Sign-Off

- [ ] All requirements have an automated verify or a Wave 0 dependency
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (MSW handler, the two new test files, css-rules test, e2e spec)
- [ ] No watch-mode flags (`vitest run`, not `vitest`)
- [ ] Feedback latency < 30s (unit tier)
- [ ] `nyquist_compliant: true` set in frontmatter once Wave 0 + per-requirement tests are wired

**Approval:** pending
