<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Phase 4 — UI Review (Activity Drawer, UI-06)

**Audited:** 2026-06-11
**Baseline:** `.planning/phases/04-hardening-release/04-UI-SPEC.md` (the binding design contract)
**Surface:** the per-workspace activity drawer (`ActivityDrawer` + `useWorkspaceEvents` + `EVENT_BADGE`/`badgeFor`)
**Screenshots:** not captured (no dev server on :3000/:5173/:8080 — code-only audit)
**Registry audit:** skipped — no `components.json` (shadcn not initialized); UI-SPEC declares zero registries. No new runtime UI dependency was added.

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 4/4 | Every spec string is verbatim; sentence case, middle-dot separator, no generic labels; read-only (no CTA) honored. |
| 2. Visuals | 4/4 | Clear hierarchy (dot + badge + timestamp + wrapped data); `boot.error` is the single emphasized row; icon buttons carry aria-labels. |
| 3. Color | 4/4 | Tokens only — zero hex, zero `--gold` in the drawer; badge map mirrors `status.ts`; accent reserved (not spent as a badge fill). |
| 4. Typography | 4/4 | Three families, max weight 500, every size on the spec scale (16/14/12/11.5px); unknown type rendered in mono as required. |
| 5. Spacing | 3/4 | 4px-grid paddings and fixed-chrome dimensions correct, BUT the responsive width is a single static value — the phone `100vw` full-width sheet (criterion 10) is not implemented. |
| 6. Experience Design | 3/4 | Four data states + newest-first + poll-gating + Esc/focus-trap/focus-return all present; BUT the spec's `--accent-line :focus-visible` ring and the `_ds` 3px scrollbar it leans on do not exist in the codebase. |

**Overall: 22/24**

## Top Priority Fixes

1. **Phone breakpoint never reaches `100vw` (WARNING — criterion 10 violated).**
   `ActivityDrawer.tsx:40` hardcodes `DRAWER_WIDTH = "min(360px, 100vw)"`. The comment on `:39` claims "360px desktop, min(360px,80vw) tablet, 100vw phone," but a single value cannot express three breakpoints. On a 375px phone the drawer renders 360px wide, leaving a ~15px scrim sliver instead of the spec'd full-width sheet; the tablet `min(360px,80vw)` band is also collapsed (it only coincidentally equals 360px at ≥640px because 80vw ≥ 512px there).
   *Impact:* the phone sheet UX in the contract is not delivered; the comment is misleading about what ships.
   *Fix:* drive the width from a media query rather than a constant — e.g. move the width to `index.css` as `.activity-drawer { width: 360px } @media (max-width:1023px){ width:min(360px,80vw) } @media (max-width:639px){ width:100vw }` and apply the class, or read `window.matchMedia` breakpoints. Inline styles cannot express the breakpoints, so a CSS rule is required.

2. **Spec-promised `--accent-line` focus ring and `_ds` scrollbar do not exist (WARNING — criterion 11 + Scroll/Overflow partially unmet).**
   UI-SPEC Color/A11y/Scroll sections promise an `--accent-line` `:focus-visible` ring on the `×`, the trigger, and the scroll region, and a global `_ds` 3px neutral scrollbar that "already" applies. Grep of the entire `ui/src` tree finds **no** `:focus-visible` rule and **no** `::-webkit-scrollbar` rule in `index.css` (the only stylesheet); the sole `_ds` token is a font-fallback comment. The drawer even sets `outline:"none"` on the `<aside>` (`ActivityDrawer.tsx:92`). Keyboard focus is still visible because the close `×` keeps the UA-default outline (nothing suppresses it), so this is a degraded pass, not a break — but the specific accent-token ring the contract mandates is absent app-wide.
   *Impact:* focus affordance is the browser default, not the Burrow accent ring; the "thin neutral 3px scrollbar" is the UA default. Cosmetic, not a task-blocker.
   *Fix:* add a global `:focus-visible { outline: 2px solid var(--accent-line); outline-offset: 2px }` and the `::-webkit-scrollbar` / `scrollbar-width:thin; scrollbar-color:` rules to `index.css` so the drawer (and the rest of the shell) inherits the contracted treatment. Remove or scope the `outline:"none"` on the `<aside>`.

3. **No explicit tablet/phone width path means responsive criterion can never be verified by a checker (WARNING — testability gap).**
   Because the width is a constant, there is no media query, class, or breakpoint hook a Playwright/visual checker could assert against for the three bands. The e2e journey only exercises the default desktop viewport.
   *Impact:* criterion 10 is unprovable; a future viewport regression would pass CI silently.
   *Fix:* once fix #1 lands (a CSS class with media queries), add a Playwright viewport assertion at 375px that the drawer width equals the viewport width.

## Minor Recommendations

- `dataSummary` (`ActivityDrawer.tsx:157-161`) renders every `data` key, not a redaction-aware subset — this is correct per the contract (the server already `_safe()`-redacted the object and the UI must render verbatim), but for very large `data` objects there is no key cap, so a pathological event could produce a long wrapped block. Spec allows wrapping, so this is acceptable; consider a soft key cap only if real events grow.
- The spec mentions an **optional** relative-time hint (`· 3m ago`) alongside the canonical `HH:MM:SS`. Only the absolute time is rendered (`formatTime`, `:164-170`). This is spec-compliant (the relative hint is explicitly optional and the absolute time is canonical), noted only for completeness.
- The drawer title falls back to literal `"Activity"` when `workspaceName` is absent (`:273`), while the `aria-label` falls back to `"Workspace activity log"` (`:330`). In practice `TerminalPanel` always passes `name`, so the fallback path is unreachable in the shipped wiring; harmless.

## Detailed Findings

### Pillar 1: Copywriting (4/4)

Every copy string matches the UI-SPEC Copywriting Contract verbatim, defined as named constants:
- Empty heading `"No activity yet"` (`ActivityDrawer.tsx:34`) and body `"Events appear here as this workspace boots, connects, and stops."` (`:35-36`) — exact.
- Poll-error strip `"Couldn't load the event log. Retrying…"` (`:37`) — exact, with the real ellipsis character.
- a11y labels: trigger `"Activity log"` (`TerminalPanel.tsx:274`), close `"Close activity log"` (`ActivityDrawer.tsx:341`) — exact.
- Badge labels (`events.ts:30-47`, `:70-75`): `Created`/`Started`/`Stopped`/`Auto-stopped (idle)`/`Destroyed`/`Terminal connected`/`Terminal disconnected`/`Boot error`/`Boot config persisted`/`Reaper · {suffix}` — all sentence case, middle-dot separator, matching the contract table.
- **Read-only honored:** no CTA, no mutation, no destructive confirmation in the drawer (the contract declares none). Rows are non-interactive `<li>` (`:200`). The terminate/confirm flow correctly stays in `TerminalPanel`, out of drawer scope.

No generic labels (`Submit`/`OK`/`Cancel`/`Save`) appear in the drawer. **No finding lowers this pillar.**

### Pillar 2: Visuals (4/4)

- **Focal hierarchy** per row: a 7px colored dot (`aria-hidden`) + a token-colored badge label + a right-pushed mono timestamp on line one, and a wrapped mono `data` summary on line two (`ActivityDrawer.tsx:218-236`). Size/weight/color differentiate the label (Inter 500 12px, token color) from the timestamp (mono 11.5px muted) from the data (mono 11.5px `--text-sub`).
- **`boot.error` is the single emphasized row** — 2px `--err` left bar + `--bg-panel-alt` tint + red mono reason (`:210-215`, `:231`); `isBootError` gates it so no other row type gets a bar/tint (criterion 4). Verified the reverse: the conditional is keyed strictly on `event.type === "boot.error"`.
- **Icon-only buttons are labelled:** the trigger (`aria-label="Activity log"`), the close `×` (`aria-label="Close activity log"`), and even the dismiss scrim (`aria-label`, then `aria-hidden` to drop it from the a11y tree). No unlabeled icon button.
- **Flat depth model honored:** no shadows, no gradients, no radius on the right edge; separation is `--bg-surf` body + a single 0.5px `--border` left border (`:87`), matching the contract's flat posture.

### Pillar 3: Color (4/4)

- **Tokens only.** Grep of `ActivityDrawer.tsx` and `events.ts` for `#[0-9a-fA-F]{3,8}`, `rgb(`, and `--gold` returns only documentation-comment matches — **zero** hardcoded colors and **zero** `--gold` in executable style (criterion 1, criterion 7). Every color resolves from a `--token`, so all four `data-theme`s render with no orphaned hue.
- **Badge map mirrors `status.ts`** (`events.ts:29-47`): `--ok` for created/started, `--err` for destroyed/boot.error, `--text-muted` for stopped/terminal.disconnected, `--accent-line` for terminal.connected, `--warn` for the idle special-case and `reaper.*`, `--text-sub` for bootconfig.persisted and the unknown fallback — a 1:1 match with the binding table.
- **Accent discipline:** `--accent-line` is used **only** as the `terminal.connected` dot/label token (which the spec's own map dictates) — it is never a badge **fill** (fills are always neutral `--bg-panel-alt`, `:132`) and never row text. The contract's "accent reserved for the focus ring" intent is met for fills; the one accent-as-status-color use is the map's own prescription, not an overuse.
- **`--err` reserved** for destructive/emphasis only (boot.error row + destroyed badge + poll-error strip), per the contract.

### Pillar 4: Typography (4/4)

Distinct sizes in use across the drawer: `16px` (title, Space Grotesk via `--font-display`, weight 500, `:108-110`), `14px` (empty heading, `:384`), `12px` (badge label `:138`; empty body `:390`), `11.5px` (timestamp `:153`; data summary `:228`; poll-error strip `:358`). All six sizes are on the UI-SPEC Typography table; **no size outside the table**. Distinct weights: `400` (default mono/body) and `500` (title, badge label, empty heading) — **max weight 500, never 600/700** (verified: no `fontWeight` > 500 anywhere in the file).

- **Three families** mapped to roles correctly: `--font-display` (title), `--font-sans` (labels/empty copy), `--font-mono` (timestamp, data, and the unknown-type badge via `badge.mono`, `:135`).
- **Unknown type renders in mono** (`events.ts:84` sets `mono: true`; `ActivityDrawer.tsx:135` switches the badge font family) so a forward-compatible type is visibly a system string (criterion 3) — confirmed by the test at `ActivityDrawer.test.tsx:154-167`.

### Pillar 5: Spacing (3/4)

**Correct:**
- Fixed-chrome dimensions match the contract: drawer header `var(--h-panel-header)` = 36px (`:99`), type badge `18px` (`:130`), status dot `var(--sz-status-dot)` = 7px (`:144`), row `min-height 44px` + `padding 10px 16px` (`:204-206`), icon button 24px (`:69-70`).
- Paddings are on or within ±2px of the 4px grid: header `0 var(--space-md)` (`:100`), empty state `var(--space-xl) var(--space-lg)` (`:377`), badge `0 6px` (`:131`), row gap `8px`/`4px`. No arbitrary off-grid pixel values; radius uses `--radius-chip`/`--radius-control` tokens.

**Finding (drops to 3):**
- **Responsive width is a single constant, not the three-band contract** (criterion 10). `ActivityDrawer.tsx:40` = `min(360px, 100vw)`. The spec mandates **360px desktop / `min(360px,80vw)` tablet / `100vw` phone, right-anchored full-width sheet on phone.** At 375px the rendered width is 360px (not full-width), so the phone sheet is missing; the tablet band is collapsed. Inline styles can't carry media queries, so this needs a CSS class. The misleading `:39` comment asserts the three bands are implemented when they are not — WARNING.

### Pillar 6: Experience Design (3/4)

**Strong state + interaction coverage:**
- **Four data states all present and distinct:** loading → `ShimmerRows` reusing the `pulse 1.4s` treatment (`:172-191`); empty → centered "No activity yet" + body (`:367-393`); error → the `role="alert"` `--err` strip rendered **over kept rows** so history is not discarded (`:348-363`); populated → the live list keyed on `event.id` for stable rows (`:396-400`). Matches criterion 6.
- **Newest-first** via `[...(data ?? [])].reverse()` (`:249`) — the endpoint is oldest-first; the test asserts boot.error (most recent) is the top row (criterion 2, `ActivityDrawer.test.tsx:100-109`).
- **Poll-gated:** `useWorkspaceEvents(workspaceId, isOpen)` with `enabled: enabled && !!id` (`useWorkspaceEvents.ts:37`) and an error-state backoff (`:35-36`, WR-04) so a destroyed workspace's 404 stops the poll. Closed drawer returns `null` and fires no request (test `:184-198`). Criterion 5 met.
- **A11y core met:** `role="dialog"` + `aria-modal` + `aria-label` (`:328-330`); `Esc` closes (`:277-279`); focus moves to the close `×` on open and **returns to the trigger** on close via the open-effect cleanup (`:258-267`) — a contract item `NewWorkspaceModal` omits, correctly added here; a focus trap cycles Tab within the `<aside>` and **correctly excludes the scrim** (`tabIndex=-1` + `aria-hidden`, `:312`/`:331`) so Tab can't escape onto the dismiss button (WR-03, tested `:215-241`); `aria-live="polite"` on the list (`:396`); status is dot **plus** text label, never color-only.
- **Redaction respected:** the drawer renders the server-`_safe()`-redacted `data` verbatim (`dataSummary`, `:157-161`) and makes **only** the same-origin events poll — no second request, no un-redact, no CDN (verified: no `fetch`/`EventSource`/`WebSocket`/`axios` in the drawer files). Threats T-04-03A/B/C honored.
- **Reduced motion:** the 200ms slide is a CSS `transition` (`:90`) that the global `prefers-reduced-motion` block in `index.css:264-272` collapses to ~0 — no JS animation bypasses it.

**Finding (drops to 3):**
- **The `--accent-line :focus-visible` ring and the `_ds` 3px scrollbar that criterion 11 / the Scroll section promise are absent from the codebase.** `index.css` (the only stylesheet) has no `:focus-visible` rule and no `::-webkit-scrollbar` rule; the drawer sets `outline:"none"` on the `<aside>` (`:92`). Keyboard focus remains visible via the UA-default outline on the close `×` (nothing suppresses it), so this is a **degraded pass, not a break** — but the contract's specific accent-token focus ring and styled scrollbar do not ship. WARNING.

## Files Audited

- `ui/src/components/ActivityDrawer.tsx` — the implemented drawer (primary audit target)
- `ui/src/components/ActivityDrawer.test.tsx` — the 11-test vitest suite (state/reverse/badge/emphasis/poll-gating/a11y coverage)
- `ui/src/lib/events.ts` — `EVENT_BADGE` map + `badgeFor` resolver
- `ui/src/hooks/useWorkspaceEvents.ts` — the enabled-gated poll hook
- `ui/src/components/TerminalPanel.tsx` — the Activity-log trigger + ephemeral `activeEventsWorkspaceId` wiring
- `ui/src/components/WorkspaceList.tsx` — the ShimmerRows + poll-error strip patterns the drawer mirrors (cross-check)
- `ui/src/lib/status.ts` — the `STATUS_COLOR` pattern `events.ts` mirrors (cross-check)
- `ui/src/index.css` — the design tokens + global motion/animation block (token-reuse + reduced-motion + focus-ring/scrollbar gap)
- `ui/src/lib/themes.ts` — the four-theme registry (token-swap completeness)
- `.planning/phases/04-hardening-release/04-UI-SPEC.md` — the binding contract (baseline)
- `.planning/phases/04-hardening-release/04-03-PLAN.md`, `04-03-SUMMARY.md`, `04-CONTEXT.md` — intent + locked decisions
