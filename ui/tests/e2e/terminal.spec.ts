// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// Tier-3 Playwright journey (docs/ci-cd-and-testing.md §4.4): the phase e2e gate.
// Drives a real browser through the WHOLE slice over the FakeComputeProvider + the
// standalone protocol-accurate stub ttyd:
//
//   create → terminal echoes → split/tile → detach→reconnect → terminate
//
// This is the cross-cutting acceptance layer — it exercises every prior plan together
// (the WS bridge, useTerminal, the mosaic layoutStore, the surfaces) against the live
// stack the bridge actually talks to. It asserts the detach-vs-terminate semantics
// (detach is non-destructive + shows the reconnecting overlay; terminate is confirm-
// gated by the `Destroy {name}? …` copy and removes the panel) and that the mosaic
// tiles multiple terminals + reflows on a split. It does NOT assert scrollback — there
// is none in v1 (02-RESEARCH Pitfall 7: reconnect attaches to the live PTY).

import { expect, type Page, test } from "@playwright/test";

// Unique names per run so reruns / shards never collide.
const stamp = Date.now();
const wsOne = `e2e-omega-${stamp}`;
const wsTwo = `e2e-sigma-${stamp}`;

test.describe.configure({ mode: "serial" });

/**
 * Create a workspace through the modal and wait for its panel to open. The v1 create
 * POST is synchronous (boots to `running`, returns the row), so the modal closes and a
 * terminal panel mounts once the saga resolves against the Fake + stub ttyd.
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

test("full journey: create → echo → split/tile → detach→reconnect → terminate", async ({
	page,
}) => {
	await page.goto("/");

	// ── Create + terminal echoes ───────────────────────────────────────────────
	await createWorkspace(page, wsOne);
	const termBody = page.locator('[data-testid^="term-"]').first();
	await expect(termBody).toBeVisible();

	// Focus the terminal and type; the stub ttyd echoes INPUT ('0'+data) back as
	// OUTPUT ('0'+data), which xterm renders. Assert the typed token round-trips
	// through the LIVE bridge (proves SC-7: the relay preserved the framing).
	const echoToken = "burrow-echo-123";
	await termBody.click();
	await page.keyboard.type(echoToken);
	await expect
		.poll(async () => (await termBody.innerText()).includes(echoToken), {
			timeout: 15_000,
		})
		.toBe(true);

	// ── Tile: a second workspace opens a second panel (UI-02 mosaic) ────────────
	await createWorkspace(page, wsTwo);
	await expect(page.locator('[data-testid^="term-"]')).toHaveCount(2, {
		timeout: 15_000,
	});

	// ── Split: rebalances the tiled tree (the affordance reflows the panels) ────
	// With two panels open the split affordance rebuilds the tree along a new axis;
	// the two terminals stay mounted (no panel lost) and the layout reflows.
	await page.getByRole("button", { name: "Split" }).first().click();
	await expect(page.locator('[data-testid^="term-"]')).toHaveCount(2);

	// ── Detach (non-destructive) → reconnecting overlay, workspace stays running ─
	await page
		.getByRole("button", { name: "Detach (keeps the session running)" })
		.first()
		.click();
	// The reconnecting overlay appears with the live attempt counter (TERM-06).
	await expect(
		page.getByText(/reconnecting… attempt \d+ \/ 5/).first(),
	).toBeVisible({ timeout: 10_000 });
	// Both panels survive — detach did NOT destroy the workspace (non-destructive).
	await expect(page.locator('[data-testid^="term-"]')).toHaveCount(2);
	// It reconnects to the live session (the overlay clears as the stub re-accepts).
	await expect(page.getByText(/reconnecting…/).first()).toBeHidden({
		timeout: 20_000,
	});

	// ── Terminate (confirm-gated) → one panel removed ──────────────────────────
	await page.getByRole("button", { name: "Terminate" }).first().click();
	// The confirm copy gates the destroy (UI-SPEC criterion 12) — distinct from detach.
	const confirmCopy = page.getByText(
		/Destroy .+\? The container and its session/,
	);
	await expect(confirmCopy).toBeVisible();
	// Cancel keeps the panel.
	await page.getByRole("button", { name: "Cancel" }).click();
	await expect(page.locator('[data-testid^="term-"]')).toHaveCount(2);

	// Re-open the confirm and Destroy: the panel is removed (one terminal left).
	await page.getByRole("button", { name: "Terminate" }).first().click();
	await page.getByRole("button", { name: "Destroy" }).click();
	await expect(page.locator('[data-testid^="term-"]')).toHaveCount(1, {
		timeout: 10_000,
	});
});
