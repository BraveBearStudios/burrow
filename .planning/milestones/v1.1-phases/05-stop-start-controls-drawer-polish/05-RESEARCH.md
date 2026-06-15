<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
# Phase 5: Stop/Start Controls + Drawer Polish - Research

**Researched:** 2026-06-14
**Domain:** Frontend (React 19 + TS, Tailwind v4 `@theme`, xterm.js) — lifecycle UI controls + global CSS polish; **test/validation strategy** for UI-07..UI-11
**Confidence:** HIGH (the code map is pre-enumerated in CONTEXT.md and every integration point was re-verified against source; the test seams already exist in the repo)

## Summary

This is a pure-frontend brownfield polish phase on a shipped v1.0 UI. The code map in `05-CONTEXT.md <code_context>` is authoritative and was re-verified file-by-file: the `useStopWorkspace`/`useStartWorkspace` hooks ship from v1.0 (`useWorkspaces.ts:67-68`), `useTerminal` **already** gates connect/reconnect on `status !== "running"` (`useTerminal.ts:178`) and tears down on a status change via its `[workspaceId, status]` effect dep (`useTerminal.ts:303`), and the four-theme token sheet, `iconButtonStyle`, `overlayBase`/`overlayButton`/`Spinner`, and the confirm-overlay pattern all exist in `TerminalPanel.tsx`. **Phase 5 surfaces and tests existing capability; it builds very little new machinery.** The research value is therefore the *test + validation strategy*, not a re-scout.

The single most important architectural fact for planning: **the jsdom/Playwright boundary is hard and well-precedented in this repo.** jsdom (the vitest environment, `vitest.config.ts:20`) does not evaluate `:focus-visible`, `::-webkit-scrollbar` pseudo-elements, `@media` width breakpoints, or computed layout (`offsetWidth` is 0 unless spied — see `useTerminal.test.tsx:128`). The repo already solved this once: `tests/tokens.test.ts` asserts CSS *as a source string* read off `src/index.css`, never via `getComputedStyle`. That is the locked precedent for V2/V3/V4's static half. The dynamic half (drawer width == viewport at 375px; the focus ring actually painting; the scrollbar actually rendering) belongs in Playwright, which runs real Chromium (`playwright.config.ts:84`).

**Primary recommendation:** Plan each requirement as a **two-tier test pair** — (1) a vitest unit/integration assertion on the observable React/DOM seam (button gating by status, `aria-busy`, no-socket-when-stopped via the `MockWebSocket` registry, placeholder render, and the CSS *source* presence of `--w-drawer`/`:focus-visible`/`::-webkit-scrollbar`), and (2) a Playwright leg over the Fake + stub ttyd for the things only a real browser proves (the stop→start round-trip, drawer width at a 375px viewport). Do **not** write acceptance criteria that ask jsdom to evaluate a pseudo-class, pseudo-element, or media query — those are untestable in vitest and must be CSS-source asserts or Playwright assertions.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Stop/Start button gating by `status` | Browser / Client (React render) | — | Pure conditional render off the `status` prop already flowing into `TerminalPanel`; no network on render |
| Stop/Start mutation dispatch | Browser / Client (TanStack mutation) → API | Frontend wires hook; API owns the WS-06/WS-07 transition | `LeafPanel` calls `useStopWorkspace`/`useStartWorkspace`; the backend state machine (`lib/statemachine.py` TRANSITIONS) is the authority |
| In-flight (pending) feedback | Browser / Client (`isPending` from mutation) | — | `mutation.isPending` drives `disabled` + `aria-busy` + spinner; no Zustand mirror |
| Final status reconcile | API (source of truth) → Client poll | — | `onSettled` invalidates `WORKSPACES_KEY`; the ~3s `useWorkspaces` poll re-lists; **no optimistic flip** |
| `useTerminal` gating on `stopped` | Browser / Client (effect early-return) | — | Already implemented (`useTerminal.ts:178`); Phase 5 confirms + tests, gates the *body branch* before `termStatus` overlays |
| `stopped` placeholder body | Browser / Client (React render) | — | Status-driven conditional render over the existing `position:relative` body wrapper |
| Responsive drawer width (V2) | CDN / Static (CSS token + media query) | Browser applies | A layout token in `@theme` + a `@media (max-width:375px)` override; the component stays inline-style reading `var(--w-drawer)` |
| Focus ring (V3) | CDN / Static (global CSS rule) | Browser paints on `:focus-visible` | One global rule; the browser's `:focus-visible` heuristic decides when it paints |
| Custom scrollbar (V4) | CDN / Static (global CSS rule) | Browser renders | `::-webkit-scrollbar` (Chromium) + `scrollbar-width`/`scrollbar-color` (Firefox); browser-only rendering |

## Standard Stack

No new runtime dependency is added (locked: `05-UI-SPEC` Registry Safety; `05-CONTEXT` Area 1-3). Everything below already ships in `ui/package.json` — the table documents the **versions the tests run against**, verified from the lockfile-pinned `package.json`.

### Core (already installed — no install step)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| react / react-dom | 19.2.7 | Component render + effects | Project stack (CLAUDE.md); StrictMode-safe teardown already proven |
| @tanstack/react-query | 5.101.0 | `useMutation` (`isPending`, `onSettled`) + `useQuery` poll | The stop/start hooks are already built on it (`useWorkspaces.ts`) |
| vitest | 4.1.8 | Tier-2 unit/integration runner (jsdom) | `vitest.config.ts`; `globals:true`, `environment:"jsdom"` |
| @testing-library/react | 16.3.2 | `render`, `screen`, `waitFor`, `act` | Established in every `*.test.tsx` |
| @testing-library/jest-dom | 6.9.1 | `toBeInTheDocument`, `toBeDisabled`, `toHaveAttribute` | Loaded in `tests/setup.ts:7` |
| msw | 2.14.6 | `/api/v1` mocking in the `{data,meta,error}` envelope | `tests/msw/handlers.ts`; `onUnhandledRequest:"error"` |
| @playwright/test | 1.60.0 | Tier-3 e2e over Fake + stub ttyd | `playwright.config.ts`; Chromium `Desktop Chrome` |
| @biomejs/biome | 2.4.16 | lint/format gate (`npm run lint` = `biome ci .`) | Project gate |
| typescript | 6.0.3 | `tsc --noEmit` typecheck gate | Project gate |

### Supporting (test seams — already in `ui/tests/helpers/`)
| Helper | Path | Purpose | When to Use |
|--------|------|---------|-------------|
| `MockWebSocket` | `tests/helpers/mockWebSocket.ts` | Records every constructed socket (`WS.instances`), `.url`, `.closed`, `emitOpen/emitClose/emitMessage/emitOutput` | The **load-bearing seam** for "no socket when stopped" and "socket tears down on running→stopped" |
| `mockXterm` | `tests/helpers/mockXterm.ts` | `lastTerminal()`, `liveTerminalCount()`, `resetXtermMocks()` | jsdom can't lay out a real xterm; mock it (see `vi.mock` at top of every terminal test) |
| `resizeObserver` | `tests/helpers/resizeObserver.ts` | `installMockResizeObserver`, `liveObserverCount` | Mount/teardown leak counting |
| `seedWorkspaces` | `tests/msw/handlers.ts:29` | Seed list already contains `ws-running`, `ws-stopped`, `ws-creating`, `ws-error` | Drive gating tests off real seed rows — **no new fixture needed for status coverage** |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Reading CSS source as a string for V2/V3/V4 unit half | `getComputedStyle` in jsdom | **Rejected** — jsdom does not resolve `:focus-visible`, `::-webkit-scrollbar`, or `@media` width queries; `getComputedStyle` returns empty/default. The source-string assert (`tokens.test.ts` precedent) is the only reliable unit-tier proof. |
| `fireEvent` / direct prop calls for interactions | `@testing-library/user-event` | `user-event` is **not installed**. Adding it is a new dev dep (CLAUDE.md: justify deps). The existing tests interact via `fireEvent.click`, direct handler calls, and mock emitters — stay consistent; do not add user-event for this phase. |
| Asserting the ring paints in unit tests | Playwright `toHaveCSS('outline-color', …)` after Tab | jsdom can't; this **must** be a Playwright assertion or a CSS-source assert. |

**Installation:** none. `npm ci` already resolves the full toolchain. No `npm install` task in any plan for UI-07..UI-11.

## Package Legitimacy Audit

> No external package is installed in this phase. The audit is therefore **not applicable** — every dependency is already present in the committed `ui/package.json` + lockfile and was vetted in prior phases (Plan 02-02). slopcheck was not run because no `npm install` occurs.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| (none — no install) | — | — | — | — | n/a | No package added this phase |

**Packages removed due to slopcheck [SLOP] verdict:** none (no install).
**Packages flagged as suspicious [SUS]:** none (no install).

## Architecture Patterns

### System Architecture Diagram

```
                         user clicks Stop (header) ──────┐
                                                          │
                         user clicks Start (header OR ────┤
                            placeholder CTA)              │
                                                          ▼
              ┌───────────────────────────────────────────────────────┐
              │  TerminalPanel (status prop drives render)             │
              │   header slot: status==="running" → Stop btn          │
              │                status==="stopped" → Start btn         │
              │                creating/error/destroyed → empty       │
              │   body branch:  status==="stopped" → placeholder       │
              │                 else → containerRef (xterm) + overlays │
              └───────────────┬───────────────────────────────────────┘
                              │ onStop(id) / onStart(id)
                              ▼
              ┌───────────────────────────────────────────────────────┐
              │  WorkspaceLayout.LeafPanel                             │
              │   useStopWorkspace().mutate(id, {onError: console})    │
              │   useStartWorkspace().mutate(id, {onError: console})   │
              │   (mirrors the existing useDestroyWorkspace wiring)    │
              └───────────────┬───────────────────────────────────────┘
                              │ POST /api/v1/workspaces/{id}/stop|start
                              ▼
              ┌───────────────────────────────────────────────────────┐
              │  Backend (WS-06/WS-07) — state machine is authority    │
              │   stop: LXC down, disk kept   start: awaits ttyd health│
              │   200 → mutation onSettled                             │
              └───────────────┬───────────────────────────────────────┘
                              │ onSettled → invalidate WORKSPACES_KEY
                              ▼
              ┌───────────────────────────────────────────────────────┐
              │  useWorkspaces ~3s poll re-lists  (SOURCE OF TRUTH)    │
              │   new status → re-render header (Stop↔Start swap)      │
              │   new status → re-render body (placeholder↔terminal)   │
              │   running→stopped: useTerminal effect re-runs,         │
              │      cleanup closes socket, new effect early-returns   │
              │   stopped→running: effect re-runs, reconnects          │
              └───────────────────────────────────────────────────────┘

   CSS (global, no JS path):
     --w-drawer token (@theme) ──@media(max-width:375px)──▶ 100vw
       ActivityDrawer reads width:var(--w-drawer)
     :focus-visible { outline: 2px solid var(--accent-line) }  (browser paints)
     ::-webkit-scrollbar + scrollbar-width/color (browser renders)
```

### Component Responsibilities

| File | Phase-5 change | Already exists? |
|------|----------------|-----------------|
| `ui/src/components/TerminalPanel.tsx` | Stop/Start glyphs + gated header buttons; `stopped` body branch (before `termStatus` overlays); accept `onStop`/`onStart` props | header cluster, `iconButtonStyle`, `overlayBase`/`overlayButton`/`Spinner`, body wrapper all present |
| `ui/src/components/WorkspaceLayout.tsx` (`LeafPanel`) | Wire `useStopWorkspace`/`useStartWorkspace` → `onStop`/`onStart` | `useDestroyWorkspace`→`onTerminate` is the exact template (`WorkspaceLayout.tsx:69-76,96-103`) |
| `ui/src/hooks/useTerminal.ts` | **Confirm + test** the `status==="stopped"` gate; no code change expected | gate at line 178; teardown at 288-302; effect dep `[workspaceId,status]` at 303 |
| `ui/src/components/ActivityDrawer.tsx` | Swap `width: DRAWER_WIDTH` literal → `width: "var(--w-drawer)"`; remove/scope `outline:"none"` so V3 ring shows | `DRAWER_WIDTH` at line 40; `drawerStyle.width` at 83; `outline:"none"` at 92 |
| `ui/src/index.css` | Add `--w-drawer` to `@theme`; `@media (max-width:375px)` override; global `:focus-visible`; global scrollbar | `@theme` block at line 32 (has `--w-sidebar`/`--w-modal`); `--radius-full` (63), `--ease-ui` (66) present; **no** focus/scrollbar/drawer-media exist |
| `ui/src/hooks/useWorkspaces.ts` | **none** — `useStopWorkspace`/`useStartWorkspace` already exported (lines 67-68) | yes |

### Pattern 1: Status-gated header slot (show-only-applicable)
**What:** Render exactly one of Stop/Start, or neither, off the `status` prop.
**When to use:** UI-07/UI-08 header buttons.
**Example:**
```tsx
// Source: derived from TerminalPanel.tsx header cluster (existing iconButtonStyle pattern)
{status === "running" ? (
  <button type="button" aria-label="Stop workspace" aria-busy={stop.isPending}
          disabled={stop.isPending} style={iconButtonStyle}
          onClick={() => onStop?.(id)}>
    {stop.isPending ? <InlineSpinner /> : <StopIcon />}
  </button>
) : status === "stopped" ? (
  <button type="button" aria-label="Start workspace" aria-busy={start.isPending}
          disabled={start.isPending} style={iconButtonStyle}
          onClick={() => onStart?.(id)}>
    {start.isPending ? <InlineSpinner /> : <StartIcon />}
  </button>
) : null}
```
**Note on `isPending` ownership:** the mutation lives in `LeafPanel` (per the existing destroy wiring), so `isPending`/`onStop` must be **passed into `TerminalPanel`** (a `stopPending`/`startPending` prop or the whole mutation result), OR the panel owns the mutations. Either is valid; the planner picks one. The cleaner seam that matches the `onTerminate` precedent is: `LeafPanel` owns the mutations and passes `onStop`, `onStart`, plus pending booleans, into `TerminalPanel`. **This is a real decision the planner must lock** — flagged in Open Questions.

### Pattern 2: Body branch ordered BEFORE the termStatus overlays
**What:** Branch the panel body on `status === "stopped"` *before* the `termStatus`-driven connecting/reconnecting/error overlays, so a transient `termStatus` can't flash an error scrim during a stop.
**When to use:** UI-07 placeholder body (`05-UI-SPEC §2`, criterion 6).
**Example:**
```tsx
// Body region (existing position:relative wrapper at TerminalPanel.tsx:311)
{status === "stopped" ? (
  <StoppedPlaceholder onStart={() => onStart?.(id)} pending={start.isPending} />
) : (
  <>
    <div ref={containerRef} className="term" data-testid={`term-${id}`} … />
    {termStatus === "connecting" ? <ConnectingOverlay/> : null}
    {termStatus === "reconnecting" ? <ReconnectingOverlay/> : null}
    {termStatus === "error" ? <ErrorOverlay/> : null}
  </>
)}
```

### Pattern 3: CSS-source assertion for un-jsdom-able rules (the V2/V3/V4 unit tier)
**What:** Read `src/index.css` as a string and assert the rule's *presence and shape*, exactly as `tokens.test.ts` does.
**When to use:** the unit half of UI-09/UI-10/UI-11 (jsdom cannot evaluate the live rule).
**Example:**
```ts
// Source: tests/tokens.test.ts pattern (readFileSync + substring assertions)
const css = readFileSync(resolve(process.cwd(), "src/index.css"), "utf8");
expect(css).toMatch(/--w-drawer:\s*min\(360px,\s*100vw\)/);
expect(css).toMatch(/@media\s*\(max-width:\s*375px\)/);
expect(css).toMatch(/:focus-visible\s*\{[^}]*outline:\s*2px solid var\(--accent-line\)/);
expect(css).toMatch(/::-webkit-scrollbar-thumb\s*\{[^}]*var\(--border-mid\)/);
expect(css).toMatch(/scrollbar-color:\s*var\(--border-mid\)/);
```
This proves the contract *shipped in the source* without asking jsdom to render it. It is a real regression guard (it goes RED if someone deletes the rule) and it is fast.

### Anti-Patterns to Avoid
- **Mirroring status into Zustand for an optimistic flip.** Locked against (`05-CONTEXT` Area 1; criterion 4). The server is the source of truth; the ~3s poll drives the swap. A test that asserts the header swaps Stop→Start *immediately on click* would encode the wrong behavior — assert instead that the mutation fired and that the swap follows a re-list.
- **Asserting `:focus-visible`/scrollbar via `getComputedStyle` in jsdom.** Returns empty; the test would be tautological or falsely green. Use CSS-source asserts (unit) + Playwright (render).
- **A `disabled` button with an `onClick` that can still double-fire.** The `disabled` attribute is the double-fire guard (`05-UI-SPEC §1`); test that a second click while pending does not fire a second mutation.
- **Leaving a timer/socket alive across running→stopped.** The effect dep `[workspaceId, status]` already forces cleanup; a test must prove `WS.instances` gets no *new* open socket and the prior one is `.closed` after the transition.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Pending/in-flight tracking | A `useState(isLoading)` around the fetch | `mutation.isPending` from `useStopWorkspace`/`useStartWorkspace` | TanStack already tracks it; hand-rolled state desyncs with `onSettled` |
| Final-status reconcile after stop/start | Manual `setStatus` / Zustand write | `onSettled` → `invalidateQueries(WORKSPACES_KEY)` (already in the hooks) + the ~3s poll | Server is source of truth; the hooks already invalidate |
| Terminal teardown on stop | A manual `socket.close()` on the Stop click | The existing `useTerminal` `[workspaceId,status]` effect cleanup | The gate + teardown already exist (line 178/288-302); re-implementing risks a double-close/leak |
| Responsive width logic | A `matchMedia` + `useState` width hook | A CSS token `--w-drawer` overridden in `@media` | Locked decision (V2); keeps the component inline-style, no JS, no jsdom-matchMedia fragility |
| Focus ring per-component | Per-button `:focus` inline outline | One global `:focus-visible` rule | DRY (V3); one rule covers every control across four themes |
| Spinner | A new spinner component | Reuse `@keyframes spin` + the `Spinner` shape (`TerminalPanel.tsx:172`); add a 14px variant for the header button | Motion already honors `prefers-reduced-motion`; new keyframes would bypass it |

**Key insight:** Nearly every "new" behavior in this phase is a *render-time consequence* of state the system already owns (mutation `isPending`, polled `status`, the `useTerminal` gate). The phase is wiring + CSS, not new state machinery. Tests should assert the *seams* (button gating, `aria-busy`, socket registry, CSS source), not re-prove the underlying hooks.

## Runtime State Inventory

> Phase 5 is a greenfield-on-the-UI render/CSS change. No rename/refactor/migration. This section is included for completeness because the phase touches a global CSS file and a shared hook, but there is **no stored runtime state** to migrate.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — no DB, no datastore touched. The frontend persists only `layoutStore` (mosaic tree + activeWorkspaceId, `tests/integration/restore.test.tsx:179`); status is never persisted. | none |
| Live service config | None — no external service config. Stop/Start hit same-origin `/api/v1/.../stop|start` only. | none |
| OS-registered state | None — no OS registration. | none |
| Secrets/env vars | None new. Playwright e2e env (`BURROW_COMPUTE=fake`, `BURROW_E2E_TTYD_HOST`) is unchanged and already in `playwright.config.ts`. | none |
| Build artifacts | The Playwright `webServer` requires `ui/dist` from `npm run build` (`playwright.config.ts:62`); the e2e leg must rebuild after the UI change. The `vite preview` step serves the *built* SPA, not live source. | rebuild `ui/dist` before the e2e run (already part of the e2e gate) |

**Nothing found in the first four categories — verified by reading the persisted-state partialize (`restore.test.tsx`) and the network surface (`useWorkspaces.ts`, same-origin only).**

## Common Pitfalls

### Pitfall 1: Asserting an immediate status swap on click (optimistic-flip trap)
**What goes wrong:** A test clicks Stop and asserts the header now shows Start. It fails (or, worse, passes only because the test mutates state directly), encoding a behavior the spec forbids.
**Why it happens:** Intuition says "click → state changes." But status is server-owned; the swap follows the next poll re-list after `onSettled` invalidation.
**How to avoid:** Unit-tier — assert (a) the mutation `mutationFn` fired with the workspace id (spy or MSW request capture) and (b) the button is `disabled`+`aria-busy` while pending. Drive the swap by changing the MSW seed/`useWorkspaces` return and re-rendering, or assert the swap in Playwright where the real poll runs. Do **not** assert "swaps on click."
**Warning signs:** A test that calls `setStatus` or writes Zustand to make the assertion pass.

### Pitfall 2: jsdom can't prove `:focus-visible`, `::-webkit-scrollbar`, or a width `@media`
**What goes wrong:** A unit test does `getComputedStyle(button).outlineColor` after focusing and asserts the accent color — it's empty in jsdom, so the test is false-green or impossible.
**Why it happens:** jsdom implements the DOM, not a full rendering/styling engine. It does not resolve pseudo-classes driven by UA heuristics (`:focus-visible`), pseudo-elements (`::-webkit-scrollbar`), or viewport media queries for width.
**How to avoid:** Split the criterion. **Unit (vitest):** CSS-source assert the rule exists and has the right tokens (Pattern 3). **Render (Playwright):** assert the painted effect — `toHaveCSS`, a screenshot, or a width measurement. Never ask jsdom to evaluate the live rule.
**Warning signs:** Any unit test calling `getComputedStyle` on a `:focus-visible`/scrollbar/media-driven property.

### Pitfall 3: `matchMedia` is not implemented in jsdom (so don't gate on it, and don't test it there)
**What goes wrong:** If the responsive width were implemented as a JS `matchMedia` hook, the unit tests would need a `matchMedia` polyfill (it's `undefined` in jsdom — not stubbed in `tests/setup.ts`), and the test would assert a mock, not real behavior.
**Why it happens:** jsdom does not ship `window.matchMedia`.
**How to avoid:** The locked V2 approach is **CSS-only** (a token + a media override) — there is *no* `matchMedia` in the implementation, so there is nothing to polyfill. Keep it CSS-only. Assert the media rule via CSS-source (unit) and the actual width at a 375px viewport via Playwright (`test.use({ viewport: { width: 375, height: 800 } })`, then `boundingBox().width === 375`).
**Warning signs:** A plan task that adds `window.matchMedia` to `tests/setup.ts` — that signals the implementation drifted to JS and away from the locked CSS approach.

### Pitfall 4: A leaked socket or timer across the running→stopped transition
**What goes wrong:** On stop, the terminal's WebSocket or backoff timer survives, producing a phantom reconnect loop or an error scrim under the placeholder.
**Why it happens:** If the body branch renders the placeholder but the `useTerminal` effect isn't allowed to tear down (e.g. the panel stops mounting the hook, or the status prop doesn't reach the hook), the prior socket lingers.
**How to avoid:** Keep `useTerminal(id, status, …)` mounted with the live `status` (it already is — `TerminalPanel.tsx:205`). The `[workspaceId,status]` dep change runs the cleanup (closes the socket, clears the timer — lines 288-302), then the re-run early-returns at line 178. **Test it:** render at `status="running"`, drive a socket open, re-render at `status="stopped"`, assert (a) the prior socket is `.closed`, (b) `WS.instances` gains no new *open* socket, (c) `liveTerminalCount()`/timers settle. This is the `restore.test.tsx` socket-registry pattern applied to a status flip.
**Warning signs:** `WS.instances` growing after the flip; a fake-timer test showing a pending reconnect timer post-stop.

### Pitfall 5: `:focus-visible` removal on the drawer `<aside>` clobbers control rings
**What goes wrong:** The drawer `<aside>` sets `outline:"none"` (`ActivityDrawer.tsx:92`). A blanket global `:focus-visible` rule still works on controls, but if a future edit broadens the `outline:none` (e.g. to `* { outline: none }`) it would suppress the contracted ring.
**Why it happens:** Inline `outline:"none"` on the container is fine (the container is `tabIndex=-1` programmatic focus, not `:focus-visible`), but the relationship is subtle.
**How to avoid:** Keep the global `:focus-visible` rule un-scoped (applies to all controls); leave the `<aside>`'s `outline:"none"` only on the bare container or remove it. The unit test asserts the global rule's presence in source; a Playwright test Tabs to a control inside the drawer and asserts the ring paints (`toHaveCSS('outline-style','solid')`).
**Warning signs:** A `* { outline: none }` anywhere; the global `:focus-visible` rule scoped to a selector narrower than "every control."

### Pitfall 6: Tailwind v4 `@theme` token override under a media query
**What goes wrong:** `--w-drawer` is declared in the `@theme` block. A naive `@media { @theme { --w-drawer: 100vw } }` is invalid — `@theme` is a Tailwind at-rule, not nestable under `@media`.
**Why it happens:** Tailwind v4's `@theme` registers design tokens; the media override is plain CSS custom-property re-declaration, which belongs on `:root` (or the same scope the token effectively resolves on), not inside another `@theme`.
**How to avoid:** Declare the default in `@theme` (it resolves to `:root`), then override in plain CSS: `@media (max-width: 375px) { :root { --w-drawer: 100vw } }`. This matches `05-UI-SPEC §4` ("apply to the same scope the token is declared on"). The CSS-source test asserts both the `@theme` default and the `:root` media override exist.
**Warning signs:** `@theme` nested inside `@media`; the override on a selector that doesn't actually cascade to the `ActivityDrawer` `<aside>`.

### Pitfall 7: The placeholder Start CTA and the header Start button double-firing
**What goes wrong:** When `stopped`, both the header Start button and the placeholder Start CTA are visible and both can fire `useStartWorkspace`. Clicking both (or one twice before settle) issues duplicate POSTs.
**Why it happens:** Two affordances for one action sharing one pending state.
**How to avoid:** Both reflect the same `isPending` and both carry `disabled` while pending (`05-UI-SPEC §2`). Test: with one mutation pending, assert *both* controls are `disabled`. The backend state machine also rejects an illegal double-start (envelope error, self-corrects on poll) — but the UI should not rely on that.
**Warning signs:** Only one of the two Start affordances disables while pending.

## Code Examples

### No-socket-when-stopped + teardown-on-flip (the UI-07/UI-08 hook gate test)
```tsx
// Source: pattern from useTerminal.test.tsx + restore.test.tsx (MockWebSocket registry)
import { installMockWebSocket, type MockWebSocket } from "../../tests/helpers/mockWebSocket";

it("opens NO socket while status is stopped", () => {
  const WS = installMockWebSocket();
  function H() { const t = useTerminal("w1", "stopped"); return <div ref={t.containerRef} />; }
  render(<H />);
  expect(WS.instances).toHaveLength(0);   // gate at useTerminal.ts:178 holds
});

it("tears the socket down on running→stopped and opens none after", () => {
  const WS = installMockWebSocket();
  function H({ status }: { status: WorkspaceStatus }) {
    const t = useTerminal("w1", status); return <div ref={t.containerRef} />;
  }
  const { rerender } = render(<H status="running" />);
  act(() => WS.instances.at(-1)!.emitOpen());
  const before = WS.instances.length;
  rerender(<H status="stopped" />);          // [workspaceId,status] dep change → cleanup
  expect(WS.instances.at(before - 1)!.closed).toBe(true);
  expect(WS.instances.filter(s => !s.closed)).toHaveLength(0);
});
```

### Gating + pending feedback (UI-07/UI-08 header)
```tsx
// Source: TerminalPanel render contract + jest-dom matchers
it("shows Stop only when running, Start only when stopped, neither otherwise", () => {
  const { rerender } = renderPanel({ status: "running" });
  expect(screen.getByLabelText("Stop workspace")).toBeInTheDocument();
  expect(screen.queryByLabelText("Start workspace")).toBeNull();

  rerender(panel({ status: "stopped" }));
  expect(screen.getByLabelText("Start workspace")).toBeInTheDocument();
  expect(screen.queryByLabelText("Stop workspace")).toBeNull();

  for (const s of ["creating", "error", "destroyed"] as const) {
    rerender(panel({ status: s }));
    expect(screen.queryByLabelText("Stop workspace")).toBeNull();
    expect(screen.queryByLabelText("Start workspace")).toBeNull();
  }
});

it("disables + aria-busy while the stop mutation is pending and does not double-fire", async () => {
  const stopSpy = vi.fn();                 // or capture the MSW request
  renderPanel({ status: "running", onStop: stopSpy /* pending toggled by harness */ });
  const btn = screen.getByLabelText("Stop workspace");
  fireEvent.click(btn);
  // once pending propagates: disabled + aria-busy
  await waitFor(() => expect(btn).toBeDisabled());
  expect(btn).toHaveAttribute("aria-busy", "true");
  fireEvent.click(btn);                     // second click while disabled
  expect(stopSpy).toHaveBeenCalledTimes(1); // no double-fire
});
```

### Stop/Start MSW handlers (Wave 0 — these DO NOT exist yet)
```ts
// Source: tests/msw/handlers.ts envelope() helper; add to the handlers array
http.post("/api/v1/workspaces/:id/stop", ({ params }) => {
  const w = seedWorkspaces.find(x => x.id === params.id);
  if (!w) return notFound();               // reuse the 404 shape already in the file
  return HttpResponse.json(envelope({ ...w, status: "stopped",
    stoppedAt: "2026-06-10T04:00:00Z" }));
}),
http.post("/api/v1/workspaces/:id/start", ({ params }) => {
  const w = seedWorkspaces.find(x => x.id === params.id);
  if (!w) return notFound();
  return HttpResponse.json(envelope({ ...w, status: "running", stoppedAt: null }));
}),
```

### CSS-source asserts for V2/V3/V4 (Pattern 3, extends tokens.test.ts)
```ts
// Source: tests/tokens.test.ts (readFileSync of src/index.css)
const css = readFileSync(resolve(process.cwd(), "src/index.css"), "utf8");
// V2
expect(css).toMatch(/--w-drawer:\s*min\(\s*360px\s*,\s*100vw\s*\)/);
expect(css).toMatch(/@media\s*\(\s*max-width:\s*375px\s*\)\s*\{[^}]*--w-drawer:\s*100vw/s);
// V3
expect(css).toMatch(/:focus-visible\s*\{[^}]*outline:\s*2px\s+solid\s+var\(--accent-line\)[^}]*outline-offset:\s*2px/s);
// V4
expect(css).toMatch(/::-webkit-scrollbar-thumb\s*\{[^}]*background:\s*var\(--border-mid\)/s);
expect(css).toMatch(/scrollbar-color:\s*var\(--border-mid\)\s+transparent/);
```
Also assert `ActivityDrawer.tsx` reads the token (source or render): the `drawerStyle.width` is `"var(--w-drawer)"` (a unit render assert: `getByRole("dialog")` then `.style.width === "var(--w-drawer)"` — inline style *is* readable in jsdom even though the *computed* width is not).

### Playwright: drawer full-width at 375px (UI-09 render half)
```ts
// Source: terminal.spec.ts journey shape + Playwright viewport override
test.describe("drawer responsive (UI-09)", () => {
  test.use({ viewport: { width: 375, height: 800 } });
  test("fills the viewport width on a 375px phone", async ({ page }) => {
    await page.goto("/");
    // open a workspace + its Activity drawer (Activity log button)
    await page.getByRole("button", { name: "Activity log" }).first().click();
    const drawer = page.getByRole("dialog");
    await expect(drawer).toBeVisible();
    const box = await drawer.boundingBox();
    expect(box?.width).toBe(375);          // full-width sheet, not 360px
  });
});
```

### Playwright: stop→start round-trip (extends the existing journey)
```ts
// Source: terminal.spec.ts waitForResponse pattern (proves the real POST fires)
await page.getByRole("button", { name: "Stop workspace" }).first().click();
const [stopRes] = await Promise.all([
  page.waitForResponse(r =>
    /\/api\/v1\/workspaces\/[^/]+\/stop$/.test(new URL(r.url()).pathname) &&
    r.request().method() === "POST", { timeout: 15_000 }),
  Promise.resolve(),
]);
expect(stopRes.ok()).toBe(true);
// after the ~3s poll the placeholder shows and the terminal body is gone
await expect(page.getByText("Workspace stopped")).toBeVisible({ timeout: 15_000 });
// Start from the placeholder CTA → POST /start → terminal remounts
await page.getByRole("button", { name: "Start workspace" }).first().click();
await expect(page.getByText("Workspace stopped")).toBeHidden({ timeout: 30_000 });
await expect(page.locator('[data-testid^="term-"]').first()).toBeVisible();
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `:focus` outline (paints on mouse click too) | `:focus-visible` (UA heuristic; keyboard/programmatic only) | Baseline-available across modern browsers for years | V3 must use `:focus-visible` (locked) — a mouse click must NOT paint the ring |
| JS `matchMedia` width hooks | CSS custom-property token overridden in `@media` | — | V2 stays CSS-only; no jsdom matchMedia fragility |
| Per-component spinner state | TanStack `mutation.isPending` | TanStack Query v5 | `isPending` (v5 name; was `isLoading` in v4) drives pending UI |
| Tailwind config file tokens | Tailwind v4 CSS-first `@theme` (no `tailwind.config.ts`) | Tailwind v4 / ADR-0008 | `--w-drawer` goes in the `@theme` block, not a config file |

**Deprecated/outdated:**
- TanStack v4 `isLoading` on mutations → in v5 (`5.101.0`) the mutation pending flag is **`isPending`**. Use `isPending`.
- `tailwind.config.ts` was removed in Plan 02-02 / ADR-0008 — do not reintroduce a config file for the `--w-drawer` token; it belongs in `index.css` `@theme`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `useTerminal` requires **no code change** — the existing `status !== "running"` gate (line 178) + `[workspaceId,status]` teardown already satisfy UI-07/UI-08's hook behavior; Phase 5 only *confirms + tests* it. | Component Responsibilities, Pitfall 4 | LOW — verified in source; but if the planner finds the body must branch *before* the hook (e.g. to suppress a transient `termStatus`), a tiny render-order change in `TerminalPanel` (not the hook) is needed. Re-confirmed against `05-UI-SPEC §2` ("branch the body on `status==="stopped"` **before** the termStatus overlays") — this is a `TerminalPanel` render-order requirement, not a hook change. |
| A2 | The mutations are owned by `LeafPanel` and passed into `TerminalPanel` as `onStop`/`onStart` (+ pending), mirroring the `onTerminate` precedent. | Pattern 1, Open Questions | MEDIUM — alternative is the panel owning the mutations directly. Both work; the planner must lock one. Flagged as an open question. |
| A3 | The Playwright `Activity log` button + drawer `role="dialog"` are the e2e handles for the UI-09 viewport test. | Code Examples (Playwright UI-09) | LOW — verified in `ActivityDrawer.tsx` (role=dialog) and `TerminalPanel.tsx:274` (aria-label "Activity log"). |
| A4 | A 14px inline spinner can sit inside the 24px `iconButtonStyle` button without reflow. | Standard Stack / Don't Hand-Roll | LOW — `05-UI-SPEC` Spacing locks this dimension; visual-only, Playwright/visual confirms. |

**These are the only assumptions; everything else is VERIFIED against repo source or CITED from the binding `05-UI-SPEC`/`05-CONTEXT`.**

## Open Questions

1. **Where do the Stop/Start mutations live — `LeafPanel` or `TerminalPanel`?**
   - What we know: `useDestroyWorkspace`→`onTerminate` is wired in `LeafPanel` (`WorkspaceLayout.tsx:69-76`), and `TerminalPanel` takes callback props. The pending state (`isPending`) must reach the button to drive `disabled`/`aria-busy`/spinner.
   - What's unclear: if `LeafPanel` owns the mutations, it must pass `isPending` down (extra props); if `TerminalPanel` owns them, the wiring diverges from the `onTerminate` precedent.
   - Recommendation: **`LeafPanel` owns both mutations (consistency with `onTerminate`) and passes `onStop`, `onStart`, `stopPending`, `startPending` into `TerminalPanel`.** The placeholder Start CTA and the header Start button then share `startPending`. Lock this in the plan; it determines the test harness shape (props vs. internal hook).

2. **Does the `stopped` placeholder reuse `overlayBase` or a sibling style object?**
   - What we know: `05-CONTEXT` Area 2 + `05-UI-SPEC §2` mark this Claude's discretion, recommending a calm `--bg-surf` wash (not the dim error scrim).
   - What's unclear: nothing blocking — discretion is granted.
   - Recommendation: a sibling style object over `--bg-surf` (opaque, calm). No test impact beyond asserting the heading/copy/CTA render; the wash color is a visual/Playwright check.

3. **Does the e2e stop→start leg extend the existing `terminal.spec.ts` journey or get its own spec?**
   - What we know: the existing journey is `mode:"serial"` and already creates/terminates workspaces; the Fake supports stop/start (it's lifecycle-accurate per Plan 00-02).
   - What's unclear: whether to bolt a stop→start leg into the one journey (faster, fewer server spin-ups) or a new `stop-start.spec.ts`.
   - Recommendation: a **new `tests/e2e/stop-start.spec.ts`** (own create→stop→start→assert) so the long terminate-journey stays focused and a stop/start failure is independently legible. Reuse the `createWorkspace` helper shape and the `waitForResponse` POST-assertion pattern.

## Environment Availability

> The phase has external test-tooling dependencies (the toolchain is installed; the e2e leg needs Python for the stub ttyd). Probed against the committed config.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node + npm (`npm ci`) | vitest/biome/tsc/build | ✓ (project baseline) | per `package.json` engines | — |
| vitest + jsdom | Tier-2 unit/integration | ✓ | 4.1.8 / jsdom 29.1.1 | — |
| Playwright Chromium | Tier-3 e2e | ✓ (CI installs via `npx playwright install chromium`) | @playwright/test 1.60.0 | — |
| Python 3.12 + uv (stub ttyd + uvicorn) | e2e `webServer` (`playwright.config.ts:35,47`) | ✓ (api/ toolchain) | per api/ | compose lane (`BURROW_E2E_USE_COMPOSE=1`) |
| `ui/dist` (built SPA) | e2e `vite preview` | built on demand | — | `npm run build` before `npm run e2e` |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** the e2e leg can run either via the local `webServer` (3 processes) or the compose stack — both already wired in `playwright.config.ts`. On a host without Docker, the local lane is the path (Plan 02-06 ran it green locally in 21.7s).

## Validation Architecture

> nyquist_validation is enabled (no `workflow.nyquist_validation:false` in config). This section maps the observable signals + test seams that prove UI-07..UI-11, and the minimal unit-vs-e2e test set per requirement.

### Test Framework
| Property | Value |
|----------|-------|
| Framework (Tier-2) | vitest 4.1.8 + @testing-library/react 16.3.2 + jest-dom 6.9.1 + MSW 2.14.6, jsdom env |
| Framework (Tier-3) | @playwright/test 1.60.0 (Chromium) over FakeComputeProvider + stub ttyd |
| Config file | `ui/vitest.config.ts`, `ui/playwright.config.ts` |
| Quick run command | `cd ui && npm test` (vitest run) — also `npm run lint`, `npm run typecheck` |
| Full suite command | `cd ui && npm test && npm run lint && npm run typecheck && npm run build && npm run e2e` |

### Observable Signals / Test Seams (what makes each criterion provable)

| Signal | Where | Tier that reads it |
|--------|-------|--------------------|
| `aria-label="Stop workspace"` / `"Start workspace"` present/absent by status | `TerminalPanel` header render | unit (`getByLabelText`/`queryByLabelText`), e2e (`getByRole button name`) |
| `disabled` + `aria-busy="true"` while pending | the gated button | unit (`toBeDisabled`, `toHaveAttribute`) |
| `MockWebSocket` registry: `WS.instances` count + `.closed` | `useTerminal` over the mock socket | unit (no-socket-when-stopped, teardown-on-flip) |
| `getByText("Workspace stopped")` + placeholder copy + `role="status"` | `stopped` body branch | unit (render), e2e (after poll) |
| `POST /workspaces/:id/stop` / `/start` fired | network | unit (MSW request capture / mutation spy), e2e (`waitForResponse`) |
| `--w-drawer` token + `@media (max-width:375px)` override in `index.css` source | CSS file | unit (CSS-source assert) |
| Drawer `boundingBox().width === 375` at a 375px viewport | rendered drawer | e2e (Playwright viewport) |
| `:focus-visible { outline … var(--accent-line) }` in `index.css` source | CSS file | unit (CSS-source assert) |
| Ring paints on Tab-focus (`toHaveCSS('outline-style','solid')`) | rendered control | e2e (Playwright) |
| `::-webkit-scrollbar*` + `scrollbar-width/color` in `index.css` source | CSS file | unit (CSS-source assert) |
| Inline `drawerStyle.width === "var(--w-drawer)"` | `ActivityDrawer` element | unit (read `.style.width` — inline style is readable in jsdom) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | jsdom-able? |
|--------|----------|-----------|-------------------|-------------|
| UI-07 | Stop shown iff `running`; neither for creating/error/destroyed | unit | `cd ui && npm test -- TerminalPanel` | ✅ yes |
| UI-07 | Stop fires `POST /stop`; disabled+aria-busy while pending; no double-fire | unit | `npm test -- TerminalPanel` | ✅ yes (MSW/spy) |
| UI-07 | `stopped` placeholder renders (heading+copy+CTA, `role=status`) instead of overlays | unit | `npm test -- TerminalPanel` | ✅ yes |
| UI-07 | `useTerminal` opens NO socket while stopped; socket tears down on running→stopped | unit | `npm test -- useTerminal` | ✅ yes (`MockWebSocket`) |
| UI-07 | full stop leg: click Stop → POST → placeholder appears after poll | e2e | `cd ui && npm run e2e` | ❌ Playwright |
| UI-08 | Start shown iff `stopped`; fires `POST /start`; pending feedback; both Start affordances disable | unit | `npm test -- TerminalPanel` | ✅ yes |
| UI-08 | `useTerminal` reconnects on stopped→running | unit | `npm test -- useTerminal` | ✅ yes (`MockWebSocket`) |
| UI-08 | full start leg: Start from placeholder → POST → terminal remounts | e2e | `npm run e2e` | ❌ Playwright |
| UI-09 | `--w-drawer` token + `@media (max-width:375px)` 100vw override present in source | unit | `npm test -- tokens` (or a new css-source test) | ❌ source-assert (not live jsdom) |
| UI-09 | `ActivityDrawer` reads `width:var(--w-drawer)` | unit | `npm test -- ActivityDrawer` | ✅ yes (inline `.style.width`) |
| UI-09 | drawer == viewport width (375px) on a phone viewport; 360px above | e2e | `npm run e2e` | ❌ Playwright viewport |
| UI-10 | global `:focus-visible { outline 2px solid var(--accent-line); offset 2px }` in source | unit | `npm test -- (css-source)` | ❌ source-assert |
| UI-10 | ring paints on keyboard focus of a control across themes | e2e | `npm run e2e` | ❌ Playwright (`:focus-visible` is UA-heuristic) |
| UI-11 | `::-webkit-scrollbar*` (thumb `--border-mid`) + Firefox `scrollbar-width/color` in source | unit | `npm test -- (css-source)` | ❌ source-assert |
| UI-11 | styled scrollbar renders on a scroll surface | e2e / visual | `npm run e2e` (screenshot) | ❌ Playwright (pseudo-element) |

### Sampling Rate
- **Per task commit:** `cd ui && npm test -- <changed-area>` + `npm run lint` + `npm run typecheck` (the failing-first regression test for that task goes green).
- **Per wave merge:** `cd ui && npm test` (full vitest) + `npm run lint` + `npm run typecheck` + `npm run build`.
- **Phase gate:** full suite green incl. `npm run e2e` (build `ui/dist` first) before `/gsd:verify-work`.

### Wave 0 Gaps
- [ ] `tests/msw/handlers.ts` — add `POST /api/v1/workspaces/:id/stop` and `/start` handlers (reuse `envelope()` + the 404 shape). **Required** — every gating/pending/round-trip unit test depends on them; `onUnhandledRequest:"error"` will otherwise fail the test on a missing handler.
- [ ] `src/components/TerminalPanel.test.tsx` — **does not exist** (no `TerminalPanel.test.tsx` in the repo; the panel is covered only indirectly via `restore.test.tsx`). Create it: covers UI-07/UI-08 gating, pending, placeholder, double-fire. Will need `QueryClientProvider` (the panel mounts the closed `ActivityDrawer` whose `useWorkspaceEvents` needs context — same deviation Plan 04-03 hit).
- [ ] `src/hooks/useTerminal.test.tsx` — add a `status="stopped"` describe block (no socket; teardown on flip; reconnect on stopped→running). The file exists but has **no stopped-status coverage** today.
- [ ] `src/components/ActivityDrawer.test.tsx` — **does not exist**; add (at minimum) the `width:var(--w-drawer)` inline-style assert.
- [ ] A CSS-source test for V2/V3/V4 — either extend `tests/tokens.test.ts` or add `tests/css-rules.test.ts` reading `src/index.css` (Pattern 3). Asserts `--w-drawer`, the media override, `:focus-visible`, and the scrollbar rules exist with the right tokens.
- [ ] `tests/e2e/stop-start.spec.ts` — **new** e2e spec (create→stop→start) + a UI-09 viewport test (`test.use({ viewport: { width: 375 } })`). Reuse `createWorkspace` + `waitForResponse`.
- [ ] No framework install needed — the full toolchain is present.

## Security Domain

> `security_enforcement` is treated as enabled (no explicit `false` in config). This phase is a LAN-only, no-auth v1 frontend change (CLAUDE.md security posture). The surface is intentionally minimal.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | v1 is LAN-only, no auth by design (CLAUDE.md; tech-spec §13) — do not add auth assumptions |
| V3 Session Management | no | no sessions in v1 |
| V4 Access Control | no (UI tier) | the backend state machine (`lib/statemachine.py`) is the authority; the UI never offers an illegal action but does not *enforce* it — backend rejects with an envelope error |
| V5 Input Validation | minimal | no new user-text input; Stop/Start take only the workspace id (already in the list); the placeholder renders fixed copy + the id-bound mutation |
| V6 Cryptography | no | none |
| V7 Error Handling / Logging | yes | a stop/start rejection surfaces as a readable envelope error + `console.error` (mirrors the existing `onError` in `LeafPanel`), self-corrects on poll — no secret in the log (the redaction is server-side, already shipped) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| New cross-origin/CDN request sneaking in (font/icon) | Tampering | inline-SVG glyphs only, no CDN; the `googleapis\|gstatic\|jsdelivr` source assert stays green (`tokens.test.ts:66`, `05-UI-SPEC` Security) |
| Optimistic client status masking a backend rejection | Spoofing (of true state) | no Zustand mirror; server-truth poll re-lists the real status (criterion 4) — a failed transition self-corrects, never wedges |
| Illegal lifecycle action offered by the UI | Elevation (of action) | show-only-applicable gating + backend `TRANSITIONS` table authority (criterion 1) |
| Double-fire of a lifecycle mutation | (consistency) | `disabled` while `isPending` is the guard; both Start affordances disable together (Pitfall 7) |

**No new network endpoint, no new secret, no new third-party request.** The only new calls are same-origin `POST /api/v1/workspaces/{id}/stop|start` via the existing hooks.

## Sources

### Primary (HIGH confidence)
- `ui/src/hooks/useTerminal.ts` (read in full) — gate at line 178, teardown 288-302, effect dep `[workspaceId,status]` at 303
- `ui/src/hooks/useWorkspaces.ts` — `useStopWorkspace`/`useStartWorkspace` (67-68), `onSettled` invalidation (61-64), 3s poll (19)
- `ui/src/components/TerminalPanel.tsx` — header cluster, `iconButtonStyle`, `overlayBase`/`overlayButton`/`Spinner`, body wrapper, `useTerminal(id,status,…)` at 205
- `ui/src/components/WorkspaceLayout.tsx` — `LeafPanel` destroy wiring (69-76), `TerminalPanel` props (96-103)
- `ui/src/components/ActivityDrawer.tsx` — `DRAWER_WIDTH` (40), `drawerStyle.width` (83), `outline:"none"` (92), `role=dialog`
- `ui/src/index.css` — `@theme` block (32), `--w-sidebar`/`--w-modal` (50/52), `--radius-full` (63), `--ease-ui` (66), `prefers-reduced-motion` (264); **no** `:focus-visible`/scrollbar/drawer-media
- `ui/tests/tokens.test.ts` — the CSS-source-assert precedent (readFileSync of `src/index.css`)
- `ui/tests/integration/restore.test.tsx` — the `MockWebSocket` registry pattern for socket assertions
- `ui/src/hooks/useTerminal.test.tsx` — the mock-WS/xterm/ResizeObserver test harness + `offsetWidth` spy for jsdom layout
- `ui/tests/msw/handlers.ts` — envelope shape, seed list (has `ws-running`/`ws-stopped`); **no stop/start handler** (Wave 0 gap)
- `ui/tests/e2e/terminal.spec.ts` — the journey + `waitForResponse` POST-assertion pattern to extend
- `ui/playwright.config.ts` / `ui/vitest.config.ts` / `ui/package.json` — toolchain versions + e2e webServer
- `.planning/phases/05-stop-start-controls-drawer-polish/05-CONTEXT.md`, `05-UI-SPEC.md` — binding decisions + acceptance criteria
- `.planning/REQUIREMENTS.md` (UI-07..UI-11), `.planning/STATE.md` — provenance

### Secondary (MEDIUM confidence)
- General `:focus-visible` vs `:focus` browser behavior (UA heuristic, keyboard/programmatic only) — well-established, baseline-available; relied on for the V3 mouse-click-no-ring contract
- jsdom limitations (no `matchMedia`, no pseudo-element/pseudo-class style resolution, `offsetWidth=0`) — confirmed by the repo's own workarounds (`offsetWidth` spy, CSS-source asserts)

### Tertiary (LOW confidence)
- none — every claim is grounded in repo source or the binding spec.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions read from the committed `package.json`; no install occurs.
- Architecture / integration points: HIGH — every seam re-verified against source; the code map in CONTEXT.md was accurate.
- Test strategy / jsdom boundaries: HIGH — the unit-vs-e2e split is grounded in the repo's existing patterns (`tokens.test.ts` source-asserts, `MockWebSocket` registry, Playwright `waitForResponse`/viewport). The two MEDIUM items are mutation ownership (Open Q1) and placeholder styling (Claude's discretion) — neither blocks planning.
- Pitfalls: HIGH — each is either demonstrated by an existing test pattern or follows directly from jsdom/Tailwind-v4 mechanics.

**Research date:** 2026-06-14
**Valid until:** 2026-07-14 (stable — pinned toolchain, no fast-moving external dependency; the only volatility is the repo itself, which this research already reflects)
