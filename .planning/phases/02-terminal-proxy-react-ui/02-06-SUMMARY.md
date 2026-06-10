<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 02-terminal-proxy-react-ui
plan: 06
subsystem: testing
tags: [playwright, e2e, vitest, msw, websockets, ttyd, react-mosaic, fastapi, docker-compose]

requires:
  - phase: 02-01
    provides: WS terminal bridge + protocol-accurate stub_ttyd_ws fixture
  - phase: 02-03
    provides: useTerminal hook + TerminalPanel + mock WebSocket/xterm helpers
  - phase: 02-04
    provides: layoutStore reconcile + WorkspaceLayout restore-after-refresh wiring
  - phase: 02-05
    provides: assembled App shell (Navbar/WorkspaceList/NewWorkspaceModal/StatusBar)
provides:
  - Standalone protocol-accurate stub ttyd (api/tests/e2e/stub_ttyd_server.py) sharing the Plan-01 handler
  - Full Playwright journey (create → echo → split/tile → detach→reconnect → terminate) over Fake + stub ttyd — RAN GREEN
  - UI-05 restore-after-refresh integration test (reconcile + live reconnect, no scrollback)
  - Terminate confirm gate + non-destructive detach (UI-SPEC criterion 12)
  - docker-compose.e2e.yml + nginx.e2e.conf + finalized playwright.config.ts e2e harness
affects: [phase-03, phase-04, ci-cd, dev-homelab-smoke]

tech-stack:
  added: [playwright webServer multi-process harness, websockets process_request HTTP health]
  patterns:
    - "Single shared stub-ttyd handler across the pytest fixture + the standalone e2e server (no protocol drift)"
    - "E2E-only ttyd host override via operator env (BURROW_E2E_TTYD_HOST), never client input — SSRF posture unchanged"
    - "Detach = close the live socket (reconnect overlay); terminate = confirm-gated closePanel"

key-files:
  created:
    - api/tests/e2e/stub_ttyd_server.py
    - api/tests/e2e/__init__.py
    - ui/tests/integration/restore.test.tsx
    - ui/tests/e2e/terminal.spec.ts
    - docker-compose.e2e.yml
    - ui/nginx.e2e.conf
  modified:
    - api/tests/integration/conftest.py
    - api/routers/terminal.py
    - api/services/workspaceService.py
    - ui/src/components/TerminalPanel.tsx
    - ui/src/hooks/useTerminal.ts
    - ui/playwright.config.ts
    - ui/vite.config.ts

key-decisions:
  - "Factor the protocol-accurate tty handler into one shared module both tiers import (T-02-07: SC-7 cannot hide in either tier)"
  - "E2E-only host override (env, not client input) so the bridge + saga reach a single local stub without a routable 10.99.0.x worker net"
  - "Stub ttyd answers the saga's HTTP health GET via websockets process_request (real ttyd serves HTTP+WS on :7681)"
  - "Wire terminate confirm + non-destructive detach (must_haves truths that were unwired before this plan)"

patterns-established:
  - "Playwright webServer array boots stub ttyd + uvicorn-on-fake + vite preview locally; BURROW_E2E_USE_COMPOSE=1 defers to docker-compose.e2e.yml in CI"
  - "vite preview.proxy mirrors the dev /api/v1 + /ws proxy so the built SPA is same-origin in e2e"

requirements-completed: [UI-02, UI-05]

duration: 35min
completed: 2026-06-10
---

# Phase 2 Plan 06: Phase E2E Gate Summary

**Full Playwright journey (create → terminal echoes → split/tile → detach→reconnect → terminate) RAN GREEN over the FakeComputeProvider + a standalone protocol-accurate stub ttyd, plus a UI-05 restore-after-refresh integration test that proves reconcile + live reconnect with no scrollback.**

## Performance

- **Duration:** 35 min
- **Started:** 2026-06-10T21:58:17Z
- **Completed:** 2026-06-10T22:33:36Z
- **Tasks:** 2
- **Files modified:** 13 (6 created, 7 modified)

## Accomplishments
- **The live Playwright e2e RAN and PASSED locally (21.7s)** — a real Chromium drives the whole slice (create via modal → terminal echoes the typed token through the live WS bridge → tile two panels + split → detach shows the reconnecting overlay non-destructively → reconnect → terminate is confirm-gated and removes the panel). This is the cross-cutting acceptance layer exercising every prior plan together.
- **Standalone protocol-accurate stub ttyd** (`api/tests/e2e/stub_ttyd_server.py`): the SAME `tty` handler the Plan-01 pytest fixture uses, factored into one shared module the fixture now imports — no duplicate, weaker echo. It also answers the create saga's HTTP health GET (process_request → 200) so the e2e create resolves.
- **UI-05 restore-after-refresh integration test** (vitest + MSW): after a simulated refresh the gone leaf reconciles out, the still-running panel re-mounts and opens a FRESH live WS, and no scrollback is replayed (Pitfall 7). Green here.
- **Terminate confirm gate + non-destructive detach** wired (these `must_haves` truths were unwired before this plan): `Destroy {name}? …` confirm before closePanel; detach closes the live socket → reconnecting overlay, session survives. Unit-covered.
- **E2E harness:** `docker-compose.e2e.yml` (api-on-fake + stub ttyd pinned at the Fake worker IP + nginx-served built UI) + `ui/nginx.e2e.conf` + finalized `playwright.config.ts`.

## Task Commits

1. **Task 1: Standalone stub ttyd + UI-05 restore test + e2e compose harness** — `f714da1` (test)
2. **Task 2: Full Playwright journey + terminate confirm + detach** — `8fbd527` (test)

**Plan metadata:** committed with this SUMMARY + STATE + ROADMAP + REQUIREMENTS.

## Files Created/Modified
- `api/tests/e2e/stub_ttyd_server.py` — standalone protocol-accurate stub ttyd (shared `tty` handler + HTTP health responder + CLI entrypoint).
- `api/tests/e2e/__init__.py` — e2e test package.
- `api/tests/integration/conftest.py` — `stub_ttyd_ws` fixture now imports the shared handler (only adds live-count + echoed-type bookkeeping).
- `api/routers/terminal.py` — `_ttyd_url` honors the e2e-only `BURROW_E2E_TTYD_HOST` env override (production dial unchanged).
- `api/services/workspaceService.py` — `_wait_ttyd` honors the same e2e host override for the step-6 health poll.
- `ui/tests/integration/restore.test.tsx` — UI-05 restore: reconcile + live reconnect + no-scrollback.
- `ui/tests/e2e/terminal.spec.ts` — the full Playwright journey.
- `ui/src/components/TerminalPanel.tsx` + `.test.tsx` — terminate confirm gate + detach wiring + coverage.
- `ui/src/hooks/useTerminal.ts` — `detach()` (non-destructive socket close → reconnect overlay).
- `ui/playwright.config.ts` — finalized webServer (stub + api + preview) / compose toggle.
- `ui/vite.config.ts` — `preview.proxy` mirrors the dev proxy for same-origin e2e.
- `docker-compose.e2e.yml` + `ui/nginx.e2e.conf` — containerized e2e stack.
- `.gitignore` — ignore Tier-3 Playwright artifacts.

## Decisions Made
- One shared stub-ttyd handler across both test tiers (T-02-07): a `.encode()`/subprotocol regression fails BOTH the integration tier and the live e2e journey.
- E2E host override is an operator-controlled env var, never client input, so the SSRF guard's intent is intact (the access gate still requires a running workspace with a resolved IP; the override only retargets the reachable test stub).
- The stub answers HTTP health on the same port as the WS handshake (real ttyd does), so the synchronous create saga resolves quickly against one process.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Wired the terminate confirm gate + non-destructive detach**
- **Found during:** Task 2 (the journey could not assert the detach-vs-terminate semantics).
- **Issue:** The plan's `must_haves` truths require "terminate asks the confirm copy before removing the panel; detach is non-destructive." But `WorkspaceLayout` wired `onTerminate` to call `closePanel` directly (no confirm) and `onDetach` was unwired entirely — so the behavior the e2e + UI-SPEC criterion 12 must prove did not exist.
- **Fix:** Added a confirm overlay in `TerminalPanel` (`Destroy {name}? …` → `Destroy`/`Cancel`, panel dim) and a `detach()` on `useTerminal` (close the live socket → reconnecting overlay, session survives). Wired the detach button to call it. Added unit coverage.
- **Files modified:** `ui/src/components/TerminalPanel.tsx`, `ui/src/hooks/useTerminal.ts`, `ui/src/components/TerminalPanel.test.tsx`.
- **Verification:** TerminalPanel unit tests (confirm gate + detach overlay) pass; the live Playwright journey asserts both end-to-end.
- **Committed in:** `8fbd527` (Task 2 commit).

**2. [Rule 3 - Blocking] E2E-only ttyd host override (bridge + saga) so the stack is reachable**
- **Found during:** Task 2 (the live create hung, then the bridge could not reach the stub).
- **Issue:** The Fake derives `lxc_ip = 10.99.0.<vmid>`, which is unroutable on a single host. Both the create saga's step-6 health GET and the WS bridge dial that IP, so neither reached the local stub (the create modal hung for the full `ttyd_timeout`).
- **Fix:** Added a `BURROW_E2E_TTYD_HOST` env override (operator env, never client input) to `_ttyd_url` and `_wait_ttyd`; absent it, production behavior is unchanged. Set in the Playwright webServer + the compose stack. Also taught the standalone stub to answer the HTTP health GET (`process_request` → 200).
- **Files modified:** `api/routers/terminal.py`, `api/services/workspaceService.py`, `api/tests/e2e/stub_ttyd_server.py`, `ui/playwright.config.ts`, `ui/vite.config.ts`, `docker-compose.e2e.yml`.
- **Verification:** The full live journey passes (HTTP health 200 + WS terminals accepted in the api logs); all 127 api + 81 ui tests still green.
- **Committed in:** `8fbd527` (Task 2 commit).

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 blocking).
**Impact on plan:** Both were required for the plan's own acceptance criteria (the must_haves detach-vs-terminate truths + a reachable e2e stack). No scope creep; the override is e2e-only and leaves the production SSRF posture unchanged.

## Issues Encountered
- The installed Playwright browser (chromium-1148) mismatched `@playwright/test@1.60.0` (wanted v1223). Resolved by `npx playwright install chromium` (~112 MiB) — the environment permitted it, so the live e2e RAN rather than being deferred.
- First create attempt hung (saga health poll + bridge both dialing the unroutable Fake IP) — resolved by the e2e host override + stub HTTP health (Deviation 2).
- Split on a single open panel is a no-op by design (`layoutStore.splitPanel` rebalances 2+ leaves; Mosaic forbids duplicate ids). The journey opens a second workspace so the tiling/split assertion is meaningful — faithful to the real UX.

## Live E2E Status
**RAN GREEN locally** (`npx playwright test tests/e2e/terminal.spec.ts` → 1 passed, 21.7s) against the live Fake + standalone stub ttyd stack. The api logs confirm the real path (HTTP health 200, WS terminals accepted for both workspaces, echo round-trip, detach→reconnect, terminate). The real ttyd `tty` handshake + a live `claude` TUI against a real worker remains the dev-homelab smoke gate (deferred, `human_needed`) — NOT this plan.

## User Setup Required
None — the e2e stack is hermetic (Fake compute, stub ttyd, no secrets). In CI: `npx playwright install chromium` before the e2e job (already noted in playwright.config.ts).

## Next Phase Readiness
- The phase slice is proven end-to-end without real infra: the WS bridge, useTerminal, the mosaic layoutStore, and the surfaces all work together.
- Phase 3+ can rely on the standalone stub ttyd + the e2e harness as the regression floor for the terminal path.
- `docker compose -f docker-compose.e2e.yml config` was NOT validated here (no Docker on this host) — validated by YAML parse + structure assertions instead; first CI run will confirm the compose stack boots.

## Self-Check: PASSED

All created files exist on disk (stub_ttyd_server.py, restore.test.tsx, terminal.spec.ts, docker-compose.e2e.yml, nginx.e2e.conf, SUMMARY.md) and both task commits (`f714da1`, `8fbd527`) are present in the git history.

---
*Phase: 02-terminal-proxy-react-ui*
*Completed: 2026-06-10*
