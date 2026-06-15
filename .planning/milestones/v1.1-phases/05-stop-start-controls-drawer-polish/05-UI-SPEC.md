<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 5
slug: stop-start-controls-drawer-polish
status: approved
shadcn_initialized: false
preset: none
created: 2026-06-14
reviewed_at: 2026-06-14
surfaces: terminal-panel-header, terminal-panel-body, activity-drawer, global-css
requirements: UI-07, UI-08, UI-09, UI-10, UI-11
---

# Phase 5 — UI Design Contract (Stop/Start Controls + Drawer Polish)

> Visual and interaction contract for the four frontend surfaces Phase 5 touches:
> the **TerminalPanel header** (Stop/Start icon buttons, UI-07/UI-08), the
> **TerminalPanel body** (the `stopped` placeholder, UI-07/UI-08), the
> **ActivityDrawer width** (UI-09), and **`index.css`** global rules (focus ring
> UI-10, custom scrollbar UI-11). No backend change; CI-provable over the Fake
> provider + stub ttyd (vitest + MSW + Playwright).
>
> **Binding inheritance — this is a brownfield polish phase on a SHIPPED v1.0 UI.**
> You are NOT inventing a design system; one exists and is binding. Reuse the tokens
> in `ui/src/index.css` (four-theme CSS-first `@theme`), the status→color map in
> `ui/src/lib/status.ts`, the icon-button + overlay patterns in
> `ui/src/components/TerminalPanel.tsx`, and the copywriting/a11y conventions from
> the binding `02-UI-SPEC` and `04-UI-SPEC`. **Do not invent a new palette, type
> scale, or aesthetic.** Where this spec is silent, the 02/04-UI-SPECs govern.
>
> **Locked upstream (do not re-litigate):** every decision in `05-CONTEXT.md` is a
> user decision — Stop/Start as header icon buttons (square / play-triangle glyphs),
> show-only-applicable gating, **no Stop confirm**, disable+spinner while pending, a
> `Workspace stopped` placeholder body + Start CTA with `useTerminal` gated off while
> stopped, V2 via a `--w-drawer` token overridden at `@media (max-width:375px)`, V3
> global `:focus-visible` ring using `--accent-line`, V4 global custom scrollbar with
> the thumb at `--border-mid`. This document encodes those decisions; it does not
> re-ask them.
>
> **Why this phase exists (provenance):** the `04-UI-REVIEW` scored the activity
> drawer **22/24**, dropping exactly two points: (Pillar 5) the responsive width is a
> single constant, so the phone full-width sheet never ships; and (Pillar 6) the
> contract-promised `--accent-line :focus-visible` ring and styled scrollbar **do not
> exist anywhere in `ui/src`**. UI-09/UI-10/UI-11 close those two findings. UI-07/UI-08
> surface the WS-06/WS-07 stop/start endpoints (TanStack hooks already ship from v1.0).

---

## Surface Scope (what this contract covers)

| # | Surface | File(s) | Requirement |
|---|---------|---------|-------------|
| 1 | **Stop/Start header buttons** | `TerminalPanel.tsx` header cluster | UI-07, UI-08 |
| 2 | **`stopped` placeholder body** | `TerminalPanel.tsx` body branch | UI-07, UI-08 |
| 3 | **Terminal-hook gating on `stopped`** | `useTerminal.ts` | UI-07, UI-08 |
| 4 | **Mutation wiring** | `WorkspaceLayout.tsx` (`LeafPanel`) | UI-07, UI-08 |
| 5 | **Responsive drawer width** | `index.css` (`--w-drawer` + media query), `ActivityDrawer.tsx` | UI-09 |
| 6 | **Global focus-visible ring** | `index.css` | UI-10 |
| 7 | **Global custom scrollbar** | `index.css` | UI-11 |

**Out of scope (do not touch):** any lifecycle endpoint / backend, the sidebar-row
stop/start affordance (deferred), tablet (376–768px) width tuning (only ≤375px is in
scope for UI-09), the events poll/redaction (shipped in v1.0), and the v1.0 real-infra
acceptance debt (ACC-01/02/03).

---

## Design System

| Property | Value |
|----------|-------|
| Tool | **none** (hand-built; Tailwind v4 `@theme` CSS-first, no shadcn). shadcn gate: **not applicable** — the design system was established in Phase 2 and is binding; the scope guardrails explicitly forbid introducing a new design system on this shipped UI. No `components.json`, no `tailwind.config.*`. |
| Preset | not applicable |
| Component library | **none** — every surface is hand-rolled on inline `React.CSSProperties` + the existing tokens. **No new runtime UI dependency** is added for any of UI-07..UI-11. |
| Icon library | **inline outline SVG only**, 1.5px stroke, round caps/joins, `currentColor`, `fill:none` — the existing `ICON` spread in `TerminalPanel.tsx`. NO icon font, NO CDN (Registry Safety / PLAT-05). The two new glyphs (Stop square, Start play-triangle) are inline SVG matching the `Grip/Split/Plug/Close/Activity` set. |
| Font (display) | `--font-display` (Space Grotesk 500, system-stack fallback) — the `stopped` placeholder heading only |
| Font (UI/body) | `--font-sans` (Inter 400–500) — placeholder body copy, button `aria-label`s |
| Font (mono) | `--font-mono` (JetBrains Mono) — n/a for the new copy; terminal body keeps mono |
| Theme | inherits `data-theme` on `<html>`; **all four themes (`dark`/`dark-soft`/`medium`/`light`) must render** the new buttons, the placeholder, the focus ring, and the scrollbar with zero hardcoded hue. `--accent-line` and `--border-mid` are defined in every theme block. |
| Max font-weight | **500.** Never 600/700. |
| Casing | **Sentence case** everywhere; uppercase only for the existing 11px tracked overline (not used by this phase). |
| Depth model | **Flat. No gradients, no shadows, no glow.** Surfaces separate by token level + a single hairline border, exactly as the rest of the shell. Pseudo-class / media / scrollbar rules MUST live in `index.css` (inline styles cannot express them). |

---

## Spacing Scale

4px base, inherited **verbatim** from the `@theme` tokens already in
`ui/src/index.css`. No arbitrary values; reuse the existing token names.

| Token | Value | Usage in this phase |
|-------|-------|---------------------|
| xs | 4px | icon-button inner grid gap, spinner ring border math |
| sm | 8px | header button gap (`--space-sm`, existing `headerStyle`), placeholder element gap |
| md | 16px | placeholder horizontal padding, header padding (existing) |
| lg | 24px | placeholder vertical breathing |
| xl | 32px | placeholder vertical breathing (centered column) |
| 2xl | 48px | — |
| 3xl | 64px | — |

**Fixed-chrome dimensions (load-bearing; reuse the existing tokens — do not redefine):**

| Dimension | Value | Source |
|-----------|-------|--------|
| Panel header height | **36px** | `--h-panel-header` (existing; Stop/Start sit in this row) |
| Icon button | **24px × 24px** | reuse `iconButtonStyle` from `TerminalPanel` (existing) |
| Stop/Start glyph SVG | **15px × 15px**, `viewBox="0 0 24 24"` | matches `Split/Plug/Close/Activity` (existing 15px set; Grip is 14px) |
| In-flight spinner (header button) | **14px ring**, 2px border | NEW — sized to sit inside the 24px button without reflow; smaller than the 22px overlay `Spinner` (which stays for connecting/reconnecting) |
| Placeholder Start CTA spinner | **22px ring**, 2px border | reuse the existing overlay `Spinner` component (the placeholder Start awaits ttyd health → seconds) |
| Drawer width token `--w-drawer` | **`min(360px, 100vw)`** default; **`100vw`** at `@media (max-width:375px)` | NEW token; replaces the `DRAWER_WIDTH` literal |
| Focus ring | **2px** solid, **2px** offset | NEW global rule |
| Scrollbar thickness | **`thin`** (Firefox) / **8px** track-box, **6px** visible thumb via padding/border-radius | NEW global rule (see Scrollbar section) |

Intra-component paddings stay on the 4px grid (or within ±2px, as the rest of the
shell does): placeholder copy block centered with `var(--space-xl) var(--space-lg)`
(mirrors the drawer empty state), header button gap `var(--space-sm)`.

**Radius:** reuse `--radius-control` (8px) for the icon buttons and the placeholder
Start CTA (matches `overlayButton`); the scrollbar thumb uses `--radius-full`. No new
radius token.

**Motion:** the in-flight spinners reuse the existing `@keyframes spin` (`0.8s linear
infinite`); the placeholder appears/disappears with the panel status change (no bespoke
animation). All animation honors the existing global `@media (prefers-reduced-motion:
reduce)` block in `index.css` — add no JS-driven animation that bypasses it.

---

## Typography

No new sizes. All values are already on the binding 02/04 type scale and resolve from
`--font-*` tokens. Max weight **500**.

| Role | Family | Size | Weight | Line Height | Usage |
|------|--------|------|--------|-------------|-------|
| Placeholder heading | `--font-display` | 16px | 500 | 1.2 | `Workspace stopped` |
| Placeholder body | `--font-sans` | 12px | 400 | 1.5 | the one-line explanation (see Copywriting) |
| Start CTA label | `--font-sans` | inherit (12px band) | 500 | — | `Start workspace` (reuses `overlayButton` `font: inherit`) |
| Button `aria-label` | — (assistive text) | — | — | — | `Stop workspace` / `Start workspace` |

The Stop/Start header buttons carry **no visible text** (icon-only, like
Split/Detach/Terminate); their accessible name is the `aria-label`. The placeholder is
the only new on-screen copy. No size outside this table; no weight above 500.

---

## Color

Every surface reads **only `--token` variables** — zero hardcoded hex (the binding
"tokens, not hex" rule). The 60/30/10 split is inherited from the shell. This phase
spends accent **only** on the new global focus ring; the new controls are neutral.

| Role | Token | Usage in this phase |
|------|-------|---------------------|
| Dominant (60%) | `--bg`, `--bg-surf` | panel body surface; the `stopped` placeholder sits on `--bg-surf` (same as the term body) |
| Secondary (30%) | `--bg-panel` (header), `--bg-panel-alt` (placeholder Start CTA fill, button hover), `--border` / `--border-mid` (hairlines, spinner track, scrollbar thumb) | the header band + the placeholder CTA reuse `overlayButton` tokens |
| Accent (10%) | `--accent-line` | **only** the global `:focus-visible` ring (V3) and the in-flight spinner top-arc (matches the existing 22px `Spinner` default arc). Nothing else. |
| Status / muted | `--text-muted` (idle icon color, placeholder secondary text), `--text`, `--text-sub` | the Stop/Start buttons use the existing `iconButtonStyle` `--text-muted` resting color + hover `--text` |
| Destructive | `--err` | **NOT used by Stop/Start.** Stop is reversible (LXC down, disk kept) — it is a neutral control, never red. `--err` stays reserved for Terminate's confirm and the error overlay. |
| Gold | `--gold` | **never** used by this phase. Gold is prestige-only (model labels); a reviewer should see zero gold on the new controls/placeholder/ring/scrollbar. |

**Accent reserved for (this phase):** the `--accent-line` `:focus-visible` ring on
every interactive control app-wide (V3), and the in-flight spinner top-arc. **Never** a
button fill, never the Stop or Start glyph color at rest, never the placeholder text,
never the scrollbar thumb (the thumb is `--border-mid`, a neutral). This matches the
shell's "green is the only action color, used sparingly" rule and the 04-UI-SPEC accent
discipline.

**Status→color discipline (single-sourced — do not duplicate):** the workspace status
color map lives in `ui/src/lib/status.ts` (`running=--ok`, `creating=--warn`,
`error=--err`, `stopped/destroyed=--text-muted`). The Stop/Start controls and the
placeholder read status to **gate visibility**, not to recolor anything; any status
chip/dot they render must read `STATUS_COLOR`, never a literal. `stopped` is
`--text-muted` (a calm, non-alarming state — the placeholder must NOT look like an
error).

**Stop vs Detach vs Terminate colour/semantics (keep distinct):**

| Action | Glyph | Resting color | Confirm? | Semantics |
|--------|-------|---------------|----------|-----------|
| **Detach** (existing) | plug | `--text-muted` | no | non-destructive socket close; session keeps running on the worker |
| **Stop** (new, UI-07) | outline square | `--text-muted` | **no** | WS-06 lifecycle stop; LXC down, disk kept, live session ends; reversible |
| **Start** (new, UI-08) | outline play-triangle | `--text-muted` | no | WS-07 lifecycle start; awaits ttyd health, terminal reconnects |
| **Terminate** (existing) | × | `--text-muted` (resting); `--err` on the confirm `Destroy` button | **yes** (overlay) | WS-08 destroy; container + session gone for good |

All four resting glyphs share the neutral `--text-muted`; emphasis (red) appears only
on Terminate's confirm `Destroy` button and the error overlay — never on Stop/Start.

---

## Component Visual + State Contracts

### 1. Stop / Start header buttons (UI-07 / UI-08)

**Placement.** Inline 24px icon buttons in the `TerminalPanel` **header cluster**,
using the existing `iconButtonStyle` (24px grid, transparent bg, `--text-muted`,
`--radius-control`). Order in the right-aligned cluster, left→right:
`Activity · [Stop|Start] · Split · Detach · Terminate`. The Stop/Start button sits
**left of Split** so the destructive Terminate stays rightmost (matching the 04-UI-SPEC
"terminate stays rightmost" rule). Exactly **one** of Stop/Start occupies that slot at
a time (gating below); the slot is empty for `creating`/`error`/`destroyed`.

**Gating (show-only-applicable — NOT show-both-and-disable).**

| `status` | Slot renders |
|----------|--------------|
| `running` | **Stop** (square) |
| `stopped` | **Start** (play-triangle) |
| `creating` | nothing (neither) |
| `error` | nothing (neither) |
| `destroyed` | nothing (row is filtered/gone) |

The backend state machine is the authority: the UI never offers an illegal action.
This mirrors the v1.0 SC-12 posture and the `lib/statemachine.py` TRANSITIONS table.

**Glyphs (inline outline SVG, 15px, `viewBox="0 0 24 24"`, the `ICON` spread):**

- **Stop = outline square.** A centered rounded square, e.g.
  `<rect x="6" y="6" width="12" height="12" rx="1.5" />`. Outline only (`fill:none`,
  stroke 1.5) — distinct from a solid stop block, consistent with the outline set.
- **Start = outline play-triangle.** A right-pointing triangle, e.g.
  `<path d="M8 5v14l11-7z" />` rendered as an outline (stroke 1.5, round joins,
  `fill:none`). Geometry is Claude's discretion within "outline play-triangle, 15px,
  matches the existing set."

**Resting / hover / focus states** (reuse the existing icon-button treatment):

- Resting: `color: var(--text-muted)`, transparent bg.
- Hover: `background: var(--bg-hover)`, `color: var(--text)` (matches the other header
  buttons — apply via the same mechanism the existing buttons use; no new hover token).
- Focus-visible: the global `--accent-line` 2px ring (V3) — these inline icon buttons
  have **no focus affordance today**; V3 is what gives them one.

**In-flight (pending) state.** While the stop/start mutation is `isPending`:

- The button is **disabled** (`disabled` attribute → no double-fire) and shows an
  **inline 14px spinner** in place of the glyph (reuse `@keyframes spin`, 2px border,
  track `--border-mid`, top-arc `--accent-line`). The 14px size keeps the 24px button
  from reflowing.
- Start's pending state can last **seconds** (WS-07 awaits ttyd health); Stop's is
  brief. Both show the same spinner.
- The button keeps its `aria-label`; add `aria-busy="true"` while pending so assistive
  tech announces the in-flight state.
- **No optimistic status flip.** Status is **never** mirrored into Zustand — the server
  is the source of truth. The mutation's `onSettled` invalidates `WORKSPACES_KEY`; the
  existing **~3s `useWorkspaces` poll** drives the final `stopped`/`running` state, which
  re-renders the header (swapping Stop↔Start) and the body (placeholder↔terminal). The
  spinner clears when the mutation settles; the control swap follows on the next poll
  reconciliation.

**Error (rejection) handling.** A backend rejection (e.g. an illegal transition that
slipped through, or a 5xx) surfaces as a **readable envelope error**, not a broken
state: the mutation's `onError` logs (console) and the next poll re-lists the true
status so the UI self-corrects (same pattern as the existing destroy `onError` in
`LeafPanel`). The control never wedges into a permanent spinner — clearing on
`onSettled` guarantees the disabled+spinner state ends whether the call succeeds or
fails. (A toast/inline banner is **not** required for v1.1; the self-correcting poll +
the legible `stopped`/`running`/`error` surfaces are the contract.)

### 2. `stopped` placeholder body (UI-07 / UI-08)

When `status === "stopped"`, the panel **body** renders a dedicated placeholder
**instead of** the connecting/reconnecting/error overlays — stopping must never produce
a scary reconnect-loop or error state.

**Anatomy** (a centered muted column over the panel body, mirroring the drawer/sidebar
empty-state construction):

```
            [ outline square glyph, 22px, --text-muted ]   (optional, decorative)
                          Workspace stopped                 (display 16px/500, --text-sub)
        This workspace is stopped. Start it to reconnect    (sans 12px/400, --text-muted)
              the terminal and pick up where you left off.
                       [ ▷ Start workspace ]                (overlayButton style + play glyph)
```

- **Container:** position over the body (the body's `position:relative` wrapper already
  exists). Reuse the `overlayBase` style object **or** a sibling style object
  (Claude's discretion per 05-CONTEXT) — but the background must be the **opaque-ish
  calm wash** consistent with a non-error state. Recommended: `background: var(--bg-surf)`
  (fully cover the term body) rather than the dim `rgba(26,28,26,.78)` error/reconnect
  scrim — a stopped workspace is a resting state, not an alert.
- **Heading:** `Workspace stopped` — `--font-display`, 16px, weight 500, `--text-sub`.
- **Body copy:** see Copywriting. `--font-sans`, 12px, weight 400, `--text-muted`,
  `max-width ~260px`, centered (matches the terminate-confirm copy width).
- **Start CTA:** a real `<button>` reusing the `overlayButton` style (`--bg-panel-alt`
  fill, `0.5px --border-mid`, `--radius-control`, `padding: 5px 12px`, `color: --text`)
  with the **play-triangle glyph + `Start workspace` label**. Clicking it fires the same
  `useStartWorkspace` mutation as the header Start button; while pending it disables and
  shows the **22px** spinner (the placeholder has room for the larger ring) — and the
  header Start button (gated to `stopped`) also reflects pending. On success the ~3s poll
  flips status to `running`; the placeholder unmounts and the terminal mounts/reconnects.
- **A11y:** the placeholder is a `role="status"` `aria-live="polite"` region (it is a
  resting state announcement, not an alert). The Start CTA is a focusable button with the
  global focus ring; on `stopped` it is the natural focus target.

**Terminal-hook gating (`useTerminal`).** `useTerminal` already early-returns its effect
when `status !== "running"` (line ~178: `if (!container || status !== "running") return`)
and tears the socket/term down on the cleanup when `status` leaves `running`. This phase
**confirms and tests** that contract for `stopped`: while `status === "stopped"` the hook
**must not** open a socket, must not enter the reconnect/backoff loop, and must not render
the connecting/reconnecting/error overlays — the `stopped` placeholder owns the body. On
the `running → stopped` transition the socket tears down (the terminal disconnects,
criterion 1); on `stopped → running` (after Start) the effect re-runs and reconnects
(criterion 2). The panel must branch the body on `status === "stopped"` **before** the
`termStatus`-driven overlays so a transient `termStatus` value can't flash an error scrim
during the stop.

### 3. Mutation wiring (`WorkspaceLayout.LeafPanel`)

`LeafPanel` already owns the per-workspace mutation wiring (it wires
`useDestroyWorkspace → onTerminate`). Add the analogous wiring: `useStopWorkspace` and
`useStartWorkspace` (both already exported from `useWorkspaces.ts`; **no new hook**)
into new `onStop`/`onStart` props passed to `TerminalPanel`. Reconcile keeps `stopped`
panels mounted (only `gone`/`destroyed` leaves drop) — verified in the existing reconcile
(`isVisibleStatus` filters only `destroyed`; the mosaic reconcile drops leaves whose id
left the live set, and a stopped workspace is still in the list). The mutations'
`onSettled` invalidates `WORKSPACES_KEY` (already wired in the hooks).

### 4. Responsive drawer width (UI-09 / V2)

**Problem (04-UI-REVIEW Pillar 5):** `ActivityDrawer.tsx` hardcodes
`DRAWER_WIDTH = "min(360px, 100vw)"`; an inline style cannot express a breakpoint, so on
a 375px phone the drawer renders 360px (a cramped panel with a ~15px scrim sliver) instead
of a full-width sheet.

**Fix (locked, V2):**

- Add a `--w-drawer` token to `index.css`. Default: `--w-drawer: min(360px, 100vw)`.
  Place it with the fixed-chrome dimensions in the `@theme` block (alongside `--w-sidebar`,
  `--w-modal`) so it is a first-class layout token. (It need not be re-declared per theme —
  it is a dimension, not a color.)
- Add a media override: `@media (max-width: 375px) { :root { --w-drawer: 100vw } }`
  (apply to the same scope the token is declared on). **375px** is the locked phone
  breakpoint (matches the phone-375 UAT screenshot and the UI-09 ≤375px wording).
- In `ActivityDrawer.tsx`, replace `width: DRAWER_WIDTH` with
  `width: "var(--w-drawer)"`. The component stays inline-style; the responsiveness lives
  in the token. Update the now-inaccurate `DRAWER_WIDTH` comment (the 04-UI-REVIEW flagged
  it as misleading).

**Result:** full-width sheet **≤375px**, 360px panel **>375px**. Tablet (376–768px) tuning
is explicitly **out of scope** for v1.1 (only the ≤375px phone case). The drawer stays
right-anchored in both bands; the top bar (52px) and status bar (32px) never grow or shrink.

### 5. Global focus-visible ring (UI-10 / V3)

**Problem (04-UI-REVIEW Pillar 6):** no `:focus-visible` rule exists anywhere in `ui/src`;
the inline icon buttons have no Burrow focus affordance (they rely on the UA default, and
the drawer even sets `outline:"none"`).

**Fix (locked, V3):** add **one global rule** to `index.css`:

```css
:focus-visible {
  outline: 2px solid var(--accent-line);
  outline-offset: 2px;
}
```

- **DRY:** one rule covers every interactive control app-wide — the new Stop/Start
  buttons, the placeholder Start CTA, the existing header buttons, sidebar rows, modal
  inputs, the drawer close `×`, and the focusable drawer region.
- `--accent-line` is defined per-theme, so the ring renders correctly in all four themes
  (it is the single app-wide focus color, matching the active-panel `--accent-line` ring
  and the sidebar active bar).
- **2px solid, 2px offset** (locked). Use `:focus-visible` (keyboard/programmatic focus),
  **not** `:focus`, so a mouse click does not paint the ring.
- Remove or neutralize the `outline:"none"` the `ActivityDrawer` `<aside>` sets
  (`drawerStyle`), so the contracted ring is not suppressed on the drawer container. (If
  the bare `<aside>` should not show a ring, scope the removal to keep `:focus-visible`
  working on the controls inside.)
- Honors `prefers-reduced-motion` trivially (a static outline, no animation).

### 6. Global custom scrollbar (UI-11 / V4)

**Problem (04-UI-REVIEW Pillar 6):** no `::-webkit-scrollbar` rule exists; scrollable
surfaces use the native UA scrollbar, which clashes with the flat Burrow surfaces across
themes.

**Fix (locked, V4):** add a **global** custom scrollbar to `index.css`, tokens only:

```css
/* Chromium / WebKit */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
  background: var(--border-mid);
  border-radius: var(--radius-full);
  border: 2px solid transparent;   /* inset the thumb to ~4px visible on an 8px track */
  background-clip: padding-box;
}
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

/* Firefox */
* { scrollbar-width: thin; scrollbar-color: var(--border-mid) transparent; }
```

- **Thumb = `--border-mid`** (locked), on a **transparent track**. Hover deepens to
  `--text-muted` (a neutral; never accent, never gold).
- **`scrollbar-width: thin`** + **`scrollbar-color`** for Firefox.
- **Tokens only** — `--border-mid` and `--text-muted` are defined per theme, so the
  scrollbar renders correctly across all four. Zero hex.
- **Applies to** the drawer list, the terminal body (`.term`, `overflow-y:auto`), and the
  sidebar list — every scroll surface inherits the global rule (the 05-CONTEXT V4 scope).
  No per-surface scrollbar override is needed.
- The xterm.js terminal renders its own canvas/viewport; the global rule styles the panel
  body's own scrollbar. Do not restyle xterm's internal scrollbar beyond what the global
  rule reaches.

---

## Accessibility (binding)

- **Stop/Start buttons** are real `<button type="button">` with an explicit
  `aria-label` (`Stop workspace` / `Start workspace`) — icon-only, so the label is the
  accessible name (matches Split/Detach/Terminate). While pending: `disabled` +
  `aria-busy="true"`.
- **`stopped` placeholder** is a `role="status"` `aria-live="polite"` region (resting
  state, not an alert — contrast the error overlay's `role="alert"` /
  `aria-live="assertive"`). The Start CTA is the focusable element inside it.
- **Focus ring (V3):** every focusable control shows the `--accent-line` 2px
  `:focus-visible` ring — the single app-wide focus color. This is the affordance the
  inline icon buttons lacked. Never remove an outline without this replacement.
- **No color-only state.** `stopped` is conveyed by the **placeholder text**
  (`Workspace stopped`) and the sidebar overline (`stopped` label + `--text-muted` dot),
  not color alone. The Stop/Start affordance is conveyed by the glyph **plus** the
  `aria-label`, not glyph shape alone.
- **Keyboard:** Stop/Start/Start-CTA are tabbable and Enter/Space-activated (native
  `<button>`). The pending `disabled` state removes them from the tab order until settled
  — acceptable, as the action is in flight.
- **Motion:** the in-flight spinners reuse `@keyframes spin`, stilled by the existing
  global `prefers-reduced-motion` block. The drawer slide (untouched) keeps honoring it.
- **Scrollbar (V4):** styling-only; does not change keyboard scroll or the a11y tree.

---

## Copywriting Contract

Sentence case, second-person, technical, unhedged — consistent with the 02/04-UI-SPEC
voice (cf. the terminate-confirm `Destroy {name}? …` and the drawer empty-state copy).
The middle-dot `·` separator and the real ellipsis `…` character are used where relevant.

| Element | Copy |
|---------|------|
| Primary CTA (this phase) | **`Start workspace`** (the placeholder Start CTA — specific verb + noun; the play-triangle glyph precedes it) |
| Stop button label (a11y) | `Stop workspace` |
| Start button label (a11y) | `Start workspace` |
| `stopped` placeholder heading | `Workspace stopped` |
| `stopped` placeholder body | `This workspace is stopped. Start it to reconnect the terminal and pick up where you left off.` |
| In-flight (optional, a11y) | the button's existing `aria-label` + `aria-busy="true"`; no visible "Starting…" text required (the spinner conveys it). If a visible micro-label is added to the placeholder while Start is pending, use `Starting…` (sentence case, real ellipsis). |
| Empty state (grid/sidebar/drawer) | **unchanged** — owned by `WorkspaceLayout`/`WorkspaceList`/`ActivityDrawer`; this phase adds none. |
| Error state | **no new error copy.** Stop/Start failures self-correct via the poll; the existing error overlay (`Session unavailable. the worker isn't ready.`) and the sidebar `error` overline cover the surfaced-error path. |

**Destructive actions this phase:** **none.** Stop is **reversible** (LXC stopped, disk
state preserved) — by locked decision it fires **immediately with no confirmation**. The
one destructive action in the panel, **Terminate**, keeps its existing confirm overlay
(`Destroy {name}? The container and its session are gone for good.`) — unchanged, out of
this phase's scope. Therefore this contract declares **no new destructive confirmation**.

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official | none | not applicable — no shadcn in this project (hand-built on Tailwind v4 `@theme` tokens) |
| third-party | none | not applicable — no registry fetch occurs; the vetting gate is not triggered |

No component registries are used. Every surface is hand-built on the existing tokens and
reuses established patterns: the `TerminalPanel` `iconButtonStyle` + inline-SVG icon set,
the `overlayBase`/`overlayButton`/`Spinner` overlay patterns, and the drawer/sidebar
empty-state construction. **No new runtime UI dependency** is added for any of UI-07..UI-11
(no button/dialog/icon library). The two new glyphs are inline SVG (no icon font, no CDN —
PLAT-05). No `shadcn view`/registry call is made.

---

## Security / Posture Reconciliation (binding)

- **No external font or icon CDN** — inherits the shell's self-hosted-fonts / inline-SVG
  posture (PLAT-05). The Stop/Start glyphs are inline SVG; the design mockup's Google-Fonts
  `<link>` is a design artifact only and is **not** reintroduced (the shipped app resolves
  `--font-*` to system stacks; the global `grep googleapis|gstatic|jsdelivr` assert must
  stay green).
- **Server is the source of truth.** Stop/Start never mirror status into Zustand; the only
  new network calls are the **same-origin** `POST /api/v1/workspaces/{id}/stop` and
  `/start` (via the existing hooks). No new endpoint, no third-party request.
- **Tokens only, zero hex** across all four themes — the focus ring, scrollbar, spinner,
  buttons, and placeholder all resolve from `--token`. A four-theme render must show no
  orphaned hue and no gold on the new controls.

---

## Acceptance-Checkable Visual Criteria (gsd-ui-auditor grades against these)

1. **Gating, not disabling.** `running` shows **Stop** (square) only; `stopped` shows
   **Start** (play-triangle) only; `creating`/`error`/`destroyed` show neither. The UI never
   offers an illegal lifecycle action.
2. **No Stop confirm; Terminate keeps its confirm.** Clicking Stop fires immediately (no
   overlay); Terminate still opens its `Destroy {name}? …` confirm. Stop is neutral
   (`--text-muted`), never red.
3. **In-flight feedback.** While stop/start is pending the button is `disabled` +
   `aria-busy` and shows the 14px spinner (top-arc `--accent-line`, track `--border-mid`);
   it clears on settle and never wedges.
4. **No optimistic flip.** Status is never written to Zustand; the ~3s `useWorkspaces` poll
   drives the Stop↔Start swap and the placeholder↔terminal swap after `onSettled`
   invalidation.
5. **`stopped` placeholder.** A stopped panel body shows the `Workspace stopped` heading +
   the locked body copy + a `Start workspace` CTA over a calm `--bg-surf` wash —
   **not** the connecting/reconnecting/error overlay. It is `role="status"`/`aria-live=
   polite`, never `role="alert"`.
6. **Terminal hook gated on `stopped`.** While `status === "stopped"`, `useTerminal` opens
   no socket, runs no reconnect/backoff, and renders no overlay; the socket tears down on
   `running→stopped` (terminal disconnects) and reconnects on `stopped→running`.
7. **Tokens, not hex.** No hardcoded color on any new surface; every color resolves from a
   `--token`. All four `data-theme`s render the buttons, placeholder, ring, and scrollbar
   with no orphaned hue. **Zero `--gold`** on the new controls.
8. **Responsive drawer (V2).** `--w-drawer` is `min(360px,100vw)` by default and `100vw`
   under `@media (max-width:375px)`; `ActivityDrawer` reads `width:var(--w-drawer)`. At
   375px the drawer is full-width; above it, 360px. (Playwright asserts drawer width ==
   viewport width at 375px.)
9. **Focus ring (V3).** A single global `:focus-visible { outline: 2px solid
   var(--accent-line); outline-offset: 2px }` exists in `index.css`; keyboard-focusing any
   interactive control (Stop/Start, the placeholder CTA, the drawer `×`, sidebar rows)
   shows the `--accent-line` ring across all four themes. The drawer `<aside>`'s
   `outline:"none"` no longer suppresses control rings.
10. **Custom scrollbar (V4).** `index.css` has `::-webkit-scrollbar`/`-thumb`/`-track`
    (thumb `--border-mid`, transparent track) + Firefox `scrollbar-width: thin` /
    `scrollbar-color: var(--border-mid) transparent`; the drawer list, terminal body, and
    sidebar list use it (no native scrollbar). Tokens only.
11. **Three actions stay distinct.** Detach (plug, socket close), Stop (square, WS-06
    lifecycle), and Terminate (×, WS-08 destroy) are visually and semantically separate;
    Stop is never confused with Detach or Terminate.
12. **No new runtime dependency / no CDN.** No button/dialog/icon library is added; the
    glyphs are inline SVG; the `googleapis|gstatic|jsdelivr` CDN assert stays green.

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS
- [ ] Dimension 4 Typography: PASS
- [ ] Dimension 5 Spacing: PASS
- [ ] Dimension 6 Registry Safety: PASS

**Approval:** pending
