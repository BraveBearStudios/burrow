<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
# Phase 5: Stop/Start Controls + Drawer Polish - Context

**Gathered:** 2026-06-14
**Status:** Ready for planning
**Mode:** Smart discuss (autonomous) — 12 decisions across 3 areas, all recommended answers accepted

<domain>
## Phase Boundary

Surface the backend-ready stop/start lifecycle (WS-06 stop, WS-07 start — endpoints
+ `useStopWorkspace`/`useStartWorkspace` hooks already ship from v1.0) as explicit,
state-machine-gated UI controls, and restore the three activity-drawer polish details
the v1.0 UI review flagged (04-UI-REVIEW 22/24): V2 phone full-width responsive sheet,
V3 `--accent-line` focus ring, V4 custom Burrow scrollbar.

Covers requirements **UI-07, UI-08, UI-09, UI-10, UI-11**. Pure frontend (`ui/`);
CI-provable over the FakeComputeProvider + stub ttyd (vitest + MSW + Playwright). No
backend change, no real-Proxmox path. Out of boundary: any new lifecycle endpoint,
sidebar-row stop/start affordance (deferred), and the v1.0 real-infra acceptance debt.
</domain>

<decisions>
## Implementation Decisions

### Area 1 — Stop/Start controls (placement & behavior)
- **Placement:** Stop/Start render as inline icon buttons in the `TerminalPanel` header, beside the existing Detach (plug) and Terminate (×) buttons — `status` already flows into `TerminalPanel`, and this reuses the established `iconButtonStyle` icon-button pattern (no icon font — Registry Safety).
- **Gating:** Show only the applicable control — Stop iff `status === "running"`, Start iff `status === "stopped"`; render neither while `creating`/`error`/`destroyed`. (Not "show both + disable".)
- **Confirm on Stop:** No confirmation modal. Stop is reversible (LXC stopped, disk state preserved); it fires immediately. The stopped panel state + the sidebar status overline make the result legible. (Contrast: Terminate keeps its destructive confirm overlay.)
- **In-flight feedback:** While the stop/start mutation is pending, disable the button and show an inline spinner (Start awaits ttyd health → seconds). The ~3s `useWorkspaces` poll drives the final state; status is never mirrored into Zustand (server is source of truth).

### Area 2 — Stopped-workspace panel state + glyphs
- **Panel body when `stopped`:** Render a dedicated "Workspace stopped" placeholder over the panel body with a Start CTA + short copy, instead of the connecting/reconnecting/error overlays. Stopping must not produce a scary reconnect-loop/error state.
- **Terminal hook when `stopped`:** Gate `useTerminal` so it does **not** attempt connect/reconnect while `status === "stopped"` (and tears the socket down on the running→stopped transition). It resumes connecting when Start flips the workspace back to `running`.
- **Glyphs:** Stop = outline square; Start = outline play-triangle — inline outline SVG matching the existing TerminalPanel icon set (Grip/Split/Plug/Close), `aria-label`ed.
- **Start when the workspace has no open panel:** Clicking the sidebar row opens its panel (existing `openPanel`+`setActive`) → Start from the panel placeholder. No separate sidebar-row Start affordance in v1.1 (deferred).

### Area 3 — Drawer polish V2/V3/V4 (CSS approach)
- **V2 responsive (UI-09):** Add a `--w-drawer` token = `min(360px, 100vw)` in the token sheet, overridden to `100vw` under `@media (max-width: 375px)`; `ActivityDrawer` reads `width: var(--w-drawer)` so the inline-style component stays inline-style but becomes responsive. Full-width sheet ≤375px, 360px panel above.
- **V3 focus ring (UI-10):** One global `:focus-visible { outline: 2px solid var(--accent-line); outline-offset: 2px }` rule in `index.css` — DRY, covers every interactive control across all four themes (`--accent-line` is defined per-theme). Replaces the missing focus affordance the inline icon buttons lack today.
- **V4 scrollbar (UI-11):** Global custom scrollbar in `index.css` — `::-webkit-scrollbar`/`-thumb`/`-track` (Chromium) + `scrollbar-width: thin` / `scrollbar-color` (Firefox), thumb = `--border-mid` on a transparent track, tokens only. Applies to the drawer list, terminal body, and sidebar list scroll surfaces.
- **Phone breakpoint:** 375px — matches the documented phone-375 UAT screenshot and the UI-09 ≤375px wording.

### Claude's Discretion
- Exact SVG path geometry for the Stop/Start glyphs, spinner sizing, and precise outline/offset px within the accepted approach.
- Whether the stopped placeholder reuses the existing `overlayBase` styling or a sibling style object.
- Test structure (which assertions live in vitest unit vs the Playwright journey), provided UI-07..11 each get a failing-first then passing test.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ui/src/hooks/useWorkspaces.ts` — `useStopWorkspace`, `useStartWorkspace`, `useDestroyWorkspace` (all POST `/workspaces/{id}/{action}` except destroy=DELETE), each `onSettled` invalidates `WORKSPACES_KEY`. Stop/Start need **no** new hook.
- `ui/src/components/TerminalPanel.tsx` — header icon-button row (Activity/Split/Detach/Terminate), `iconButtonStyle`, inline outline-SVG icon components, `status` prop, the confirm-overlay + `overlayBase`/`overlayButton` patterns, `useTerminal(id, status, …)`.
- `ui/src/components/WorkspaceLayout.tsx` — `LeafPanel` owns the per-workspace mutation wiring (already wires `useDestroyWorkspace` → `onTerminate`); the analogous place to wire `useStopWorkspace`/`useStartWorkspace` → new `onStop`/`onStart` props passed to `TerminalPanel`. Reconcile keeps `stopped` panels (only `gone/destroyed` leaves drop).
- `ui/src/hooks/useTerminal.ts` — the connect/reconnect state machine to gate on `stopped`.
- `ui/src/index.css` — 4-theme token sheet (`--accent-line`, `--border-mid`, `--bg-surf`, etc. all per-theme), `@theme` block, `.burrow-mosaic` chrome, `@keyframes pulse/spin/blink`, the `prefers-reduced-motion` block. **No** `:focus-visible`, `::-webkit-scrollbar`, or drawer media query exist yet — V2/V3/V4 are net-new CSS here.
- `ui/src/lib/status.ts` — `STATUS_COLOR` map + `isVisibleStatus`; `WorkspaceStatus` union is `creating|running|stopped|error|destroyed`.

### Established Patterns
- Inline `React.CSSProperties` style objects everywhere; tokens via `var(--…)`, never hex; gold reserved (never for status). Pseudo-class/media/scrollbar rules therefore **must** live in `index.css`, not inline.
- Server is source of truth — status never mirrored into Zustand; mutations invalidate the list and the ~3s poll reconciles. Zustand `layoutStore` owns only mosaic tree + `activeWorkspaceId`.
- Icons are inline outline SVG (stroke 1.5, round caps), no icon font/CDN.
- Tests: vitest + MSW `/api/v1` harness (unit/integration), Playwright over `BURROW_COMPUTE=fake` + a protocol-accurate stub ttyd (e2e). Every change lands failing-first then passing tests; SPDX header on every file.

### Integration Points
- `TerminalPanel` header — add Stop/Start buttons (gated by `status`).
- `TerminalPanel` body — add the `stopped` placeholder branch alongside the existing overlays.
- `useTerminal` — gate connect/reconnect on `status === "stopped"`.
- `WorkspaceLayout.LeafPanel` — wire `useStopWorkspace`/`useStartWorkspace` into new `onStop`/`onStart` props.
- `index.css` — `--w-drawer` token + `@media (max-width:375px)` override; global `:focus-visible`; global custom scrollbar.
- `ActivityDrawer` — swap `width: DRAWER_WIDTH` literal for `width: var(--w-drawer)`.
</code_context>

<specifics>
## Specific Ideas

- Honor the design handoff (`design/Burrow-handoff/`, `docs/design/`) and the binding 02-UI-SPEC / 04-UI-SPEC contracts — tokens only, four themes must all render the new controls + polish correctly.
- The stopped placeholder copy should match the existing Copywriting voice (cf. the terminate-confirm + empty-state copy).
- Stop is distinct from Detach: Detach = non-destructive socket close (session keeps running); Stop = WS-06 lifecycle stop (LXC down, disk kept, live session ends). Keep the three actions (Detach / Stop / Terminate) visually and semantically distinct.
</specifics>

<deferred>
## Deferred Ideas

- Sidebar-row stop/start (and other per-row quick actions) — deferred; v1.1 surfaces stop/start in the panel header only.
- v1.0 real-infra acceptance debt (homelab smoke / first CI run / GHCR release) — tracked in REQUIREMENTS.md Future Requirements (ACC-01/02/03), not this phase.
- Tablet (376–768px) drawer width tuning — only the ≤375px phone case is in scope for UI-09.
</deferred>
