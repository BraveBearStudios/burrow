<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
# Phase 5 — UI Review

**Audited:** 2026-06-14
**Baseline:** `05-UI-SPEC.md` (binding design contract) + `05-CONTEXT.md` (12 locked decisions)
**Screenshots:** not captured (no dev server on :3000/:5173/:8080 — code-only audit). The five `ui/uat-shots/*.png` are v1.0 shell shots and predate the Phase 5 token work (e.g. `05-drawer-phone-375.png` shows the pre-V2 360px panel with a scrim sliver, not the new full-width sheet); they are context only, not Phase 5 evidence.
**Stance:** advisory / non-blocking. Score + findings only; the orchestrator commits.

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 4/4 | Heading + body + a11y labels match the Copywriting Contract verbatim; sentence case, no generic strings. |
| 2. Visuals | 3/4 | Gating, glyphs, in-flight feedback all correct; the spec's optional decorative 22px square glyph above the placeholder heading was omitted, flattening the drawn hierarchy. |
| 3. Color | 4/4 | Zero hex on new surfaces, zero gold on new controls, accent reserved to the focus ring + spinner arc; CDN assert green. |
| 4. Typography | 4/4 | Max weight 500, no new sizes; placeholder heading 16px/display, body 12px/sans via `overlayBase`. |
| 5. Spacing | 4/4 | Placeholder column on the 4px grid (`--space-xl --space-lg`, gap `--space-sm`); fixed-chrome reuses existing tokens; 14px/22px spinner sizes are the contracted load-bearing dimensions. |
| 6. Experience Design | 4/4 | Show-only-applicable gating, no optimistic flip, `useTerminal` teardown/reconnect on the status dep, V2/V3/V4 all present and token-driven across four themes. |

**Overall: 23/24**

## Top 3 Priority Fixes

1. **Optional decorative square glyph omitted from the `stopped` placeholder** — the spec anatomy (05-UI-SPEC §2, line 273) draws a 22px outline-square `--text-muted` glyph above the `Workspace stopped` heading; the implementation renders heading → body → CTA only (`TerminalPanel.tsx:437-472`). The spec marks it "(optional, decorative)," so this is contract-compliant, but it is the one delta from the drawn hierarchy and the only reason Visuals is 3/4. **Fix (if desired):** add a `<StopIcon>`-style 22px square at `--text-muted` as the first child of the placeholder column, gap already `--space-sm`. Low effort, restores the drawn focal stack.

2. **Placeholder body copy relies on `overlayBase` inheritance rather than an explicit type declaration** — the body `<span>` (`TerminalPanel.tsx:447-456`) sets `color`, `maxWidth`, `textAlign`, `lineHeight` but inherits `font-family`/`font-size` from the `overlayBase` spread (`--font-sans` / 12px). It resolves to the correct 12px/400 sans the Typography table wants, but the value is implicit; a future `overlayBase` edit would silently shift the placeholder copy. **Fix (defensive, optional):** add explicit `fontFamily: "var(--font-sans)"`, `fontSize: "12px"` to the body span so the contract value is pinned at the call site, matching how the heading already pins its own font.

3. **Drawer `<aside>` still sets `outline: "none"` on the bare container** — `ActivityDrawer.tsx:91` keeps `outline:"none"` in `drawerStyle`. The spec (§5 / criterion 9) asked to "remove or neutralize" it so the contracted ring is not suppressed. It is benign in practice: the `<aside>` is `tabIndex={-1}` (line 330) so it never keyboard-focuses, and the global `:focus-visible` rule still rings the controls inside (close `×`, scrim-excluded). **Fix (optional, for literal criterion-9 conformance):** drop the `outline:"none"` from `drawerStyle` or scope it explicitly to `:focus:not(:focus-visible)`; no behavioral change, closes the spec's worded ask.

## Detailed Findings

### Pillar 1: Copywriting (4/4)
- Heading `STOPPED_HEADING = "Workspace stopped"` (`TerminalPanel.tsx:253`) — verbatim match to the Copywriting Contract row.
- Body `STOPPED_BODY = "This workspace is stopped. Start it to reconnect the terminal and pick up where you left off."` (`TerminalPanel.tsx:254-255`) — verbatim, sentence case, second-person, unhedged.
- CTA visible label `Start workspace` (`TerminalPanel.tsx:471`) and a11y labels `Stop workspace` / `Start workspace` (`TerminalPanel.tsx:361,373,459`) — all match.
- No new error copy added (the contract says Stop/Start failures self-correct via the poll) — confirmed; `onStop`/`onStart` `onError` only `console.error` (`WorkspaceLayout.tsx:90-102`).
- Generic-label grep on the new surfaces found no `Submit`/`OK`/`Click here`. BLOCKER: none. WARNING: none.

### Pillar 2: Visuals (3/4)
- **Gating (criterion 1):** exactly one of Stop (square) / Start (play-triangle) renders per status; `creating`/`error`/`destroyed` render `null` (`TerminalPanel.tsx:358-380`). Correct, show-only-applicable, not show-both-and-disable.
- **Three actions stay distinct (criterion 11):** Detach = `PlugIcon`, Stop = outline `rect` `StopIcon` (`TerminalPanel.tsx:124-136`), Terminate = `CloseIcon` `×`. Glyphs are visually and semantically separate; Stop is left of Split so Terminate stays rightmost (matches the placement contract, `TerminalPanel.tsx:353-409`).
- **Glyphs:** Stop `<rect x="6" y="6" width="12" height="12" rx="1.5"/>`, Start `<path d="M8 5v14l11-7z"/>`, both 15px outline, `fill:none`, stroke 1.5 via the `ICON` spread — match the existing Split/Plug/Close set.
- **In-flight focal feedback:** header swaps glyph→14px `HeaderSpinner`; placeholder swaps glyph→22px `Spinner` (`TerminalPanel.tsx:367,378,470`). Clear focal change, no reflow.
- **WARNING (the lost point):** the spec's optional decorative 22px square above the heading is absent (see Priority Fix 1). The heading still carries the focal weight (16px/display/`--text-sub`), so hierarchy is legible — but the drawn anatomy's top glyph is missing. Spec-sanctioned omission; flagged for completeness, not a defect.

### Pillar 3: Color (4/4)
- **Zero hex on new surfaces:** grep for `#[0-9a-f]{3,8}` across `TerminalPanel.tsx` / `ActivityDrawer.tsx` / `WorkspaceLayout.tsx` returns none. The four `rgba(26,28,26,.xx)` literals (`TerminalPanel.tsx:495,506,520,548`) are the **pre-existing v1.0** connecting/reconnecting/error/terminate scrims — out of this phase's scope and untouched. The **new** `stopped` placeholder correctly uses `background: "var(--bg-surf)"` (`TerminalPanel.tsx:432`), the calm wash the contract specified, not a hardcoded scrim.
- **Zero gold on new controls (criterion 7):** `HeaderSpinner` hard-codes `--accent-line`, no `gold` prop path (`TerminalPanel.tsx:245`); the placeholder `<Spinner />` is rendered with no `gold` prop (`TerminalPanel.tsx:470`) → defaults to `--accent-line`. The only `--gold` reads are the pre-existing model label (`:338`) and the reconnect spinner's `gold` prop (`:510`), neither in this phase's surfaces.
- **Accent discipline (10% rule):** `--accent-line` is spent only on the global `:focus-visible` ring (`index.css:296`) and the spinner top-arcs. The Stop/Start glyphs, placeholder text, and CTA fill all resolve to neutrals (`--text-muted` / `--text-sub` / `--bg-panel-alt`). No accent on a button fill, glyph at rest, or scrollbar thumb.
- **Scrollbar thumb is `--border-mid`** (a neutral), hover `--text-muted` (`index.css:314-322`) — never accent, never gold. Correct.
- **Status→color single-sourced:** `lib/status.ts` keeps `stopped = --text-muted` (calm, non-alarming); the new controls read status to gate visibility, never to recolor. No literal status color introduced.
- **CDN assert green:** `grep -E "googleapis|gstatic|jsdelivr"` across `ui/src` → none (PLAT-05 intact).

### Pillar 4: Typography (4/4)
- **No weight above 500:** the only `fontWeight` values in `TerminalPanel.tsx` are 500 (name `:311`, heading `:441`). Placeholder body and CTA inherit 400/500 from `--font-sans` defaults. No 600/700 anywhere.
- **No new sizes:** placeholder heading 16px (`:440`), body 12px via `overlayBase` (`:200`) — both on the binding 02/04 scale. The 10.5px/11px/12.5px values are pre-existing v1.0 header chrome, untouched.
- **Heading family/color:** `--font-display`, 16px, 500, `--text-sub` (`TerminalPanel.tsx:438-443`) — matches the Typography table and the §2 anatomy.
- Minor: body copy size is implicit via inheritance (see Priority Fix 2) — resolves correctly today, flagged as a defensive nit, not a defect.

### Pillar 5: Spacing (4/4)
- **Placeholder column on the 4px grid:** `padding: var(--space-xl) var(--space-lg)` (32/24), `gap: var(--space-sm)` (8) — `TerminalPanel.tsx:430-431`. Matches the "centered with `--space-xl --space-lg`, gap `--space-sm`" spec line and mirrors the drawer empty state.
- **Header button gap:** `headerStyle` keeps `gap: var(--space-sm)` (`:171`), unchanged. The new Stop/Start buttons reuse `iconButtonStyle` (24×24, `--radius-control`) verbatim (`:179-189`) — no new dimension introduced.
- **Spinner sizes are the contracted load-bearing values:** `HeaderSpinner` 14px / 2px border (`:241-242`), placeholder `Spinner` 22px / 2px (`:220-221`). These are the spec's fixed-chrome dimensions, not arbitrary drift — correctly off-grid by contract to fit inside the 24px button without reflow.
- `maxWidth: "260px"` on the body copy (`:450`) matches the spec's "~260px, matches the terminate-confirm copy width." CTA `gap: "6px"` (`:464`) is within the ±2px tolerance the shell allows.

### Pillar 6: Experience Design (4/4)
- **No Stop confirm; Terminate keeps confirm (criterion 2):** `onStop` fires immediately on click (`TerminalPanel.tsx:365`); Terminate still opens the `Destroy {name}?` overlay (`:406,544-578`). Stop is neutral `--text-muted`, never red. Correct.
- **In-flight feedback (criterion 3):** both buttons set `disabled={pending}` + `aria-busy` and swap to the spinner (`:363-378`); the placeholder CTA shares `startPending` so header + body disable together (`:466-470`). The spinner clears on settle (mutation `onSettled` → poll), never wedges.
- **No optimistic flip (criterion 4):** `onStop`/`onStart` call `mutate` only — no `closePanel`, no Zustand status write (`WorkspaceLayout.tsx:89-103`). Status is server-truth; the ~3s `useWorkspaces` poll drives the Stop↔Start and placeholder↔terminal swap. Correct.
- **`stopped` placeholder (criterion 5):** body branches on `status === "stopped"` **before** the `termStatus` overlays (`TerminalPanel.tsx:425`), so a transient `termStatus` during teardown can't flash an error scrim. It is `role="status"` / `aria-live="polite"` (`:434-435`), never `role="alert"`. Correct.
- **Terminal hook gated on `stopped` (criterion 6):** `useTerminal` early-returns at `status !== "running"` (`useTerminal.ts:178`); the effect deps are `[workspaceId, status]` (`:303`), so on `running→stopped` the cleanup runs (sets `disposedRef`, `socket.close()`, `term.dispose()` — `:288-302`) and the early-return blocks re-connect; on `stopped→running` the effect re-runs and reconnects. The contracted teardown/reconnect is structurally correct.
- **V2 responsive drawer (criterion 8):** `--w-drawer: min(360px,100vw)` in `@theme` (`index.css:53`), `@media (max-width:375px){:root{--w-drawer:100vw}}` (`:282-286`), `ActivityDrawer` reads `width: var(--w-drawer)` (`:82`). Full-width ≤375px, 360px above. Closes the 04-UI-REVIEW Pillar-5 finding.
- **V3 focus ring (criterion 9):** one global `:focus-visible { outline: 2px solid var(--accent-line); outline-offset: 2px }` (`index.css:295-298`), `:focus-visible` not `:focus`. `--accent-line` is per-theme, so it rings across all four. Closes the 04-UI-REVIEW Pillar-6 finding. WARNING: the drawer `<aside>`'s `outline:"none"` is still present (see Priority Fix 3) — benign (the `<aside>` is `tabIndex=-1`), but the spec's literal "remove or neutralize" ask is unmet.
- **V4 scrollbar (criterion 10):** `::-webkit-scrollbar`/`-track`/`-thumb` with thumb `--border-mid`, transparent track, hover `--text-muted` (`index.css:307-322`) + Firefox `scrollbar-width: thin` / `scrollbar-color: var(--border-mid) transparent` (`:325-328`). Tokens only, global, reaches the drawer list / terminal body / sidebar list. Closes the 04-UI-REVIEW Pillar-6 finding.
- **Four-theme coverage:** `--accent-line`, `--border-mid`, `--text-muted`, `--bg-surf` are all declared in every `[data-theme]` block (`index.css:99-185`), so the single global rules for the ring, scrollbar, spinner, and placeholder render correctly in dark / dark-soft / medium / light with no orphaned hue. (Code-confirmed; not visually screenshot-confirmed — see Screenshots note.)
- **a11y / no color-only state:** `stopped` is conveyed by the placeholder text plus the sidebar overline, not color alone; the Stop/Start affordance is glyph **plus** `aria-label`. The duplicate "Start workspace" accessible name (header button + placeholder CTA both on a `stopped` panel) is **UI-SPEC-sanctioned** (both fire the same `useStartWorkspace`) — noted and accepted per the audit brief.

## Registry Safety

Skipped. No `components.json` in the repo (`shadcn_initialized: false` in the spec front-matter) and the Registry Safety table declares no shadcn and no third-party registries. The two new glyphs are inline outline SVG; no `shadcn view` / registry fetch occurs. Registry audit: 0 third-party blocks, no flags.

## Files Audited
- `.planning/phases/05-stop-start-controls-drawer-polish/05-UI-SPEC.md` (binding contract)
- `.planning/phases/05-stop-start-controls-drawer-polish/05-CONTEXT.md` (12 locked decisions)
- `ui/src/components/TerminalPanel.tsx` (Stop/Start header buttons, glyphs, `HeaderSpinner`, `stopped` placeholder)
- `ui/src/components/WorkspaceLayout.tsx` (`LeafPanel` onStop/onStart wiring, no optimistic flip)
- `ui/src/components/ActivityDrawer.tsx` (V2 `width: var(--w-drawer)`)
- `ui/src/index.css` (four-theme tokens, `--w-drawer` + 375px media override, global `:focus-visible`, custom scrollbar)
- `ui/src/lib/status.ts` (status→color single source; `stopped = --text-muted`)
- `ui/src/hooks/useTerminal.ts` (connect/reconnect gating on `status`, teardown deps) — read for criterion 6 verification
- `ui/uat-shots/*.png` (v1.0 context only; predate Phase 5)
