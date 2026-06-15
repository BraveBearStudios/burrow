<!--
SPDX-FileCopyrightText: 2026 Brave Bear Studios
SPDX-License-Identifier: AGPL-3.0-or-later
-->
# Phase 5: Stop/Start Controls + Drawer Polish - Pattern Map

**Mapped:** 2026-06-14
**Files analyzed:** 9 (5 source modified, 4 test modified/added)
**Analogs found:** 9 / 9 (all in-repo; zero net-new construction without an analog)

> Pure frontend (`ui/`), brownfield polish on the SHIPPED v1.0 UI. Every new
> surface has a direct in-repo analog — there is no "no analog" case. The locked
> approaches in `05-CONTEXT.md` / `05-UI-SPEC.md` map 1:1 to existing code below.
> Conventions are absolute: inline `React.CSSProperties` for components, tokens via
> `var(--…)` never hex, gold reserved (never status/action), inline outline SVG
> icons (no font/CDN), server is source of truth (status never in Zustand), SPDX
> header on every file, vitest+MSW for unit, Playwright+Fake for e2e.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `ui/src/components/TerminalPanel.tsx` (header buttons + `stopped` body branch) | component | event-driven (status-gated render) + request-response (mutation trigger) | itself — existing Detach/Terminate icon buttons + `overlayBase`/`overlayButton`/`Spinner` overlays | exact (self-extension) |
| `ui/src/components/WorkspaceLayout.tsx` (`LeafPanel` stop/start wiring) | component | request-response (mutation → invalidate → poll) | itself — existing `useDestroyWorkspace` → `onTerminate` wiring in `LeafPanel` | exact (self-extension) |
| `ui/src/hooks/useTerminal.ts` (status gating on `stopped`) | hook | event-driven (WS lifecycle state machine) | itself — existing `status !== "running"` early-return + cleanup teardown | exact (self-extension) |
| `ui/src/index.css` (`--w-drawer` token + media query, `:focus-visible`, scrollbar) | config (global stylesheet) | n/a (static CSS) | itself — existing `@theme` block, per-theme blocks, `.burrow-mosaic` chrome, `@keyframes`, `prefers-reduced-motion` | exact (self-extension) |
| `ui/src/components/ActivityDrawer.tsx` (`DRAWER_WIDTH` literal → `var(--w-drawer)`) | component | n/a (style swap) | itself — existing `drawerStyle` / `DRAWER_WIDTH` constant | exact (self-extension) |
| `ui/src/components/TerminalPanel.test.tsx` (Stop/Start + `stopped` placeholder tests) | test | request-response + render assertion | itself — existing terminate-confirm / detach tests + `renderPanel` QueryClient harness | exact |
| `ui/src/components/WorkspaceLayout.test.tsx` (stop/start mutation tests) | test | request-response | itself — existing `Destroy issues DELETE …` test with MSW `server.use` spy | exact |
| `ui/src/components/ActivityDrawer.test.tsx` (responsive width assertion, optional) | test | render assertion | itself — existing drawer render harness + style assertions | role-match |
| `ui/tests/e2e/*.spec.ts` (stop→placeholder→start journey) | test (e2e) | request-response over Fake | `ui/tests/e2e/terminal.spec.ts` (`createWorkspace` helper + `getByRole("button")` flow) | exact |

**Shared infra (read-only, no change):**
`ui/src/hooks/useWorkspaces.ts` (`useStopWorkspace`/`useStartWorkspace` already exported — **no new hook**),
`ui/src/lib/status.ts` (`STATUS_COLOR` / `isVisibleStatus` — read only, single source for status color),
`ui/tests/msw/handlers.ts` (`seedWorkspaces` already includes a `ws-stopped` / `ws-running` row),
`ui/src/types/workspace.ts` (`WorkspaceStatus` union + `TerminalState` union).

---

## Pattern Assignments

### `ui/src/components/TerminalPanel.tsx` — Stop/Start header buttons (component, event-driven render)

**Analog:** the existing Detach + Terminate buttons in the same header cluster (lines 271-308) and the `iconButtonStyle` / `ICON` / icon components.

**Icon-button pattern to copy** (`TerminalPanel.tsx:280-308`) — the new Stop/Start button is a clone of these, gated by `status`:
```tsx
<button
  type="button"
  aria-label="Detach (keeps the session running)"
  style={iconButtonStyle}
  onClick={() => {
    detach();
    onDetach?.(id);
  }}
>
  <PlugIcon />
</button>
<button
  type="button"
  aria-label="Terminate"
  style={iconButtonStyle}
  onClick={() => setConfirmingTerminate(true)}
>
  <CloseIcon />
</button>
```

**`iconButtonStyle` to reuse verbatim** (`TerminalPanel.tsx:136-146`) — 24px grid, transparent bg, `--text-muted`, `--radius-control`. Do **not** redefine:
```tsx
const iconButtonStyle: React.CSSProperties = {
  display: "grid",
  placeItems: "center",
  width: "24px",
  height: "24px",
  border: "none",
  background: "transparent",
  color: "var(--text-muted)",
  borderRadius: "var(--radius-control)",
  cursor: "pointer",
};
```

**Inline-SVG icon component pattern to copy** (`TerminalPanel.tsx:37-43` + `64-77`) — the `ICON` spread + a 15px `viewBox="0 0 24 24"` `<svg>`. The new `StopIcon` (`<rect x="6" y="6" width="12" height="12" rx="1.5"/>`) and `StartIcon` (`<path d="M8 5v14l11-7z"/>`) are clones of `SplitIcon`:
```tsx
const ICON = {
  stroke: "currentColor",
  strokeWidth: 1.5,
  fill: "none",
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

function SplitIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" aria-hidden="true" {...ICON}>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <line x1="12" y1="4" x2="12" y2="20" />
    </svg>
  );
}
```

**Gating model** — render exactly one of Stop/Start by `status`, never disable-both. Order per UI-SPEC: `Activity · [Stop|Start] · Split · Detach · Terminate` (Stop/Start sits **left of Split**, after `<span style={{ flex: 1 }} />` at line 271). The slot is empty for `creating`/`error`/`destroyed`. Conditional render with `status === "running" ? <Stop/> : status === "stopped" ? <Start/> : null`.

**In-flight spinner** — NEW 14px ring, but the geometry copies the existing 22px `Spinner` (`TerminalPanel.tsx:172-186`); reuse `@keyframes spin`, `--border-mid` track, `--accent-line` top-arc, downsized to 14px / 2px border to avoid 24px-button reflow:
```tsx
function Spinner({ gold }: { gold?: boolean }) {
  return (
    <span
      aria-hidden="true"
      style={{
        width: "22px",
        height: "22px",
        borderRadius: "var(--radius-full)",
        border: "2px solid var(--border-mid)",
        borderTopColor: gold ? "var(--gold)" : "var(--accent-line)",
        animation: "spin 0.8s linear infinite",
      }}
    />
  );
}
```
Pending button gets `disabled` + `aria-busy="true"`; spinner replaces the glyph. **No gold** on Stop/Start (pass no `gold` prop).

---

### `ui/src/components/TerminalPanel.tsx` — `stopped` placeholder body branch (component, event-driven render)

**Analog:** the existing connecting / reconnecting / error overlays + the terminate-confirm overlay (`TerminalPanel.tsx:335-420`), and `overlayBase` / `overlayButton`.

**Overlay branch pattern to copy** (`TerminalPanel.tsx:360-384`, the error overlay) — same shape, but `role="status"`/`aria-live="polite"` (a calm resting state, NOT `role="alert"`), and a calm `--bg-surf` wash instead of the dim `rgba(26,28,26,.78)` scrim:
```tsx
{termStatus === "error" ? (
  <div
    style={{ ...overlayBase, background: "rgba(26,28,26,.78)" }}
    role="alert"
    aria-live="assertive"
  >
    <span aria-hidden="true" style={{ /* glyph */ }}>!</span>
    <span>{`Session unavailable. ${ERROR_REASON}.`}</span>
    <button type="button" style={overlayButton} onClick={reattach}>
      Retry
    </button>
  </div>
) : null}
```

**`overlayBase` + `overlayButton` to reuse** (`TerminalPanel.tsx:148-169`) — the centered muted column + the Start CTA button style. The Start CTA reuses `overlayButton` verbatim (with the play glyph + `Start workspace` label):
```tsx
const overlayBase: React.CSSProperties = {
  position: "absolute",
  inset: 0,
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  gap: "9px",
  fontFamily: "var(--font-sans)",
  fontSize: "12px",
  color: "var(--text-sub)",
};

const overlayButton: React.CSSProperties = {
  font: "inherit",
  color: "var(--text)",
  background: "var(--bg-panel-alt)",
  border: "0.5px solid var(--border-mid)",
  borderRadius: "var(--radius-control)",
  padding: "5px 12px",
  cursor: "pointer",
};
```

**Confirm-copy constant pattern** (`TerminalPanel.tsx:30-35`) — the placeholder heading/body copy go in module-level consts the same way `ERROR_REASON` and `terminateConfirmCopy` do:
```tsx
const ERROR_REASON = "the worker isn't ready";
const terminateConfirmCopy = (name: string) =>
  `Destroy ${name}? The container and its session are gone for good.`;
```
New: `Workspace stopped` heading + `This workspace is stopped. Start it to reconnect the terminal and pick up where you left off.` (from the Copywriting Contract). The centered copy `<span>` mirrors the terminate-confirm `maxWidth: "260px", textAlign: "center"` at line 397.

**Ordering rule (load-bearing):** branch the body on `status === "stopped"` **before** the `termStatus`-driven overlays (which start at line 335) so a transient `termStatus` can't flash an error scrim during the running→stopped tear-down. The body wrapper at lines 311-333 (`position: relative`, the `.term` div + overlays) is where the new branch slots in.

---

### `ui/src/hooks/useTerminal.ts` — status gating on `stopped` (hook, event-driven)

**Analog:** itself — the existing single-effect early-return + cleanup teardown already implement the contract; this phase confirms + tests it for `stopped`.

**Existing gate to confirm/extend** (`useTerminal.ts:175-181`) — the effect early-returns for any non-`running` status, so `stopped` already opens no socket and runs no reconnect loop:
```tsx
useEffect(() => {
  const container = containerRef.current;
  // Only a running workspace has a live ttyd to bridge to.
  if (!container || status !== "running") {
    return;
  }
  disposedRef.current = false;
  // … term/socket/observer setup …
```

**Existing teardown on transition** (`useTerminal.ts:288-303`) — the effect's cleanup tears the socket/term/observer down; because `status` is in the dependency array (line 303: `}, [workspaceId, status]);`), a `running → stopped` flip runs this cleanup (socket closes, terminal disconnects), and `stopped → running` re-runs the effect (reconnect):
```tsx
  return () => {
    disposedRef.current = true;
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    observer.disconnect();
    observerRef.current = null;
    socketRef.current?.close();
    socketRef.current = null;
    fitAddon.dispose();
    fitRef.current = null;
    term.dispose();
    termRef.current = null;
  };
}, [workspaceId, status]);
```
**Likely zero production change** — the contract already holds. The work is (a) the failing-first then passing test that asserts no socket opens while `status="stopped"` and the socket tears down on `running→stopped`, and (b) ensuring the panel branches the body before overlays (see TerminalPanel body branch above) so `termStatus` never leaks an error scrim. If any change is needed it is a defensive guard, not a rewrite.

---

### `ui/src/components/WorkspaceLayout.tsx` — `LeafPanel` mutation wiring (component, request-response)

**Analog:** itself — the existing `useDestroyWorkspace` → `onTerminate` wiring in `LeafPanel` (lines 57, 69-76, 96-103).

**Mutation-hook wiring to copy** (`WorkspaceLayout.tsx:52-76`) — add `const stopWorkspace = useStopWorkspace();` / `const startWorkspace = useStartWorkspace();` beside `destroyWorkspace`, and `onStop`/`onStart` handlers mirroring `onTerminate` (but **without** the `closePanel` call — stop/start keep the panel mounted; the poll reconciles status):
```tsx
function LeafPanel({ id, workspace }: { id: string; workspace?: Workspace }) {
  const activeWorkspaceId = useLayoutStore((s) => s.activeWorkspaceId);
  const setActive = useLayoutStore((s) => s.setActive);
  const closePanel = useLayoutStore((s) => s.closePanel);
  const splitPanel = useLayoutStore((s) => s.splitPanel);
  const destroyWorkspace = useDestroyWorkspace();
  const isActive = activeWorkspaceId === id;

  const onTerminate = (panelId: string) => {
    destroyWorkspace.mutate(panelId, {
      onError: (error) => {
        console.error(`Failed to destroy workspace ${panelId}:`, error);
      },
    });
    closePanel(panelId);
  };
```
New `onStop`/`onStart` follow the same `.mutate(panelId, { onError: (e) => console.error(...) })` shape — the self-correcting poll (`onSettled` invalidates `WORKSPACES_KEY` inside the hooks) re-lists the true status, so no toast/banner is needed (matches the destroy `onError` posture).

**Import line to extend** (`WorkspaceLayout.tsx:21`):
```tsx
import { useDestroyWorkspace, useWorkspaces } from "../hooks/useWorkspaces";
```
becomes `import { useDestroyWorkspace, useStartWorkspace, useStopWorkspace, useWorkspaces } from "../hooks/useWorkspaces";`

**Prop pass-through to copy** (`WorkspaceLayout.tsx:96-103`) — add `onStop`/`onStart` alongside `onTerminate`:
```tsx
<TerminalPanel
  id={id}
  name={workspace?.name ?? id}
  status={workspace?.status ?? "running"}
  branch={workspace?.projectBranch}
  onSplit={(panelId) => splitPanel(panelId, "row")}
  onTerminate={onTerminate}
/>
```

**Reconcile keeps `stopped` panels (no change needed)** — the reconcile (`WorkspaceLayout.tsx:128-134`) drops only leaves whose id left the live set; `isVisibleStatus` (`lib/status.ts:23-25`) filters only `destroyed`, so a `stopped` workspace stays in the list and its panel stays mounted:
```tsx
useEffect(() => {
  if (!isSuccess) {
    return;
  }
  const liveIds = new Set((workspaces ?? []).map((w) => w.id));
  reconcile(liveIds);
}, [isSuccess, workspaces, reconcile]);
```

---

### `ui/src/components/ActivityDrawer.tsx` — width token swap (component, style swap)

**Analog:** itself — the existing `DRAWER_WIDTH` constant + `drawerStyle` (lines 39-40, 78-93).

**The literal to replace** (`ActivityDrawer.tsx:39-40`):
```tsx
/** Drawer width: 360px desktop, min(360px,80vw) tablet, 100vw phone (criterion 10). */
const DRAWER_WIDTH = "min(360px, 100vw)";
```
**`drawerStyle` consuming it** (`ActivityDrawer.tsx:78-93`) — swap `width: DRAWER_WIDTH` for `width: "var(--w-drawer)"`; the responsiveness moves into the token (declared once in `index.css` `@theme`, overridden under `@media (max-width:375px)`). Drop or correct the now-stale comment (the 04-UI-REVIEW flagged it as misleading):
```tsx
const drawerStyle: React.CSSProperties = {
  position: "fixed",
  top: 0,
  right: 0,
  bottom: 0,
  width: DRAWER_WIDTH,
  display: "flex",
  flexDirection: "column",
  background: "var(--bg-surf)",
  borderLeft: "0.5px solid var(--border)",
  transform: "translateX(0)",
  transition: "transform 200ms var(--ease-ui)",
  zIndex: 60,
  outline: "none",
};
```
**Note for V3 (focus ring):** `drawerStyle` sets `outline: "none"` on the `<aside>` (line 92). Per UI-SPEC §5, this must not suppress the new global `:focus-visible` ring on the **controls inside** the drawer. `:focus-visible` targets focused elements specifically, so the inline `outline:none` on the bare `<aside>` does not block child rings — but verify the `<aside>`'s own keyboard-focus ring is intentionally suppressed (it is `tabIndex={-1}`, line 331) or scope the removal.

---

### `ui/src/index.css` — `--w-drawer` token + media query (config, static CSS)

**Analog:** the existing fixed-chrome dimensions block in `@theme` (lines 47-56) + the existing `@media (prefers-reduced-motion: reduce)` block (lines 264-272).

**Where the token lives** (`index.css:47-56`) — add `--w-drawer: min(360px, 100vw);` to the fixed-chrome group, alongside `--w-sidebar` / `--w-modal` (a dimension, not a color, so it is NOT re-declared per theme):
```css
/* ── Fixed chrome dimensions (load-bearing, from the mockup) ── */
--h-topbar: 52px;
--h-statusbar: 32px;
--w-sidebar: 228px;
--h-panel-header: 36px;
--w-modal: 400px;
--h-input: 36px;
--sz-status-dot: 7px;
--sz-avatar: 30px;
--sz-brand-mark: 28px;
```

**Media-query pattern to copy** (`index.css:264-272`) — the existing `@media` block is the model for adding `@media (max-width: 375px) { :root { --w-drawer: 100vw; } }`:
```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.001ms !important;
  }
}
```

---

### `ui/src/index.css` — global `:focus-visible` ring + custom scrollbar (config, static CSS)

**Analog:** the per-theme token blocks (lines 97-184, defining `--accent-line` / `--border-mid` / `--text-muted` in every theme) + the `.burrow-mosaic` chrome rules (lines 194-231) as the model for global token-driven CSS.

**Token availability per theme to rely on** (`index.css:97-118`, the `dark` block; same shape repeats for `dark-soft`/`medium`/`light`) — `--accent-line`, `--border-mid`, `--text-muted` are all defined in every theme, so a single global rule renders correctly across all four:
```css
:root,
[data-theme="dark"] {
  --bg-surf: #212321;
  --border: rgba(255, 255, 255, 0.08);
  --border-mid: rgba(255, 255, 255, 0.14);
  --text-muted: #546654;
  --accent-line: #5e7d5e;
  /* … */
}
```

**Token-driven global-rule style to match** (`index.css:198-212`, the `.burrow-mosaic` splitter rules) — net-new rules use the same "tokens only, flat, hairline" discipline:
```css
.burrow-mosaic .mosaic-split .mosaic-split-line {
  box-shadow: none;
  border-color: var(--border);
}
.burrow-mosaic .mosaic-split:hover .mosaic-split-line {
  border-color: var(--accent-line);
  opacity: 0.6;
}
```

**Net-new rules (from UI-SPEC §5/§6, verbatim contract — add after the `prefers-reduced-motion` block):**
```css
:focus-visible {
  outline: 2px solid var(--accent-line);
  outline-offset: 2px;
}

/* Chromium / WebKit */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
  background: var(--border-mid);
  border-radius: var(--radius-full);
  border: 2px solid transparent;
  background-clip: padding-box;
}
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

/* Firefox */
* { scrollbar-width: thin; scrollbar-color: var(--border-mid) transparent; }
```
Use `:focus-visible` (not `:focus`) so a mouse click does not paint the ring. Thumb is `--border-mid` (a neutral) — never accent, never gold.

---

## Test Pattern Assignments

### `ui/src/components/TerminalPanel.test.tsx` — Stop/Start + placeholder unit tests

**Analog:** the existing terminate-confirm + detach tests (lines 143-217) and the `renderPanel` QueryClient harness (lines 33-40).

**Render harness to reuse** (`TerminalPanel.test.tsx:33-40`) — wraps the panel in a `QueryClient` (the panel renders the closed `ActivityDrawer`, whose hook needs context):
```tsx
function renderPanel(ui: ReactElement): RenderResult {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>,
  );
}
```

**Gating + interaction test pattern to copy** (`TerminalPanel.test.tsx:153-182`) — drive the button by `aria-label`, assert the gated render, assert the callback fires once with the id. The Stop test asserts Stop renders iff `status="running"`, fires `onStop` **immediately** (no confirm), and Start renders iff `status="stopped"`:
```tsx
it("terminate (×) asks the confirm copy and does NOT terminate until Destroy", () => {
  const onTerminate = vi.fn();
  renderPanel(
    <TerminalPanel id="w1" name="project-eta" status="running" onTerminate={onTerminate} />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Terminate" }));
  expect(onTerminate).not.toHaveBeenCalled();
  // … re-open + Destroy → fires once with id
  expect(onTerminate).toHaveBeenCalledWith("w1");
});
```
New Stop test: `fireEvent.click(screen.getByRole("button", { name: "Stop workspace" }))` → `expect(onStop).toHaveBeenCalledWith("w1")` with **no** intervening confirm. Gating test: render `status="stopped"` → `expect(screen.queryByRole("button", { name: "Stop workspace" })).not.toBeInTheDocument()` and the `Workspace stopped` placeholder + `Start workspace` CTA are present. Render `status="creating"` → neither button present.

**Mocking the terminal stack** (`TerminalPanel.test.tsx:27-29`) — reuse verbatim so the panel mounts in jsdom:
```tsx
vi.mock("@xterm/xterm", () => import("../../tests/helpers/mockXterm"));
vi.mock("@xterm/addon-fit", () => import("../../tests/helpers/mockXterm"));
vi.mock("@xterm/xterm/css/xterm.css", () => ({}));
```

---

### `ui/src/components/WorkspaceLayout.test.tsx` — stop/start mutation integration test

**Analog:** the existing `Destroy issues DELETE …` test (lines 80-140) — the MSW `server.use` spy that proves the mutation actually hit the API.

**Mutation-spy pattern to copy** (`WorkspaceLayout.test.tsx:81-133`) — seed a single open panel via `useLayoutStore.setState`, register a `server.use` handler that records the call, click the button, `waitFor` the recorded id. Mirror this for `POST /api/v1/workspaces/:id/stop` and `/start`:
```tsx
let destroyedId: string | null = null;
server.use(
  http.delete("/api/v1/workspaces/:id", ({ params }) => {
    destroyedId = params.id as string;
    return HttpResponse.json({ data: { /* … destroyed row … */ }, meta: {…}, error: null });
  }),
);
renderLayout();
await waitFor(() => expect(screen.getByText("project-eta")).toBeInTheDocument());
fireEvent.click(screen.getByRole("button", { name: "Terminate" }));
fireEvent.click(screen.getByRole("button", { name: "Destroy" }));
await waitFor(() => expect(destroyedId).toBe("ws-running"));
```
New Stop test: seed `mosaicNode: "ws-running"`, `server.use(http.post("/api/v1/workspaces/:id/stop", …))` recording the id + returning a `stopped` row, click `Stop workspace`, `waitFor` the recorded id == `ws-running`. New Start test: seed `mosaicNode: "ws-stopped"` (the MSW seed already has `project-iota` stopped — `handlers.ts:60-74`), `server.use(http.post("/api/v1/workspaces/:id/start", …))`, click `Start workspace`. Assert the panel stays mounted (NOT pruned — unlike terminate).

**Layout-store seed pattern** (`WorkspaceLayout.test.tsx:37-43`, the `beforeEach`):
```tsx
beforeEach(() => {
  localStorage.clear();
  useLayoutStore.setState({ mosaicNode: null, activeWorkspaceId: null });
  installMockWebSocket();
  installMockResizeObserver();
  resetXtermMocks();
});
```

---

### `ui/src/components/ActivityDrawer.test.tsx` — responsive width assertion (optional unit coverage)

**Analog:** the existing drawer render + style-assertion tests (lines 99-152) and the `renderDrawer` MSW harness (lines 69-89).

**Style-assertion pattern** (`ActivityDrawer.test.tsx:136-147`) — jsdom keeps inline-style values un-expanded, so assert the raw inline style/`toHaveStyle`. For V2, assert `drawerStyle` now reads `width: var(--w-drawer)` (the token), not the old `min(360px, 100vw)` literal:
```tsx
const created = await screen.findByText("Created");
expect(created).toHaveStyle({ color: "var(--ok)" });
// boot.error 2px --err bar (raw inline-style assertion):
expect(row.style.borderLeft).toBe("2px solid var(--err)");
```
The full-width-at-375px behavior is better proven in Playwright (jsdom has no layout / media-query engine — see e2e below). A unit test here only confirms the `<aside>` reads the CSS var.

---

### `ui/tests/e2e/*.spec.ts` — stop → placeholder → start journey (Playwright over Fake)

**Analog:** `ui/tests/e2e/terminal.spec.ts` — the full create→echo→detach→terminate journey, and `ui/tests/e2e/activity-drawer.spec.ts` — the create→open-drawer flow. Both share the `createWorkspace` helper.

**`createWorkspace` helper to reuse verbatim** (`terminal.spec.ts:32-45` / identical in `activity-drawer.spec.ts:28-41`):
```ts
async function createWorkspace(page: Page, name: string): Promise<void> {
  await page.getByRole("button", { name: /New workspace/ }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await page.locator("#ws-name").fill(name);
  await page.locator("#ws-repo").fill(`github.com/acme/${name}`);
  await page.locator("#ws-branch").fill("main");
  await page.getByRole("button", { name: "Create" }).click();
  await expect(dialog).toBeHidden({ timeout: 30_000 });
  await expect(page.getByText(name).first()).toBeVisible({ timeout: 30_000 });
}
```

**Journey + role-button + waitForResponse pattern to copy** (`terminal.spec.ts:47-140`) — the stop/start e2e: create → click `Stop workspace` → assert `Workspace stopped` placeholder appears (poll-driven, use `expect(...).toBeVisible({ timeout })`) → assert the terminal `[data-testid^="term-"]` body is gone/replaced → click `Start workspace` (header or placeholder CTA) → assert the placeholder unmounts and the terminal reconnects. Reuse the `waitForResponse` assertion for the lifecycle POST (the detach/terminate spec only uses it for DELETE; clone for `/stop` and `/start`):
```ts
const [deleteResponse] = await Promise.all([
  page.waitForResponse(
    (res) =>
      /\/api\/v1\/workspaces\/[^/]+$/.test(new URL(res.url()).pathname) &&
      res.request().method() === "DELETE",
    { timeout: 15_000 },
  ),
  page.getByRole("button", { name: "Destroy" }).click(),
]);
expect(deleteResponse.ok()).toBe(true);
```
Adapt the regex to `…/workspaces/[^/]+/stop$` (method POST) and `…/start$`.

**Responsive-width assertion (V2, UI-SPEC criterion 8)** — Playwright at a 375px viewport is the only place the media query is real. Set `page.setViewportSize({ width: 375, height: 720 })`, open the drawer, assert `drawer.boundingBox().width === 375` (full-width sheet); then at >375px assert width ~360px. This is net-new (no exact analog assertion exists), but the drawer-open flow comes from `activity-drawer.spec.ts:53-55`:
```ts
await page.getByRole("button", { name: "Activity log" }).first().click();
const drawer = page.getByRole("dialog", { name: /activity log/i });
await expect(drawer).toBeVisible();
```

**Harness note:** the whole e2e harness (Fake provider + stub ttyd + vite preview) is already wired in `playwright.config.ts` — no new harness. `test.describe.configure({ mode: "serial" })` + a `Date.now()`-stamped unique name per run (terminal.spec.ts:20-25) carry over.

---

## Shared Patterns

### Lifecycle mutation hooks (NO new hook)
**Source:** `ui/src/hooks/useWorkspaces.ts:53-69`
**Apply to:** `WorkspaceLayout.LeafPanel` (stop/start wiring), both new placeholder + header buttons.
`useStopWorkspace` / `useStartWorkspace` already exist and POST `/workspaces/{id}/{action}`, each `onSettled`-invalidating `WORKSPACES_KEY`. Do not write a new hook.
```tsx
function useWorkspaceAction(action: "stop" | "start" | "destroy") {
  const queryClient = useQueryClient();
  const method = action === "destroy" ? "DELETE" : "POST";
  const suffix = action === "destroy" ? "" : `/${action}`;
  return useMutation({
    mutationFn: (id: string) =>
      api<Workspace>(`/workspaces/${id}${suffix}`, { method }),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: WORKSPACES_KEY });
    },
  });
}
export const useStopWorkspace = () => useWorkspaceAction("stop");
export const useStartWorkspace = () => useWorkspaceAction("start");
```

### Status → color (single source — read only)
**Source:** `ui/src/lib/status.ts:14-25`
**Apply to:** any status dot/label the new controls render (they read it; they never recolor with a literal). `stopped` maps to `--text-muted` (calm, never `--err`).
```tsx
export const STATUS_COLOR: Record<WorkspaceStatus, string> = {
  running: "var(--ok)",
  creating: "var(--warn)",
  error: "var(--err)",
  stopped: "var(--text-muted)",
  destroyed: "var(--text-muted)",
};
export function isVisibleStatus(status: WorkspaceStatus): boolean {
  return status !== "destroyed";
}
```

### Server-is-source-of-truth (no optimistic status flip)
**Source:** the destroy `onError` posture in `WorkspaceLayout.tsx:69-76` + the `onSettled` invalidation in `useWorkspaces.ts:61-64`.
**Apply to:** Stop/Start. Never mirror status into Zustand. The mutation invalidates `WORKSPACES_KEY`; the ~3s `useWorkspaces` poll (`useWorkspaces.ts:19,26`) drives the final Stop↔Start swap + placeholder↔terminal swap. The spinner clears on `onSettled`; the control swap follows the next poll.

### MSW envelope + seed
**Source:** `ui/tests/msw/handlers.ts:16-26` (the `envelope<T>()` helper) + the seed list (lines 29-90, already including `ws-running` and `ws-stopped`).
**Apply to:** every new vitest/integration test. New `server.use` handlers for `/stop` and `/start` return `envelope({ ...found, status: "stopped"|"running" })` mirroring the DELETE handler (lines 162-184).

### Inline outline SVG icon (no font/CDN)
**Source:** `ui/src/components/TerminalPanel.tsx:37-123` (`ICON` spread + the `Grip/Split/Plug/Close/Activity` components).
**Apply to:** the two new glyphs (Stop square `<rect/>`, Start play-triangle `<path/>`). 15px, `viewBox="0 0 24 24"`, `fill:none`, stroke 1.5, round caps. Never an icon font or CDN (PLAT-05 / the `grep googleapis|gstatic|jsdelivr` assert must stay green).

---

## No Analog Found

None. Every surface in this phase extends or clones an existing in-repo construction. The only "net-new" code (the `:focus-visible` rule, the `::-webkit-scrollbar` rules, the `--w-drawer` media override, the 14px header spinner) follows the exact token-and-discipline pattern of adjacent existing CSS/components, and the UI-SPEC supplies the verbatim rule bodies.

---

## Metadata

**Analog search scope:** `ui/src/components/`, `ui/src/hooks/`, `ui/src/lib/`, `ui/src/types/`, `ui/src/index.css`, `ui/tests/e2e/`, `ui/tests/msw/`
**Files scanned (read in full):** TerminalPanel.tsx, WorkspaceLayout.tsx, ActivityDrawer.tsx, useTerminal.ts, useWorkspaces.ts, status.ts, index.css, types/workspace.ts, TerminalPanel.test.tsx, WorkspaceLayout.test.tsx, ActivityDrawer.test.tsx, useTerminal.test.tsx, useWorkspaces.test.tsx, terminal.spec.ts, activity-drawer.spec.ts, msw/handlers.ts, msw/server.ts (17 files)
**Pattern extraction date:** 2026-06-14
