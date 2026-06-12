<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
---
phase: 4
slug: hardening-release
status: approved
reviewed_at: 2026-06-11
shadcn_initialized: false
preset: none
created: 2026-06-11
surface: activity-drawer
requirement: UI-06
---

# Phase 4 — UI Design Contract (Activity Drawer)

> Visual and interaction contract for the **one** frontend surface in Phase 4: the
> per-workspace **activity drawer** (UI-06) that surfaces the workspace event log.
> The rest of Phase 4 (reaper, auto-stop, capacity-race fix, Dockerfiles, CI/CD
> supply-chain) is backend/infra and is **out of UI-SPEC scope**.
>
> **Binding inheritance:** this drawer is an *additive* surface on the established
> Burrow shell. It reuses the Phase-2 design system verbatim — the tokens in
> `ui/src/index.css` + `ui/src/lib/themes.ts`, the status→color map in
> `ui/src/lib/status.ts`, the type scale, gold/green discipline, and copywriting
> conventions from `.planning/phases/02-terminal-proxy-react-ui/02-UI-SPEC.md`.
> **Do not invent a new palette, type scale, or aesthetic.** Where this spec is
> silent, the 02-UI-SPEC governs.
>
> **Locked upstream (do not re-litigate):** every drawer behavior in
> `04-CONTEXT.md` "Event Drawer UI (UI-06)" is a user decision — right-side
> slide-in, opened per-workspace from the row/panel header, TanStack-Query poll of
> `GET /api/v1/workspaces/{id}/events` with a `refetchInterval` while open,
> newest-first rows, color-coded type badges + redacted `data`, `boot.error`
> emphasized. This document encodes those decisions; it does not re-ask them.

---

## Surface Scope (what this contract covers)

ONE surface, the **activity drawer** (`ActivityDrawer` + `useWorkspaceEvents`):

- the drawer open / closed states + slide-in transition,
- the drawer trigger (where it lives, what it looks like),
- the four data states: **loading**, **empty**, **error**, **populated**,
- the **event row** anatomy (timestamp · type badge · redacted `data` summary),
- the **`boot.error` emphasis** treatment,
- **scroll / overflow** behavior (long logs),
- **responsive width**,
- **interaction states** (hover, focus) + **accessibility** (focus trap, `Esc`,
  ARIA, `aria-live`, reduced-motion).

Out of scope here: the reaper/auto-stop/capacity backend, the events *endpoint*
(already shipped, WS-11 / 01-04), and all CI/CD + Docker work.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | **none** (hand-built; Tailwind v4 `@theme` CSS-first, no shadcn). shadcn gate: **not applicable** — design system already established in Phase 2; project explicitly ships no component registry (02-UI-SPEC Registry Safety). |
| Preset | not applicable |
| Component library | none — the drawer is hand-rolled. No new runtime UI dep is added for UI-06 (no drawer/dialog library; build it on a positioned `aside` + the existing tokens). |
| Icon library | **inline outline SVG only**, 1.5px stroke, `currentColor`. NO icon font, NO CDN. Matches `TerminalPanel` icon pattern. The drawer needs at most two glyphs: an **activity/list** trigger icon and a **×** close icon (the `×` is already drawn in `TerminalPanel` as `CloseIcon` — reuse that shape). |
| Font (display) | Space Grotesk 500 — drawer title only |
| Font (UI/body) | Inter 400–500 — row labels, empty/error copy |
| Font (mono) | JetBrains Mono — timestamps + the redacted `data` summary + the event type token |
| Theme | inherits `data-theme` on the app root; all four themes (`dark`/`dark-soft`/`medium`/`light`) must render the drawer with zero hardcoded hue |
| Max font-weight | **500.** Never 600/700. |
| Casing | **Sentence case** everywhere; uppercase only for the 11px tracked overline (drawer "ACTIVITY" label). |
| Depth model | **Flat. No gradients, no shadows, no glow.** The drawer separates from the grid by its surface level (`--bg-surf`) + a single hairline left border. A scrim behind it (if used) is a flat translucent wash, never a shadow. |

---

## Spacing Scale

4px base, inherited verbatim from the `@theme` tokens already in `ui/src/index.css`.
No arbitrary values.

| Token | Value | Usage in the drawer |
|-------|-------|---------------------|
| xs | 4px | badge inner padding, dot/label gaps |
| sm | 8px | row internal gap (timestamp ↔ badge ↔ data), badge gaps |
| md | 16px | drawer horizontal padding, header padding, row vertical padding |
| lg | 24px | empty/error-state padding |
| xl | 32px | empty-state vertical breathing |
| 2xl | 48px | — |
| 3xl | 64px | — |

**Fixed-chrome exceptions (load-bearing, consistent with the existing shell):**

| Dimension | Value | Source |
|-----------|-------|--------|
| Drawer width (desktop ≥1024px) | **360px** | new; sits between sidebar `228px` and modal `400px`; right-anchored, fixed |
| Drawer header height | **36px** | reuse `--h-panel-header` (matches the panel header the trigger lives in) |
| Trigger icon button | **24px** | reuse `iconButtonStyle` from `TerminalPanel` |
| Type badge height | **18px** | new; compact inline pill |
| Status/type dot | **7px** | reuse `--sz-status-dot` |
| Row min-height | **44px** | new; comfortable scan target, ≥ the a11y touch floor |

Intra-component paddings use 4px-grid values (row `10px/12px`, badge `1px 6px`,
header `0 16px`) — keep within ±2px of a grid step, as the rest of the shell does.

**Radius:** drawer container is **square-edged on its anchored (right) edge**;
inner cards/badges use the existing tokens — type badge `--radius-chip` (6px),
any inner grouping `--radius-control` (8px), the drawer surface needs no outer
radius because it is flush to the viewport's right edge.

**Motion:** slide-in via `transform: translateX(100%) → 0` over the existing
`--ease-ui` `cubic-bezier(0.16,1,0.3,1)`, duration `--dur-hover`-band but slower:
**200ms** (a panel transition, not a hover). The scrim fades `0 → 1` opacity over
the same 200ms. **Honor `prefers-reduced-motion`** — the existing global
`@media (prefers-reduced-motion: reduce)` block already collapses transition
duration to ~0; the drawer must rely on that (no JS-driven animation that bypasses
it). New rows appended on a poll **must not** animate-flash the whole list.

---

## Typography

Three families, max weight 500. Scale lifted from the 02-UI-SPEC; the drawer adds
no new sizes.

| Role | Family | Size | Weight | Line Height | Usage |
|------|--------|------|--------|-------------|-------|
| Drawer title | Space Grotesk | 16px | 500 | 1.2 | "Activity" / "{workspace name} activity" |
| Overline | Inter | 11px | 500 | — | uppercase "ACTIVITY", tracked 1.3px (matches sidebar `WORKSPACES`) |
| Row type label | Inter | 12px | 500 | 1.4 | the human-readable event label inside the badge |
| Timestamp | JetBrains Mono | 11.5px | 400 | 1.4 | per-row time, muted |
| Data summary | JetBrains Mono | 11.5px | 400 | 1.5 | the redacted `data` key·value summary |
| Empty/error heading | Inter | 14px | 500 | 1.4 | state heading |
| Empty/error body | Inter | 12px | 400 | 1.5 | state body + next step |

Body/data line-height target `1.4–1.6`; title `≤1.2`. No size outside this table.

---

## Color

The drawer reads **only `--token` variables** — zero hardcoded hex (criterion 1).
The 60/30/10 split is inherited from the shell; the drawer occupies the **secondary
(30%) surface band** and spends accent only on its focus ring.

| Role | Token | Usage in the drawer |
|------|-------|---------------------|
| Dominant (60%) | `--bg` | the scrim wash behind the drawer (flat translucent `--bg` at low alpha), drawer is NOT the page bg |
| Secondary (30%) | `--bg-surf` (drawer body) · `--bg-panel` (header) · `--bg-panel-alt` (badge fill, row hover) | the drawer is a raised secondary surface, same band as the sidebar/panel headers |
| Accent (10%) | `--accent-line` | **only** the focus-visible ring on the close button, trigger, and the scrollable region — nothing else |
| Destructive / emphasis | `--err` | the `boot.error` row emphasis + the poll-error strip |

**Accent reserved for (drawer):** the `--accent-line` focus ring on interactive
controls (close `×`, the trigger, focusable scroll region). **Never** a badge fill,
never row text, never the slide affordance. This matches the shell's "green is the
only action color, used sparingly" rule.

**Gold is NOT used in the drawer.** Gold is prestige-only (model labels, stats,
uptime, capacity numbers) per 02-UI-SPEC; the event log carries none of those, so
no `--gold` appears here. A reviewer should see zero gold in the drawer.

### Event type → badge color map (binding)

The badge **dot + text color** maps each event type to the existing status-color
language (`ui/src/lib/status.ts` tokens), so the drawer speaks the same color as
the sidebar. The badge **background** is always the neutral `--bg-panel-alt`
(a flat pill); only the dot + label color varies. **`boot.error` additionally gets
the row-level emphasis** described below.

> **Important — use the real backend event-type strings.** The backend emits
> **namespaced** types (verified in `api/services/workspaceService.py`,
> `api/routers/terminal.py`), NOT the bare shorthand listed in `04-CONTEXT.md`.
> The map MUST key off these exact strings:

| Event `type` (exact string) | Dot / label token | Human label (sentence case) | Notes |
|------------------------------|-------------------|------------------------------|-------|
| `workspace.created` | `--ok` (green) | `Created` | |
| `workspace.started` | `--ok` (green) | `Started` | |
| `workspace.stopped` | `--text-muted` (muted) | `Stopped` | if `data.reason === "idle"` → label `Auto-stopped (idle)`, dot `--warn` |
| `workspace.destroyed` | `--err` (red) | `Destroyed` | |
| `terminal.connected` | `--accent-line` (green-line) | `Terminal connected` | |
| `terminal.disconnected` | `--text-muted` (muted) | `Terminal disconnected` | |
| `boot.error` | `--err` (red) | `Boot error` | **emphasized row** (see below) |
| `bootconfig.persisted` | `--text-sub` (secondary) | `Boot config persisted` | |
| `reaper.*` (Phase-4 new — any `reaper.`-prefixed type, e.g. `reaper.destroyed`, `reaper.vmid_freed`, `reaper.timed_out`) | `--warn` (amber) | humanize the suffix in sentence case (e.g. `Reaper · destroyed`) | from the new reconciler |
| **unknown / any other type** | `--text-sub` (secondary) | render the raw `type` string verbatim in mono | forward-compatible fallback — a new backend event must never break the drawer |

The map is a single source of truth (mirror the `status.ts` pattern: a
`EVENT_BADGE` record in `ui/src/lib/events.ts`, tokens only, no hex). `destroyed`
workspaces are filtered out of the *sidebar*, but their event rows **remain visible
in the drawer** — the log is an audit trail, not a live-status list.

### `boot.error` emphasis (binding)

A `boot.error` row is the one visually-emphasized row:

- a **2px `--err` left-edge bar** on the row (same affordance language as the active
  sidebar row's `--accent-line` bar, but `--err`),
- row background `--signal`-style tint: `--err` at low alpha — reuse the existing
  pattern from `WorkspaceList`'s poll-error strip (`background: var(--bg-panel-alt)`
  with a `borderLeft: 2px solid var(--err)`); do **not** introduce a new token,
- the `data.reason` (already server-redacted via `_safe()`) is shown in full mono
  beneath the badge, `--err` colored, never truncated mid-word.

No other row type gets a left bar or a tinted background.

---

## Component Visual + State Contracts

### Drawer trigger — where it opens from

The drawer is opened **per-workspace** from two equivalent entry points (CONTEXT:
"from the workspace row/panel header"):

1. **Panel header (`TerminalPanel`)** — a new **activity icon button** (24px,
   `iconButtonStyle`, `--text-muted`, hover `--bg-hover` + `--text`) added to the
   header button cluster, placed **left of `split`** so the destructive `terminate`
   stays rightmost. `aria-label="Activity log"`. Inline outline SVG (a list/pulse
   glyph, 1.5px stroke). Opens the drawer for *that* panel's workspace id.
2. **Sidebar row (`WorkspaceList`)** — opening from the row is acceptable but the
   panel-header trigger is canonical; if added to the row it must not steal the
   row's primary click (which focuses the panel). Prefer a hover-revealed 24px icon
   at the row's right edge, same `aria-label`.

Exactly **one** drawer is open at a time, bound to a single `activeEventsWorkspaceId`
(new client state — a `useState`/Zustand field; it is **ephemeral**, not persisted,
unlike the mosaic layout). Re-triggering for a different workspace swaps the
contents in place.

### Drawer container — `ActivityDrawer` — right-anchored, 360px, `--bg-surf`

- **Anchor:** fixed to the **right** edge of the viewport, full content height
  (top under the 52px top bar is acceptable; it must never overlap or push the 52px
  top bar or 32px status bar — those chrome bars never move).
- **Surface:** `background --bg-surf`, a single **0.5px `--border` left border**, no
  outer radius on the right edge, no shadow.
- **Scrim (optional but recommended):** a flat `--bg` wash at low alpha
  (`rgba`-via-token is fine using `--accent-bg`-style alpha, but prefer a dedicated
  translucent `--bg`) behind the drawer; **click-scrim closes** the drawer (no data
  is lost — it is a read-only view). The scrim must NOT darken the top/status bars
  into looking disabled if they remain interactive; if simpler, the drawer may open
  without a scrim and rely on `Esc` + the `×`.
- **Open/closed:** closed = `translateX(100%)` (off-canvas right) + `aria-hidden`,
  not in the tab order; open = `translateX(0)`. Transition per Motion above.
- **Header (36px, `--bg-panel`, hairline bottom):** an `ACTIVITY` overline (11px,
  tracked, `--text-muted`) **or** the title `{name} activity` (Space Grotesk 16px),
  a spacer, and a **`×` close button** (24px `iconButtonStyle`, `aria-label="Close
  activity log"`).
- **Body:** the scrollable event list (newest-first), `overflow-y: auto`, inner
  scroll only — the drawer chrome never grows. Thin neutral scrollbar (the `_ds`
  3px scrollbar already in the global CSS applies).

### Event row anatomy

A single row (`min-height 44px`, `padding 10px 16px`, `--bg-surf`, hairline-bottom
between rows; hover `--bg-panel-alt`):

```
[7px dot]  [type badge — sentence-case label]        [HH:MM:SS  ·  relative]
           [redacted data summary — mono, --text-sub, wraps]
```

- **Dot:** `7px`, color per the event→token map, `aria-hidden` (the badge label is
  the accessible text).
- **Type badge:** an `18px` pill, `background --bg-panel-alt`, hairline, `radius 6px`,
  the human label (Inter 500, 12px) in the mapped token color. For the `unknown`
  fallback the raw `type` is rendered in **mono** so it is visibly a system string.
- **Timestamp:** mono `11.5px`, `--text-muted`, right-aligned within the row top
  line. Show an absolute time (`HH:MM:SS`, from `createdAt`) and optionally a
  relative hint (`· 3m ago`); the absolute time is canonical and must be present.
- **Data summary:** the redacted `data` object rendered as compact
  `key: value · key: value` mono text (`--text-sub`, `11.5px`, line-height 1.5),
  wrapping. `boot.error`'s `reason` and `workspace.stopped`'s `reason: idle` surface
  here. **Render nothing** (omit the second line) when `data` is `{}`.
- **No row is interactive** beyond hover — rows are read-only log entries. The row
  is therefore a non-button `<li>`; only the close `×`, the trigger, and the scroll
  region are focusable.

### State: loading

First fetch in flight (no cached data): **3–4 shimmer rows** matching the
`WorkspaceList` `ShimmerRows` pattern (`--bg-hover`, `pulse 1.4s`, `opacity 0.5`,
`aria-hidden`). No hard spinner block. Reuse the existing shimmer treatment so the
drawer's loading state reads identically to the sidebar's.

### State: empty

Fetch succeeded, zero events (rare — a workspace logs `workspace.created` at birth,
but the contract must define it): a **centered muted column** in the body —
heading + body, same construction as the sidebar empty state. Copy in the
Copywriting table.

### State: error

The poll failed: a small inline **`--err` strip at the body top** (reuse the exact
`WorkspaceList` poll-error pattern — `background --bg-panel-alt`,
`borderLeft 2px solid --err`, `--err` text, `role="alert"`), with the **last-known
rows kept beneath** it; auto-recovers on the next `refetchInterval` tick. Never a
full-drawer error takeover that discards already-loaded history.

### State: populated (live poll)

- **Order: newest-first.** The endpoint returns events **oldest-first** (verified:
  `getEvents` orders by `(createdAt, rowid)`); the drawer **must reverse client-side**
  — `[...events].reverse()` (or sort desc). Do not assume the endpoint is sorted for
  the UI.
- **Poll:** `useWorkspaceEvents(id, enabled)` mirrors `useWorkspaces` —
  `useQuery({ queryKey: ['workspace-events', id], queryFn: () =>
  api<WorkspaceEvent[]>(\`/workspaces/${id}/events\`), refetchInterval, enabled })`.
  `enabled` is `drawerOpen && !!id` so polling **only runs while the drawer is open**
  (CONTEXT). Recommend `refetchInterval` **3000ms** to match the workspace-list poll
  cadence (one consistent live tempo across the app).
- **Append behavior:** new events appear at the **top** on each poll; the existing
  rows must not re-mount / flash (stable React keys = the event `id`). The scroll
  position is preserved unless the user is pinned at the top.
- The `WorkspaceEvent` type mirrors `api/models/event.py`:
  `{ id, workspaceId, type, data, createdAt }` (camelCase; add to
  `ui/src/types/workspace.ts` or a new `types/event.ts`).

---

## Scroll / Overflow

- The drawer **header** (36px) is fixed; only the **body list** scrolls
  (`overflow-y: auto`, `min-height: 0` in a flex column).
- Long logs scroll within the body; the drawer never grows the viewport or pushes
  the top/status bars.
- Long `data` summaries **wrap** (never horizontal-scroll a row); the type badge and
  timestamp stay on the top line, the data summary flows to the second line.
- The 3px neutral scrollbar from the global CSS applies; do not restyle it.

---

## Responsive Behavior

- **Desktop (≥1024px):** right-anchored drawer, fixed **360px**, slides over the
  Mosaic grid (does not reflow the grid — it overlays). The scrim (if present)
  covers the grid + sidebar but not necessarily the top bar.
- **Tablet (640–1023px):** drawer widens to **min(360px, 80vw)** and still
  right-anchors; the scrim is recommended here so the smaller workspace is clearly
  backgrounded.
- **Phone (<640px):** drawer goes **full-width** (`100vw`) as a sheet over the
  single-panel focus mode; the `×` and `Esc` are the close affordances; the scrim is
  full-screen. xterm/grid beneath is untouched.
- In every breakpoint the top bar (52px) and status bar (32px) **never grow or
  shrink**, and only the drawer body scrolls.

---

## Accessibility (binding)

- **Role:** the drawer is a `role="dialog"` (a non-modal-ish complementary panel is
  acceptable, but treat it as a dialog for focus management) with
  `aria-label="{workspace name} activity log"`. `aria-modal="true"` only if a scrim
  blocks the rest of the UI.
- **Focus trap:** while open, Tab cycles within the drawer (close button → scroll
  region → close button). On open, focus moves to the drawer (the close `×` or the
  drawer container). On close, focus **returns to the trigger** that opened it.
- **`Esc` closes** the drawer (matches the modal's `Esc`-to-close convention).
- **Focus ring:** every focusable control (`×`, the trigger, the focusable scroll
  region) shows the visible `--accent-line` `:focus-visible` ring — the single ring
  color used app-wide. Never remove the outline without this replacement.
- **Live region:** the event list container is an `aria-live="polite"` region so a
  newly-polled event is announced; `boot.error` rows may use `aria-live="assertive"`
  is **not** required (the drawer is opened deliberately, not a background alert) —
  `polite` is correct for the whole list.
- **Status is never color-only:** every row pairs its colored dot with the
  **text label** in the badge (e.g. `Boot error`, `Auto-stopped (idle)`) so the
  meaning survives color-blindness. The `boot.error` emphasis is a left bar **plus**
  the red label, not color alone.
- **Timestamps** are real text (mono), readable by a screen reader; if a relative
  hint is shown it supplements, never replaces, the absolute time.
- **Motion:** the slide-in and scrim fade honor the existing global
  `prefers-reduced-motion` block (duration → ~0); no JS animation bypasses it.

---

## Copywriting Contract

Sentence case, second-person, technical, unhedged. Middle-dot `·` separator.
Consistent with the 02-UI-SPEC copy voice.

| Element | Copy |
|---------|------|
| Drawer title | `{name} activity` (e.g. `auth-api activity`) — or the overline `ACTIVITY` when space is tight |
| Trigger affordance label (a11y) | `Activity log` |
| Close affordance label (a11y) | `Close activity log` |
| Empty-state heading | `No activity yet` |
| Empty-state body | `Events appear here as this workspace boots, connects, and stops.` |
| Poll-error strip | `Couldn't load the event log. Retrying…` |
| Event labels (badges) | `Created` · `Started` · `Stopped` · `Auto-stopped (idle)` · `Destroyed` · `Terminal connected` · `Terminal disconnected` · `Boot error` · `Boot config persisted` · `Reaper · {action}` · (unknown → raw `type` in mono) |
| `boot.error` data line | the server-redacted `data.reason` verbatim (already passed through `_safe()`); the UI adds no prefix and never un-redacts |

**Destructive actions this surface:** **none.** The activity drawer is **read-only**
— it polls and renders the event log; it triggers no mutations, has no CTA, no
destroy/stop/start. (Destructive lifecycle actions live in `TerminalPanel`'s
terminate flow, already specified in 02-UI-SPEC and out of scope here.) Therefore
this contract declares **no primary CTA and no destructive confirmation** for the
drawer.

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official | none | not applicable — no shadcn in this project (hand-built on Tailwind v4 `@theme` tokens) |
| third-party | none | not applicable |

No component registries are used. The drawer is hand-built on the existing tokens
and reuses the `TerminalPanel` icon-button + inline-SVG pattern and the
`WorkspaceList` shimmer/poll-error patterns. **No new runtime UI dependency is added
for UI-06** (no drawer/dialog library). No `shadcn view`/registry fetch occurs;
the registry vetting gate is therefore not triggered.

---

## Security / Posture Reconciliation (binding)

- **No external font or icon CDN** — inherits the shell's self-hosted-fonts /
  inline-SVG posture (PLAT-05). The two glyphs the drawer needs are inline SVG.
- The drawer's only network call is the **same-origin** poll of
  `GET /api/v1/workspaces/{id}/events`; no third-party request.
- The `data` shown is **already server-redacted** (`_safe()` strips git/CI tokens,
  URL userinfo, long opaque tokens before the event is written — verified in
  `workspaceService.py`). The UI renders it as-is and must **never** attempt to
  re-expand, re-fetch, or "unredact" any field. Topology (hostnames, VMIDs beyond
  what the redacted `data` already carries) is not added by the UI.

---

## Acceptance-Checkable Visual Criteria (gsd-ui-auditor grades against these)

1. **Tokens, not hex.** No hardcoded color in the drawer; every color resolves from
   a `--token`. All four `data-theme`s render the drawer with no orphaned hue.
2. **Newest-first.** The drawer reverses the oldest-first endpoint output — the most
   recent event is the top row.
3. **Badge map = real strings.** Badges key off the namespaced backend types
   (`workspace.created`, `terminal.connected`, `boot.error`, `reaper.*`, …); an
   unknown type renders its raw string in mono, not a crash or a blank.
4. **`boot.error` emphasis.** A `boot.error` row shows the 2px `--err` left bar + the
   `--err`-tinted background + the redacted reason in red mono; no other row type
   does.
5. **Poll only while open.** The TanStack Query `enabled` flag is `drawerOpen && id`;
   closing the drawer stops the poll.
6. **Four states.** Loading shows shimmer rows; empty shows `No activity yet`; error
   shows the inline `--err` strip over kept rows; populated shows the live list.
7. **No gold, no second action hue.** Zero `--gold` in the drawer; accent
   (`--accent-line`) appears only as the focus ring.
8. **Read-only.** The drawer has no CTA and no mutation; rows are non-interactive
   beyond hover.
9. **Scroll discipline.** Header fixed; only the body scrolls; data summaries wrap
   (no horizontal row scroll); top/status bars never move.
10. **Responsive width.** 360px desktop · `min(360px,80vw)` tablet · `100vw` phone,
    always right-anchored (full-width sheet on phone).
11. **A11y.** `role="dialog"` + label; focus trap; `Esc` closes; focus returns to the
    trigger; `--accent-line` focus ring on the `×`/trigger; status never color-only
    (dot + text label); list is `aria-live="polite"`; reduced-motion stills the
    slide.
12. **Redaction respected.** The drawer renders `data` verbatim and never re-fetches
    or un-redacts; only the same-origin events poll is made.

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS
- [ ] Dimension 4 Typography: PASS
- [ ] Dimension 5 Spacing: PASS
- [ ] Dimension 6 Registry Safety: PASS

**Approval:** pending
