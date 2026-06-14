<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 05-stop-start-controls-drawer-polish
plan: 03
subsystem: frontend-ui
tags: [css, tailwind-v4, tdd-green, ui-09, ui-10, ui-11, drawer, focus-ring, scrollbar, tokens-only]

# Dependency graph
requires:
  - phase: 05-stop-start-controls-drawer-polish
    plan: 01
    provides: "The RED CSS-source tests (css-rules.test.ts V2/V3/V4) + the ActivityDrawer --w-drawer width-token RED test"
  - phase: 04-reconciler-drawer-release
    provides: "ActivityDrawer (UI-06) with the DRAWER_WIDTH literal this plan swaps for the token"
  - phase: 02-ui-foundation-terminal
    provides: "index.css four-theme @theme tokens (--accent-line/--border-mid/--text-muted/--radius-full defined per theme), the prefers-reduced-motion media-query model, the .burrow-mosaic token-driven global-rule analog"
provides:
  - "The --w-drawer layout token (min(360px, 100vw) default) + the @media (max-width:375px) :root override that ships the phone full-width sheet (UI-09)"
  - "One global :focus-visible { outline: 2px solid var(--accent-line); outline-offset: 2px } ring app-wide across all four themes (UI-10)"
  - "The global custom Burrow scrollbar (::-webkit-scrollbar(-track/-thumb) thumb --border-mid on transparent track + Firefox scrollbar-width:thin/scrollbar-color), tokens only (UI-11)"
  - "ActivityDrawer drawerStyle reading width: var(--w-drawer) instead of the inline literal"
affects: [05-04-e2e-gate]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Layout dimension as a single @theme token overridden in plain CSS under @media (NOT nested @theme — Tailwind v4 Pitfall 6): inline styles cannot express a breakpoint, so the responsiveness lives in --w-drawer and the component stays inline-style"
    - "ONE global :focus-visible rule (DRY) reading the per-theme --accent-line covers every interactive control app-wide across all four themes; :focus-visible (not :focus) so a mouse click does not paint the ring"
    - "Global custom scrollbar tokens-only: thumb --border-mid (a neutral, never accent/gold) on a transparent track + Firefox scrollbar-width/scrollbar-color; no per-theme or per-surface override needed"

key-files:
  created: []
  modified:
    - "ui/src/index.css"
    - "ui/src/components/ActivityDrawer.tsx"

key-decisions:
  - "The 375px override re-declares --w-drawer on :root inside the @media block in plain CSS — NOT a nested @theme (Tailwind v4 @theme is not nestable under @media, RESEARCH Pitfall 6). The css-rules test regex asserts exactly this shape (@media (max-width: 375px) { :root { --w-drawer: 100vw }})."
  - "One global :focus-visible rule placed after the prefers-reduced-motion block, unscoped, so it covers every control app-wide. The ActivityDrawer <aside> outline:\"none\" was NOT changed: :focus-visible targets the focused element specifically, and the bare tabIndex={-1} <aside> intentionally suppresses its own ring while leaving every child control ring intact (Pitfall 5 — never broaden to * { outline: none })."
  - "Scrollbar thumb is --border-mid (neutral) deepening to --text-muted on hover; never --accent-line, never --gold. The thumb radius reuses --radius-full and a 2px transparent border + background-clip:padding-box insets the visible thumb — tokens only, zero hex."

requirements-completed: [UI-09, UI-10, UI-11]

# Metrics
duration: 9min
completed: 2026-06-14
---

# Phase 5 Plan 03: Drawer Width Token + Global Focus Ring + Custom Scrollbar Summary

**The three 04-UI-REVIEW polish details restored as pure global-CSS additions plus one inline-style swap: the `--w-drawer` token + `@media (max-width:375px)` override (UI-09 phone full-width sheet), one global `:focus-visible` `--accent-line` ring (UI-10), and the global custom Burrow scrollbar (UI-11) — turning the remaining 6 Plan-01 RED tests GREEN with the full vitest suite now 113/113 and zero hex/CDN/gold.**

## Performance

- **Duration:** ~9 min
- **Tasks:** 2 (Task 1 = `--w-drawer` token + drawer swap; Task 2 = `:focus-visible` + scrollbar)
- **Files modified:** 2 (0 created)

## Accomplishments

- **Task 1 — `--w-drawer` token + 375px override; ActivityDrawer swap (UI-09 / V2).** Added `--w-drawer: min(360px, 100vw)` to the `@theme` fixed-chrome dimensions group (alongside `--w-sidebar`/`--w-modal`; a dimension, not a color, so not re-declared per theme). Added the plain-CSS `@media (max-width: 375px) { :root { --w-drawer: 100vw } }` override next to the existing `prefers-reduced-motion` block — NOT nested under `@theme` (Tailwind v4 Pitfall 6). In `ActivityDrawer.tsx`, swapped `width: DRAWER_WIDTH` for `width: "var(--w-drawer)"`, removed the now-unused `DRAWER_WIDTH` const, and replaced the stale/misleading width comment (flagged by 04-UI-REVIEW) with an accurate one. The component stays inline-style; the responsiveness lives in the token.
- **Task 2 — global `:focus-visible` ring + custom scrollbar (UI-10 / V3, UI-11 / V4).** Added ONE global `:focus-visible { outline: 2px solid var(--accent-line); outline-offset: 2px }` rule (keyboard/programmatic focus, not `:focus`) after the media block — app-wide, DRY, rendering in all four themes since `--accent-line` is defined per theme. Added the global custom scrollbar tokens-only: `::-webkit-scrollbar { width/height: 8px }`, `::-webkit-scrollbar-track { background: transparent }`, `::-webkit-scrollbar-thumb { background: var(--border-mid); border-radius: var(--radius-full); border: 2px solid transparent; background-clip: padding-box }`, `::-webkit-scrollbar-thumb:hover { background: var(--text-muted) }`, and the Firefox `* { scrollbar-width: thin; scrollbar-color: var(--border-mid) transparent }`. Verified the `<aside>` `outline:"none"` does not suppress child control rings — no change needed there, no `* { outline: none }` introduced.

## Task Commits

1. **Task 1: --w-drawer token + 375px override + ActivityDrawer swap** — `d309ada` (feat)
2. **Task 2: global :focus-visible ring + custom scrollbar** — `b6a861f` (feat)

**Plan metadata:** _(this commit — docs(05-03))_

## Files Created/Modified

- `ui/src/index.css` — `--w-drawer` added to the `@theme` fixed-chrome block; the `@media (max-width: 375px) { :root { --w-drawer: 100vw } }` override; the global `:focus-visible` ring; the global custom scrollbar (`::-webkit-scrollbar(-track/-thumb)` + Firefox `scrollbar-width`/`scrollbar-color`). SPDX header + `@import "tailwindcss"` ordering + `prefers-reduced-motion` block all intact.
- `ui/src/components/ActivityDrawer.tsx` — `drawerStyle.width` now reads `var(--w-drawer)`; the `DRAWER_WIDTH` literal const + its stale comment removed, replaced by an accurate token-driven comment.

## Decisions Made

- **375px override is plain-CSS `:root`, not a nested `@theme`.** Tailwind v4's `@theme` is not nestable under `@media`; the responsive token is re-declared on `:root` inside the media block (RESEARCH Pitfall 6). The `css-rules.test.ts` regex asserts exactly this shape.
- **`<aside>` `outline:"none"` left as-is.** `:focus-visible` targets the focused element specifically, so the bare `tabIndex={-1}` `<aside>` keeping `outline:none` does not suppress child control rings. No broadening to `* { outline: none }` (Pitfall 5). The global ring now gives the inline icon buttons (Stop/Start, the drawer ×, sidebar rows) the focus affordance they lacked.
- **Scrollbar thumb is a neutral, never accent/gold.** Thumb `--border-mid` → hover `--text-muted`; radius `--radius-full`; a 2px transparent border + `background-clip: padding-box` insets the visible thumb. One global rule covers all four themes (the tokens are defined per theme). Zero hex on the new rules.

## Deviations from Plan

None — plan executed exactly as written. Both tasks landed the precise rules the UI-SPEC §4/§5/§6 verbatim bodies and the `css-rules.test.ts` / `ActivityDrawer.test.tsx` regexes specify; no auto-fix (Rules 1-3) and no architectural decision (Rule 4) was triggered. No package install (pure CSS + one inline-style swap; no new runtime dependency).

## Issues Encountered

None. Typecheck, the css-rules subset, the full vitest suite, lint, and build all passed on the first post-implementation run. The 6 RED-by-design tests from Plan-01 are now GREEN with no regression to the 107 prior-passing tests.

## Known Stubs

None. The rules are live global CSS read by the real ActivityDrawer and every interactive control / scroll surface; no hardcoded/empty data, no placeholder, no TODO/FIXME. The `--w-drawer` token, the `:focus-visible` ring, and the scrollbar are all fully wired.

## Threat Flags

None. No new endpoint, network surface, auth path, file access, or schema change — the change is static stylesheet additions plus one inline-style swap. The threat register's `mitigate` dispositions are satisfied: T-05-07 (no `@import`, no `url()`, no font/icon CDN added — the `googleapis|gstatic|jsdelivr` source assert stays green), T-05-08 (the `<aside>` `outline:none` is not broadened; the unscoped `:focus-visible` covers every control; no `* { outline: none }`). T-05-SC (no package install) is n/a.

## Test Results

- **vitest (full):** 113 passed, 0 failed (15 files) — the 6 Plan-01 RED-by-design tests (5 `css-rules.test.ts` V2/V3/V4 + 1 `ActivityDrawer` `--w-drawer` width-token) are now GREEN; the FULL v1.1 Phase 5 unit suite is GREEN.
- **05-03 scope:** the 2 `--w-drawer` css-rules tests + the ActivityDrawer width-token test (V2), the `:focus-visible` test (V3), and the `::-webkit-scrollbar-thumb` + Firefox `scrollbar-width`/`scrollbar-color` tests (V4) all GREEN.
- **lint:** `biome ci .` clean (50 files).
- **typecheck:** `tsc --noEmit` exits 0.
- **build:** `npm run build` succeeds (pre-existing >500kB chunk-size advisory only; informational, not introduced by this CSS-only change — out of scope).
- **No hex / no CDN:** zero hardcoded hex in the new rules (lines 273+ are tokens-only: `var(--accent-line)`/`var(--border-mid)`/`var(--text-muted)`/`var(--radius-full)`); no new `@import`/`url()`/CDN — the global no-CDN assert stays green.
- **e2e:** not run here (the live drawer-width-at-375px / ring-on-Tab / scrollbar-paint proofs are the 05-04 Playwright gate; jsdom has no layout/media-query engine — boundary honored).

## Next Phase Readiness

- **05-04 (e2e gate)** runs the `stop-start.spec.ts` journey (create → stop → placeholder → start → reconnect) plus the V2 responsive-width proof (`page.setViewportSize({ width: 375 })` → drawer width == viewport width; >375px → ~360px) and the live ring/scrollbar paint over the built UI + Fake + stub ttyd.
- All UI-09/UI-10/UI-11 source contracts are GREEN; the full Phase 5 unit suite is GREEN. No blockers. No regression.

## Self-Check: PASSED

- `ui/src/index.css` — FOUND (modified; contains `--w-drawer`, `:focus-visible`, `::-webkit-scrollbar-thumb`, `scrollbar-width: thin`)
- `ui/src/components/ActivityDrawer.tsx` — FOUND (modified; `width: "var(--w-drawer)"`)
- Commit `d309ada` — FOUND in git history
- Commit `b6a861f` — FOUND in git history

---
*Phase: 05-stop-start-controls-drawer-polish*
*Completed: 2026-06-14*
