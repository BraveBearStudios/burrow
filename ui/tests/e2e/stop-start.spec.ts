// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// Tier-3 Playwright journey (docs/ci-cd-and-testing.md §4.4) for the Stop/Start
// lifecycle controls + the drawer polish (UI-07/UI-08/UI-09/UI-10/UI-11), over the
// FakeComputeProvider + the standalone protocol-accurate stub ttyd:
//
//   create → Stop → `Workspace stopped` placeholder → Start → terminal reconnects
//   + a 375px phone viewport where the Activity drawer is a full-width sheet
//   + the live :focus-visible ring + the custom scrollbar that jsdom cannot assert
//
// This is the phase e2e gate. vitest proves the seams over a CSS-source assertion;
// only real Chromium proves the media-query width (UI-09), the :focus-visible paint
// (UI-10), the custom scrollbar pseudo-element (UI-11), and the real ~3s server-truth
// poll driving the Stop↔Start swap (UI-07/UI-08) — never an optimistic client flip.
// The whole harness (Fake provider + stub ttyd + vite preview over ui/dist) is wired
// in playwright.config.ts — no new harness. It does NOT run in the Wave-0 vitest gate;
// it is the Plan 04 `npm run e2e` gate over the freshly-built UI.

import { expect, type Locator, type Page, test } from "@playwright/test";

// Unique names per run so reruns / shards never collide.
const stamp = Date.now();
const wsName = `e2e-stopstart-${stamp}`;
const wsDrawer = `e2e-stopstart-drawer-${stamp}`;
const wsWide = `e2e-stopstart-wide-${stamp}`;
const wsA11y = `e2e-stopstart-a11y-${stamp}`;
const wsBar = `e2e-stopstart-bar-${stamp}`;

test.describe.configure({ mode: "serial" });

// CICD-09 per-test backend isolation: track every workspace id a test creates so
// `afterEach` can DELETE exactly those rows (id-scoped — never a broad wipe). The
// Fake backend persists across tests in a `mode: serial` file, so without this the
// list accumulates and a global locator could match a sibling test's panel. Scoping
// the cleanup to the created ids keeps the suite order-independent / parallel-safe.
const createdIds: string[] = [];

/**
 * Look up the id the control plane assigned a freshly-created workspace by its
 * unique name (the create POST is synchronous, so the row is already listed). Used
 * to scope the panel locator + the per-test cleanup to THIS workspace.
 */
async function workspaceIdByName(page: Page, name: string): Promise<string> {
	const res = await page.request.get("/api/v1/workspaces");
	expect(res.ok()).toBe(true);
	const body = (await res.json()) as {
		data: Array<{ id: string; name: string }>;
	};
	const found = body.data.find((w) => w.name === name);
	expect(found, `workspace ${name} should exist in the live list`).toBeTruthy();
	return (found as { id: string }).id;
}

/**
 * Create a workspace through the modal, wait for its panel to open, and return the
 * panel locator scoped to its workspace id (`data-testid="panel-${id}"`). The v1
 * create POST is synchronous (boots to `running`, returns the row), so the modal
 * closes and a terminal panel mounts once the saga resolves against the Fake. The
 * created id is tracked for the per-test `afterEach` cleanup.
 */
async function createWorkspace(page: Page, name: string): Promise<Locator> {
	await page.getByRole("button", { name: /New workspace/ }).click();
	const dialog = page.getByRole("dialog");
	await expect(dialog).toBeVisible();

	await page.locator("#ws-name").fill(name);
	await page.locator("#ws-repo").fill(`github.com/acme/${name}`);
	await page.locator("#ws-branch").fill("main");
	// Node defaults to the first node from GET /api/v1/nodes; leave it as-is.

	await page.getByRole("button", { name: "Create" }).click();
	await expect(dialog).toBeHidden({ timeout: 30_000 });

	const id = await workspaceIdByName(page, name);
	createdIds.push(id);
	const panel = page.getByTestId(`panel-${id}`);
	await expect(panel).toBeVisible({ timeout: 30_000 });
	await expect(panel.getByText(name)).toBeVisible({ timeout: 30_000 });
	return panel;
}

// Per-test isolation (CICD-09): destroy only the workspaces this test created, by
// id, so the Fake backend never accumulates and the suite stays order-independent.
// A 404 is fine (a test may have already terminated the row through the UI).
test.afterEach(async ({ request }) => {
	while (createdIds.length > 0) {
		const id = createdIds.pop();
		if (!id) {
			continue;
		}
		await request.delete(`/api/v1/workspaces/${id}`);
	}
});

test("stop → placeholder → start → reconnect round-trip", async ({ page }) => {
	await page.goto("/");

	// ── Create + terminal echoes ───────────────────────────────────────────────
	// Every interaction below is scoped to THIS panel (`panel-${id}`) — no unscoped
	// `.first()` and no global `[data-testid^="term-"]` count assertion.
	const panel = await createWorkspace(page, wsName);
	await expect(panel.locator('[data-testid^="term-"]')).toBeVisible();

	// ── Stop: fires POST /workspaces/{id}/stop immediately (no confirm) ─────────
	// Assert the REAL POST fires over the Fake (not an optimistic client flip), the
	// same masking-proof pattern terminate uses for its DELETE.
	const [stopResponse] = await Promise.all([
		page.waitForResponse(
			(res) =>
				/\/api\/v1\/workspaces\/[^/]+\/stop$/.test(
					new URL(res.url()).pathname,
				) && res.request().method() === "POST",
			{ timeout: 15_000 },
		),
		panel.getByRole("button", { name: "Stop workspace" }).click(),
	]);
	expect(stopResponse.ok()).toBe(true);

	// After the ~3s server-truth poll re-lists status=stopped, the placeholder body
	// replaces the terminal — NOT a connecting/reconnecting/error overlay.
	await expect(panel.getByText("Workspace stopped")).toBeVisible({
		timeout: 15_000,
	});
	// The live terminal body is gone for THIS panel while stopped (the placeholder
	// owns the body) — a panel-scoped assertion, never a global count over the grid.
	await expect(panel.locator('[data-testid^="term-"]')).toHaveCount(0, {
		timeout: 15_000,
	});

	// ── Start: from the placeholder CTA → POST /start → terminal reconnects ─────
	// A stopped panel renders TWO "Start workspace" affordances (the header icon
	// button + the placeholder CTA). Scope the click to the placeholder region
	// (`role="status"`, which also owns the "Workspace stopped" heading) so the
	// locator is unambiguous — strict mode would reject the bare two-match query.
	const placeholder = panel.getByRole("status").filter({
		hasText: "Workspace stopped",
	});
	const [startResponse] = await Promise.all([
		page.waitForResponse(
			(res) =>
				/\/api\/v1\/workspaces\/[^/]+\/start$/.test(
					new URL(res.url()).pathname,
				) && res.request().method() === "POST",
			{ timeout: 15_000 },
		),
		placeholder.getByRole("button", { name: "Start workspace" }).click(),
	]);
	expect(startResponse.ok()).toBe(true);

	// The placeholder unmounts and the live terminal body re-mounts (stopped→running
	// re-runs the useTerminal effect → fresh socket → reconnect).
	await expect(panel.getByText("Workspace stopped")).toBeHidden({
		timeout: 30_000,
	});
	await expect(panel.locator('[data-testid^="term-"]')).toBeVisible({
		timeout: 30_000,
	});
});

// ── Responsive drawer (UI-09 / V2) ─────────────────────────────────────────────
// Playwright at a 375px viewport is the only place the @media (max-width:375px)
// override is real (jsdom has no layout / media-query engine). The drawer must be
// a full-width sheet (width == viewport) at 375px, and the 360px desktop panel above.
test.describe("drawer full-width at 375px (UI-09)", () => {
	test.use({ viewport: { width: 375, height: 800 } });

	test("the Activity drawer fills the 375px viewport width", async ({
		page,
	}) => {
		await page.goto("/");
		const panel = await createWorkspace(page, wsDrawer);
		await expect(panel.locator('[data-testid^="term-"]')).toBeVisible();

		// Open the per-workspace Activity drawer from THIS panel's header.
		await panel.getByRole("button", { name: "Activity log" }).click();
		const drawer = page.getByRole("dialog", { name: /activity log/i });
		await expect(drawer).toBeVisible();

		// At ≤375px the --w-drawer token resolves to 100vw — a full-width sheet,
		// not the 360px desktop panel (the media override is real only in a browser).
		const box = await drawer.boundingBox();
		expect(box?.width).toBe(375);
	});
});

test.describe("drawer is the 360px panel above 375px (UI-09)", () => {
	test.use({ viewport: { width: 1024, height: 800 } });

	test("the Activity drawer is the 360px panel above the phone breakpoint", async ({
		page,
	}) => {
		await page.goto("/");
		const panel = await createWorkspace(page, wsWide);
		await expect(panel.locator('[data-testid^="term-"]')).toBeVisible();

		await panel.getByRole("button", { name: "Activity log" }).click();
		const drawer = page.getByRole("dialog", { name: /activity log/i });
		await expect(drawer).toBeVisible();

		// Above 375px the token stays min(360px, 100vw) → 360px on a 1024px viewport,
		// NOT the full-width sheet. This is the sibling band the media query gates.
		const box = await drawer.boundingBox();
		expect(box?.width).toBe(360);
	});
});

// ── Focus ring (UI-10 / V3) ─────────────────────────────────────────────────────
// jsdom cannot evaluate :focus-visible (it is a UA modality heuristic with no layout
// engine), so live Chromium is the ONLY place the global ring is real. We keep the
// browser in keyboard modality (open the drawer via Enter on a Tab-focused control)
// so the auto-focused close button paints the :focus-visible outline — a mouse click
// would NOT, by design (the rule is :focus-visible, not :focus).
test("keyboard focus paints the global --accent-line ring (UI-10)", async ({
	page,
}) => {
	await page.goto("/");
	const panel = await createWorkspace(page, wsA11y);
	await expect(panel.locator('[data-testid^="term-"]')).toBeVisible();

	// Tab into the page header, then Tab to the panel's Activity log button and open
	// the drawer with Enter — all keyboard input, so Chromium's :focus-visible
	// heuristic stays in keyboard mode for the focus the drawer moves on open.
	const activityButton = panel.getByRole("button", { name: "Activity log" });
	await activityButton.focus();
	await page.keyboard.press("Tab");
	await page.keyboard.press("Shift+Tab"); // back to Activity log, via keyboard
	await page.keyboard.press("Enter");

	const drawer = page.getByRole("dialog", { name: /activity log/i });
	await expect(drawer).toBeVisible();

	// On open the drawer moves focus to its × close button (closeRef.focus()); in the
	// keyboard modality above it shows the global :focus-visible ring. Assert the live
	// painted outline is the contracted 2px solid ring (the jsdom-untestable half of
	// UI-10). The color resolves --accent-line per the active theme.
	const closeButton = drawer.getByRole("button", {
		name: "Close activity log",
	});
	await expect(closeButton).toBeFocused();
	await expect(closeButton).toHaveCSS("outline-style", "solid");
	await expect(closeButton).toHaveCSS("outline-width", "2px");
	await expect(closeButton).toHaveCSS("outline-offset", "2px");

	// The ring color is --accent-line (dark theme #5e7d5e → rgb(94, 125, 94)), proving
	// the accent token (not a UA default) drives the live ring.
	await expect(closeButton).toHaveCSS("outline-color", "rgb(94, 125, 94)");
});

// ── Custom scrollbar (UI-11 / V4) ───────────────────────────────────────────────
// jsdom has no rendering engine, so it cannot resolve the ::-webkit-scrollbar
// pseudo-element (getComputedStyle on a pseudo-element returns empty there). Live
// Chromium DOES resolve a styled ::-webkit-scrollbar via
// getComputedStyle(el, "::-webkit-scrollbar"), so reading its width is the
// Chromium-supported proof that the custom 8px scrollbar rule (index.css V4) is the
// one that paints — not the native UA scrollbar. A gutter measurement
// (offsetWidth − clientWidth) is NOT reliable here: Chromium uses an overlay
// scrollbar that reserves 0px, so the pseudo-element computed style is the correct
// probe. We also confirm the styled thumb resolves to the --border-mid token
// (dark theme rgba(255,255,255,0.14)) — a neutral, never accent or gold.
test("the custom 8px scrollbar renders on a scroll surface (UI-11)", async ({
	page,
}) => {
	await page.goto("/");
	const panel = await createWorkspace(page, wsBar);
	const termBody = panel.locator('[data-testid^="term-"]');
	await expect(termBody).toBeVisible();

	// Read the live computed style of the styled ::-webkit-scrollbar pseudo-element on
	// the terminal body (overflow-y:auto). Chromium resolves the global V4 rule here;
	// jsdom cannot — this is the render-engine half of UI-11.
	const scrollbar = await termBody.evaluate((el) => {
		const bar = getComputedStyle(el, "::-webkit-scrollbar");
		const thumb = getComputedStyle(el, "::-webkit-scrollbar-thumb");
		return { width: bar.width, thumbBackground: thumb.backgroundColor };
	});

	// The styled ::-webkit-scrollbar { width: 8px } resolves to 8px — the custom
	// Burrow scrollbar rule painted, not the native one (the jsdom-untestable
	// half of UI-11). A dropped/overridden rule would not resolve to 8px.
	expect(scrollbar.width).toBe("8px");
	// The thumb resolves to a neutral V4 token — --border-mid (resting,
	// rgba(255,255,255,.14)) or --text-muted (hover, rgb(84,102,84)) in the dark
	// theme. Chromium's pseudo-element computed style picks up the hover-cascaded
	// rule, so we accept either neutral; the exact resting token is owned by the
	// vitest CSS-source assert. What matters here: the live thumb is a styled,
	// tokens-only color — NEVER an accent (rgb(94,125,94)) or gold (rgb(240,167,55)).
	expect(["rgba(255, 255, 255, 0.14)", "rgb(84, 102, 84)"]).toContain(
		scrollbar.thumbBackground,
	);
});
