<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 02-terminal-proxy-react-ui
plan: 02
subsystem: ui
tags: [vite, react, tailwind-v4, vitest, msw, playwright, xterm, react-mosaic, zustand, tanstack-query, ttyd]

# Dependency graph
requires:
  - phase: 02-terminal-proxy-react-ui (plan 01)
    provides: "the {data,meta,error} envelope, camelCase Workspace JSON, /api/v1/nodes capacity shape, and the verified ttyd tty-subprotocol opcodes the UI types + frame builders mirror"
  - phase: 00-contracts-seams (plan 04)
    provides: "the bare ui/ scaffold (typescript 6.0.3 + biome 2.4.16 + tsconfig/biome configs) this plan builds the real app on"
provides:
  - "Buildable/testable Vite 8 + React 19 + Tailwind v4 UI project (green build/tsc/biome/vitest)"
  - "Typed envelope client api<T>() + ApiError (src/api/client.ts)"
  - "camelCase domain types: Workspace, WorkspaceStatus, WorkspaceCreate, NodeCapacity, ApiEnvelope, TerminalState (src/types/workspace.ts)"
  - "Verified ttyd frame builders initFrame/inputFrame/resizeFrame + opcode constants (src/lib/ttyd.ts)"
  - "Four-theme @theme design-token sheet (dark/dark-soft/medium/light) + spacing/chrome/radius/motion tokens + keyframes (src/index.css)"
  - "Self-hosted font infrastructure (system-stack fallback, ready-to-activate @font-face, CDN-free)"
  - "MSW /api/v1 test harness (handlers + server) wired into vitest setup"
affects: [02-03, 02-04, 02-05, 02-06]

# Tech tracking
tech-stack:
  added: [react@19.2.7, react-dom@19.2.7, "@xterm/xterm@6.0.0", "@xterm/addon-fit@0.11.0", "@xterm/addon-web-links@0.12.0", react-mosaic-component@6.2.0, react-dnd@16.0.1, react-dnd-html5-backend@16.0.1, "@tanstack/react-query@5.101.0", zustand@5.0.14, vite@8.0.16, "@vitejs/plugin-react@6.0.2", tailwindcss@4.3.0, "@tailwindcss/vite@4.3.0", vitest@4.1.8, "@testing-library/react@16.3.2", "@testing-library/jest-dom@6.9.1", jsdom, msw@2.14.6, "@playwright/test@1.60.0"]
  patterns: ["Tailwind v4 CSS-first @theme (no tailwind.config.ts, ADR-0008)", "envelope-unwrapping typed fetch wrapper that throws ApiError on error!=null", "ttyd protocol owned by the client (verified frame builders), proxy stays a dumb relay", "data-theme token swap with the full token set per theme block", "CDN-free self-hosted fonts with _ds system-stack fallback", "MSW handlers in the {data,meta,error} envelope for Tier-2 tests"]

key-files:
  created: [ui/vite.config.ts, ui/vitest.config.ts, ui/playwright.config.ts, ui/index.html, ui/src/main.tsx, ui/src/App.tsx, ui/src/index.css, ui/src/api/client.ts, ui/src/api/client.test.ts, ui/src/types/workspace.ts, ui/src/lib/ttyd.ts, ui/src/vite-env.d.ts, ui/tests/setup.ts, ui/tests/tokens.test.ts, ui/tests/msw/handlers.ts, ui/tests/msw/server.ts, ui/public/fonts/README.md]
  modified: [ui/package.json, ui/package-lock.json, ui/tsconfig.json, ui/biome.json]

key-decisions:
  - "react-mosaic-component pinned EXACT 6.2.0 (no caret) in package.json so a future npm install can never pull the 7.0.0-beta on latest"
  - "Fonts ship CDN-free via the _ds system-stack fallback because no woff2 was vendorable at build time; @font-face blocks + public/fonts/README.md document the drop-in activation path"
  - "RED/GREEN split for the TDD client+ttyd task: types+test (RED) then implementations (GREEN)"
  - "tests/setup.ts owns the MSW server lifecycle (listen/reset/close) so every Tier-2 test mocks /api/v1 by default with onUnhandledRequest:error"
  - "biome includes widened to tests/** and *.config.ts so the whole real tree is linted/formatted, not just src/**"

patterns-established:
  - "Pattern 1: api<T>(path) unwraps the standard envelope and throws typed ApiError(code,message) — every downstream hook/component consumes data directly"
  - "Pattern 2: lib/ttyd.ts is the single source of the verified ttyd opcodes + frame builders; useTerminal (02-04) imports them without re-derivation"
  - "Pattern 3: index.css defines bare --token aliases per [data-theme] mirroring Tailwind --color-*; components read --tokens, never hex"

requirements-completed: []

# Metrics
duration: 24min
completed: 2026-06-10
---

# Phase 2 Plan 02: UI Foundation Summary

**Real Vite 8 + React 19 + Tailwind v4 UI project on the Phase-0 scaffold: pinned stack (react-mosaic 6.2.0 exact, @xterm 6, vitest/MSW/Playwright), a typed envelope `client.ts` + camelCase domain types, verified ttyd frame builders, a four-theme CSS-first `@theme` token sheet with self-hosted fonts, and an MSW `/api/v1` harness — green build/tsc/biome/vitest.**

## Performance

- **Duration:** ~24 min
- **Started:** 2026-06-10T14:30:00Z
- **Completed:** 2026-06-10T14:54:00Z
- **Tasks:** 3 (Task 2 is TDD: RED + GREEN)
- **Files modified:** 22 (17 created, 4 modified, 1 deleted)

## Accomplishments

- Installed the full pinned UI stack on the bare scaffold and wired Vite 8 (`react()` + `tailwindcss()` plugins, no `tailwind.config.ts`), a `/api/v1` + `/ws` dev proxy, vitest 4 (jsdom + globals + setup), and a Playwright config skeleton. `react-mosaic-component` pinned EXACT 6.2.0 — verified no 7.x anywhere in the lockfile.
- Shipped the contracts layer every later UI plan imports: `client.ts` (envelope unwrap + `ApiError`), `types/workspace.ts` (camelCase `Workspace`/`WorkspaceStatus`/`WorkspaceCreate`/`NodeCapacity`/`ApiEnvelope`/`TerminalState`), and `lib/ttyd.ts` (verified `initFrame`/`inputFrame`/`resizeFrame` + opcode constants). Five behaviors proven by `client.test.ts` (TDD).
- Authored the binding four-theme `@theme` token sheet (dark/dark-soft/medium/light) lifted verbatim from 02-UI-SPEC, plus spacing/chrome/radius/motion tokens, pulse/spin/blink keyframes, and a `prefers-reduced-motion` still block.
- Self-hosted-font infrastructure that is CDN-free today (system-stack fallback) with a documented woff2 drop-in path; strict same-origin CSP in `index.html`.
- MSW `/api/v1` test harness (workspaces list/create/get + nodes) in the `{data,meta,error}` envelope, wired into the vitest setup for Tier-2 tests.

## Task Commits

Each task was committed atomically:

1. **Task 1: Install pinned stack + wire Vite/Tailwind/vitest/Playwright** - `f5b220d` (chore)
2. **Task 2 (RED): failing tests for envelope client + ttyd frames** - `02b0e22` (test)
3. **Task 2 (GREEN): typed envelope client + verified ttyd frame builders** - `c41999b` (feat)
4. **Task 3: four-theme token sheet + self-hosted fonts + MSW handlers** - `3462625` (feat)

**Plan metadata:** (final docs commit — SUMMARY + STATE + ROADMAP)

_Task 2 is TDD: RED (`02b0e22`) then GREEN (`c41999b`); no REFACTOR commit needed (code was clean)._

## Files Created/Modified

- `ui/vite.config.ts` - `react()` + `tailwindcss()` plugins (CSS-first), `/api/v1` + `/ws` dev proxy to the control plane
- `ui/vitest.config.ts` - jsdom env, globals, `setupFiles: ['./tests/setup.ts']`
- `ui/playwright.config.ts` - Tier-3 e2e skeleton (webServer wiring finalized in 02-06)
- `ui/index.html` - `data-theme="dark"` root, strict same-origin CSP (no external font/icon CDN), `#root`
- `ui/src/main.tsx` - `createRoot` + `QueryClientProvider` + `StrictMode`; `ui/src/App.tsx` placeholder shell
- `ui/src/index.css` - `@import "tailwindcss"` + `@theme` tokens + four `[data-theme]` blocks + keyframes + reduced-motion
- `ui/src/api/client.ts` - `api<T>()` envelope unwrap + `ApiError`; `ui/src/api/client.test.ts` - 5 behaviors
- `ui/src/types/workspace.ts` - camelCase domain types mirroring the backend CamelModel JSON
- `ui/src/lib/ttyd.ts` - verified ttyd opcodes + `initFrame`/`inputFrame`/`resizeFrame`
- `ui/src/vite-env.d.ts` - vite/client types (declares `*.css` side-effect imports for tsc)
- `ui/tests/setup.ts` - jest-dom matchers + MSW server lifecycle
- `ui/tests/tokens.test.ts` - asserts all four themes define the full token set + no CDN
- `ui/tests/msw/handlers.ts` + `server.ts` - `/api/v1` mock surface in the envelope
- `ui/public/fonts/README.md` - self-host drop-in contract (CDN-free)
- `ui/package.json` / `package-lock.json` - pinned deps + scripts (dev/build/preview/test/e2e); `ui/tsconfig.json` (jsx, DOM libs, types, include tests); `ui/biome.json` (widened includes)
- `ui/src/placeholder.ts` - **removed** (Phase-0 stand-in superseded by the real app entry)

## Decisions Made

- **react-mosaic 6.2.0 EXACT:** pinned without a caret so the landmine 7.0.0-beta can never resolve; lockfile verified to contain no 7.x.
- **CDN-free fonts via system-stack fallback:** no woff2 was available to vendor at build time (no font package, none in the design bundle, no network). Per the UI-SPEC's sanctioned fallback, `--font-*` resolve to the `_ds` system stacks; `@font-face` blocks + `public/fonts/README.md` make activation a drop-in.
- **TDD RED/GREEN split** for the client+ttyd task with types in the RED commit (the test needs them to compile its fixtures), implementations in GREEN.
- **No `tailwind.config.ts`** — Tailwind v4 is CSS-first (ADR-0008); tokens live in `@theme` + per-theme blocks.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added `src/vite-env.d.ts` so tsc resolves the `./index.css` side-effect import**
- **Found during:** Task 1 (tsc verification)
- **Issue:** `main.tsx` imports `./index.css`; `tsc --noEmit` errored TS2882 (no type declaration for the CSS side-effect import).
- **Fix:** Added `src/vite-env.d.ts` with `/// <reference types="vite/client" />` (declares `*.css` and asset imports).
- **Files modified:** ui/src/vite-env.d.ts (created)
- **Verification:** `npx tsc --noEmit` clean.
- **Committed in:** `f5b220d` (Task 1 commit)

**2. [Rule 3 - Blocking] Widened biome `includes` to `tests/**` and `*.config.ts`**
- **Found during:** Task 1 (biome scope)
- **Issue:** The Phase-0 biome config scoped `includes` to `src/**` only, so the new config files and the `tests/` tree (including the MSW harness and TDD test) were not linted/formatted — the plan's `biome ci .` and `biome ci tests/msw` checks would silently skip them.
- **Fix:** Added `tests/**/*.ts(x)` and `*.config.ts` to `biome.json` includes.
- **Files modified:** ui/biome.json
- **Verification:** `npx biome ci .` now checks 15 files, all green.
- **Committed in:** `f5b220d` (Task 1 commit)

**3. [Rule 1 - Bug] Token test path resolution failed under jsdom**
- **Found during:** Task 3 (token-presence test)
- **Issue:** `fileURLToPath(new URL("../src/index.css", import.meta.url))` threw `TypeError: The URL must be of scheme file` because vitest's jsdom `import.meta.url` is an `http://` URL.
- **Fix:** Resolve the CSS path from `process.cwd()` (the `ui/` root) with `node:path`.
- **Files modified:** ui/tests/tokens.test.ts
- **Verification:** `npx vitest run` — 11 tests pass.
- **Committed in:** `3462625` (Task 3 commit)

**4. [Rule 2 - Missing Critical] Reworded `public/fonts/README.md` + CSP comment to keep the CDN grep-assert clean**
- **Found during:** Task 1 + Task 3 (CDN grep-assert)
- **Issue:** The CSP comment and the fonts README named the literal forbidden CDN hostnames as documentation; Vite copies `public/` into `dist/`, so the strings appeared in the shipped artifact and tripped the binding `grep "googleapis\|gstatic\|jsdelivr"` assert (UI-SPEC criterion 6).
- **Fix:** Reworded both to refer to "external font/icon CDN" generically; the actual `@font-face`/`<link>` surface was already CDN-free.
- **Files modified:** ui/index.html, ui/public/fonts/README.md
- **Verification:** `grep -rI "googleapis\|gstatic\|jsdelivr" ui/src ui/index.html ui/public` and `ui/dist` both empty.
- **Committed in:** `f5b220d` + `3462625`

---

**Total deviations:** 4 auto-fixed (2 blocking, 1 bug, 1 missing-critical). All were correctness/posture requirements to make the plan's own verification asserts pass. No scope creep — no business components were added (those are Waves 2-4).

## Issues Encountered

- npm peer-dependency warnings during install (react 18 vs 19 transitive peers inside `react-mosaic-component`'s bundled `react-dnd-multi-backend`). Expected and non-blocking — mosaic 6.2.0 officially supports React 19 (peer `16-19`); the build, tsc, and tests are all green.

## Known Stubs

- **`src/App.tsx`** is an intentional placeholder shell (renders the wordmark on `var(--bg)`). The real top-bar / sidebar / mosaic grid / status-bar shell is delivered by Plans 02-03/04/05 (Waves 2-4). Documented as intentional; this plan is pure foundation.
- **`ui/public/fonts/`** ships no woff2 yet — the system-stack fallback renders correctly today; the Burrow faces activate when an operator drops the woff2 in and uncomments the `@font-face` blocks (drop-in contract in `README.md`). The UI renders fully without them.

## User Setup Required

None - no external service configuration required. (Optional later: drop the three woff2 faces into `ui/public/fonts/` to activate the Burrow type, per `ui/public/fonts/README.md`. The UI renders on the system-stack fallback without them.)

## Next Phase Readiness

- The contracts-and-tooling layer is in place: `client.ts`, `types/workspace.ts`, and `lib/ttyd.ts` are importable blueprints, the four-theme token sheet resolves, and MSW mocks `/api/v1`. Waves 2-4 (02-03 terminal panel, 02-04 mosaic layout + useTerminal, 02-05 sidebar/modal/statusbar) build directly on these without re-deriving the envelope, types, or ttyd protocol.
- Playwright browser binaries are NOT installed (per plan — that is the 02-06 e2e plan's concern); the dep + config skeleton are in place.
- No blockers introduced. The UI half of UI-04 (capacity chip) still lands in 02-05; this plan delivered only the foundation.

## Self-Check: PASSED

All 17 created files verified present on disk; all 4 task commits (`f5b220d`, `02b0e22`, `c41999b`, `3462625`) verified in git log. Full gate green: `npm run build` + `tsc --noEmit` + `biome ci .` (15 files) + `vitest run` (11 tests); CDN grep-assert empty; react-mosaic-component resolves to exactly 6.2.0; no `tailwind.config.ts`; REUSE/SPDX compliant 185/185.

---
*Phase: 02-terminal-proxy-react-ui*
*Completed: 2026-06-10*
