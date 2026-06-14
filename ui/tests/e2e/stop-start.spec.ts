// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// Tier-3 Playwright journey (docs/ci-cd-and-testing.md §4.4) for the Stop/Start
// lifecycle controls + the responsive drawer (UI-07/UI-08/UI-09), over the
// FakeComputeProvider + the standalone protocol-accurate stub ttyd:
//
//   create → Stop → `Workspace stopped` placeholder → Start → terminal reconnects
//   + a 375px phone viewport where the Activity drawer is a full-width sheet
//
// This is the cross-cutting acceptance scaffold the phase e2e leg (Plan 04) fills:
// it drives the real browser against the live stack the Stop/Start mutations hit
// (POST /api/v1/workspaces/{id}/stop|start over the Fake) and asserts the
// server-truth poll drives the placeholder↔terminal swap — never an optimistic
// client flip. The whole harness (Fake provider + stub ttyd + vite preview) is
// already wired in playwright.config.ts — no new harness needed. It does NOT run
// in the Wave-0 vitest gate (that is the Plan 04 `npm run e2e` gate over the built
// UI); the feature it exercises lands in Plan 02/03.

import { expect, type Page, test } from "@playwright/test";

// Unique names per run so reruns / shards never collide.
const stamp = Date.now();
const wsName = `e2e-stopstart-${stamp}`;
const wsDrawer = `e2e-stopstart-drawer-${stamp}`;

test.describe.configure({ mode: "serial" });

/**
 * Create a workspace through the modal and wait for its panel to open. The v1
 * create POST is synchronous (boots to `running`, returns the row), so the modal
 * closes and a terminal panel mounts once the saga resolves against the Fake.
 */
async function createWorkspace(page: Page, name: string): Promise<void> {
	await page.getByRole("button", { name: /New workspace/ }).click();
	const dialog = page.getByRole("dialog");
	await expect(dialog).toBeVisible();

	await page.locator("#ws-name").fill(name);
	await page.locator("#ws-repo").fill(`github.com/acme/${name}`);
	await page.locator("#ws-branch").fill("main");
	// Node defaults to the first node from GET /api/v1/nodes; leave it as-is.

	await page.getByRole("button", { name: "Create" }).click();
	await expect(dialog).toBeHidden({ timeout: 30_000 });
	await expect(page.getByText(name).first()).toBeVisible({ timeout: 30_000 });
}

test("stop → placeholder → start → reconnect round-trip", async ({ page }) => {
	await page.goto("/");

	// ── Create + terminal echoes ───────────────────────────────────────────────
	await createWorkspace(page, wsName);
	await expect(page.locator('[data-testid^="term-"]').first()).toBeVisible();

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
		page.getByRole("button", { name: "Stop workspace" }).first().click(),
	]);
	expect(stopResponse.ok()).toBe(true);

	// After the ~3s server-truth poll re-lists status=stopped, the placeholder body
	// replaces the terminal — NOT a connecting/reconnecting/error overlay.
	await expect(page.getByText("Workspace stopped")).toBeVisible({
		timeout: 15_000,
	});

	// ── Start: from the placeholder CTA → POST /start → terminal reconnects ─────
	const [startResponse] = await Promise.all([
		page.waitForResponse(
			(res) =>
				/\/api\/v1\/workspaces\/[^/]+\/start$/.test(
					new URL(res.url()).pathname,
				) && res.request().method() === "POST",
			{ timeout: 15_000 },
		),
		page.getByRole("button", { name: "Start workspace" }).first().click(),
	]);
	expect(startResponse.ok()).toBe(true);

	// The placeholder unmounts and the live terminal body re-mounts (stopped→running
	// re-runs the useTerminal effect → fresh socket → reconnect).
	await expect(page.getByText("Workspace stopped")).toBeHidden({
		timeout: 30_000,
	});
	await expect(page.locator('[data-testid^="term-"]').first()).toBeVisible({
		timeout: 30_000,
	});
});

// ── Responsive drawer (UI-09 / V2) ─────────────────────────────────────────────
// Playwright at a 375px viewport is the only place the @media (max-width:375px)
// override is real (jsdom has no layout / media-query engine). The drawer must be
// a full-width sheet (width == viewport) at 375px.
test.describe("drawer full-width at 375px (UI-09)", () => {
	test.use({ viewport: { width: 375, height: 800 } });

	test("the Activity drawer fills the 375px viewport width", async ({
		page,
	}) => {
		await page.goto("/");
		await createWorkspace(page, wsDrawer);
		await expect(page.locator('[data-testid^="term-"]').first()).toBeVisible();

		// Open the per-workspace Activity drawer from the panel header.
		await page.getByRole("button", { name: "Activity log" }).first().click();
		const drawer = page.getByRole("dialog", { name: /activity log/i });
		await expect(drawer).toBeVisible();

		// At ≤375px the drawer is a full-width sheet, not the 360px desktop panel.
		const box = await drawer.boundingBox();
		expect(box?.width).toBe(375);
	});
});
