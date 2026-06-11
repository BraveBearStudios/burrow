// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// Tier-3 Playwright journey (docs/ci-cd-and-testing.md §4.4) for the activity
// drawer (UI-06), over the FakeComputeProvider + the standalone stub ttyd:
//
//   create → open the panel-header Activity log trigger → see live event rows
//   (a freshly-created workspace logs workspace.created / bootconfig.persisted at
//   birth, so the drawer renders over the Fake) → close via × → re-open → close via Esc
//
// It proves the full open→see-events→close contract end-to-end against the live
// stack the bridge actually talks to. The whole harness (Fake provider + stub ttyd
// + vite preview) is already wired in playwright.config.ts — no new harness needed.

import { expect, type Page, test } from "@playwright/test";

// Unique name per run so reruns / shards never collide.
const stamp = Date.now();
const wsName = `e2e-drawer-${stamp}`;

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

test("activity drawer: create → open → see event rows → close (× and Esc)", async ({
	page,
}) => {
	await page.goto("/");

	// ── Create the workspace and wait for its panel ────────────────────────────
	await createWorkspace(page, wsName);
	await expect(page.locator('[data-testid^="term-"]').first()).toBeVisible();

	// ── Open the activity drawer from the panel header ─────────────────────────
	await page.getByRole("button", { name: "Activity log" }).first().click();
	const drawer = page.getByRole("dialog", { name: /activity log/i });
	await expect(drawer).toBeVisible();

	// The freshly-created workspace logged lifecycle events at birth, so rows render.
	await expect(drawer.getByRole("listitem").first()).toBeVisible({
		timeout: 10_000,
	});

	// ── Close via the × button ─────────────────────────────────────────────────
	await drawer.getByRole("button", { name: "Close activity log" }).click();
	await expect(drawer).toBeHidden();

	// ── Re-open and close via Esc ──────────────────────────────────────────────
	await page.getByRole("button", { name: "Activity log" }).first().click();
	await expect(
		page.getByRole("dialog", { name: /activity log/i }),
	).toBeVisible();
	await page.keyboard.press("Escape");
	await expect(
		page.getByRole("dialog", { name: /activity log/i }),
	).toBeHidden();
});
