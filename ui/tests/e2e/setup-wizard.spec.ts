// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// Tier-3 Playwright journey (docs/ci-cd-and-testing.md §4.4) for the first-run GATE
// (SETUP-06), over the FakeComputeProvider + the vite-preview built SPA:
//
//   unconfigured Burrow → the `Set up Burrow` gate blocks the workspace list →
//   walk the four steps over the Fake (connection → template → health → create the
//   first workspace) → setup is marked complete → the gate VANISHES to the normal
//   shell + the new workspace in the list.
//   + a configured Burrow SKIPS the gate and lands straight on the workspace list.
//
// This is the phase e2e gate. vitest (jsdom + MSW, ui/src/components/SetupWizard.test.tsx)
// proves the step seams over mocked HTTP; only real Chromium proves the full
// state → gate → walk → /setup/complete → gate-off cycle against the real built SPA,
// the real cross-origin /api/v1 proxy, and the real TanStack invalidation that flips
// App.tsx off the wizard. The harness (Fake provider + stub ttyd + vite preview over
// ui/dist) is wired in playwright.config.ts — no new harness.
//
// SHARED-DB discipline (the central determinism concern): setup-state is a SINGLE
// row in the shared burrow-e2e.db that persists across every spec in a run. Marking
// it complete is GLOBAL — and the sibling suites (stop-start, terminal, activity) all
// need the gate OFF to create workspaces. So this spec MUST control its own
// precondition and MUST leave setup COMPLETE. There is no reset endpoint, so the
// gate-visible walkthrough is guarded by the live state: on a fresh CI DB
// (setupCompletedAt null) it drives the full gate → walk → vanish journey; on a
// persisted local DB (already complete) it skips that branch (the gate is legitimately
// off — the configured-skip path in Test A already proves it) and stays green. Either
// way the spec leaves setup complete so the siblings are unblocked.

import { expect, type Page, test } from "@playwright/test";

// Unique name per run so reruns / shards never collide on the created workspace.
const stamp = Date.now();
const wsName = `e2e-setup-${stamp}`;

test.describe.configure({ mode: "serial" });

// Track every workspace id this spec creates so afterAll can DELETE exactly those
// rows (id-scoped — never a broad wipe), the 07r cleanup-robustness pattern.
const createdIds: string[] = [];

/** Read the live first-run gate state ({setupCompletedAt}) over the envelope. */
async function readSetupState(page: Page): Promise<string | null> {
	const res = await page.request.get("/api/v1/setup/state");
	expect(res.ok()).toBe(true);
	const body = (await res.json()) as {
		data: { setupCompletedAt: string | null };
	};
	return body.data.setupCompletedAt;
}

/** Look up the id the control plane assigned a freshly-created workspace by name. */
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

// Destroy only the workspaces this spec created, by id, so the Fake backend never
// accumulates and the sibling suites stay order-independent. 200 (deleted) or 404
// (already gone) are both fine; any other status is a silently-failing cleanup.
test.afterAll(async ({ request }) => {
	while (createdIds.length > 0) {
		const id = createdIds.pop();
		if (!id) {
			continue;
		}
		const res = await request.delete(`/api/v1/workspaces/${id}`);
		expect([200, 404]).toContain(res.status());
	}
});

// ── Test A — an unconfigured Burrow shows the gate; walking it completes setup ────
// MUST run FIRST (mode: serial → file order): setup-state is a single shared row, so
// once ANY test marks it complete the gate can never be observed again in this run.
// This test reads the live state at the very top; on a fresh CI DB (setupCompletedAt
// null) it drives the full gate → walk → /setup/complete → vanish journey, and the
// real create→complete flow leaves setup COMPLETE for the configured-skip test below
// (and the sibling suites). On a persisted local DB (already complete — no reset
// endpoint exists) the gate is legitimately off, so this branch skips and Test B alone
// proves the configured-skip path. The suite stays green either way.
test("an unconfigured Burrow shows the gate; walking the four steps completes setup and the gate vanishes", async ({
	page,
}) => {
	const stateBefore = await readSetupState(page);

	// On a persisted local DB setup is already complete (no reset endpoint exists), so
	// the gate is legitimately off — the gate-visible walkthrough cannot be exercised.
	// The configured-skip test below still proves the skip path; skip this branch.
	test.skip(
		stateBefore !== null,
		"DB already configured (no reset endpoint); the gate-visible walkthrough is covered on a fresh CI DB",
	);

	// ── Fresh DB: the gate BLOCKS the app before the workspace list ──────────────
	await page.goto("/");
	const gate = page.getByRole("dialog", { name: /Set up Burrow/ });
	await expect(gate).toBeVisible({ timeout: 30_000 });
	// The hard gate blocks the normal shell — the workspace manager is NOT mounted.
	await expect(
		page.getByRole("main", { name: "Burrow workspace manager" }),
	).toHaveCount(0);

	// ── Step 1: connection — dummy token only (T-13-10: never a real credential) ──
	await gate.locator("#setup-host").fill("https://pve.lan:8006");
	await gate.locator("#setup-user").fill("burrow@pve");
	await gate.locator("#setup-token-name").fill("burrow-token");
	await gate.locator("#setup-token-value").fill("dummy");
	await gate.getByRole("button", { name: "Validate connection" }).click();

	// The Fake testConnection returns success=true → auto-advance to step 2 (template).
	await expect(
		gate.getByRole("button", { name: "Verify template" }),
	).toBeVisible({ timeout: 15_000 });

	// ── Step 2: template — the Fake verifyTemplate returns usable=true ────────────
	await gate.locator("#setup-template-vmid").fill("9000");
	await gate.locator("#setup-template-node").fill("pve");
	await gate.getByRole("button", { name: "Verify template" }).click();

	// ── Step 3: health — usable=true advanced us here; the health step auto-probes
	// GET /health on mount and, with db+compute both "ok" over the Fake, auto-advances
	// to step 4 with NO interaction. So we do NOT click `Re-check` (that would race the
	// auto-advance and detach the button mid-click) — we just wait for step 4's CTA.
	const createCta = gate.getByRole("button", { name: "Create workspace" });
	await expect(createCta).toBeVisible({ timeout: 15_000 });

	// ── Step 4: create the first workspace (Node left Auto) ───────────────────────
	await gate.locator("#setup-ws-name").fill(wsName);
	await gate.locator("#setup-ws-repo").fill(`github.com/acme/${wsName}`);
	// #setup-ws-branch defaults to "main"; leave #setup-ws-node Auto (empty → null).

	// The create POST is what flips the gate: on its success the wizard fires
	// POST /setup/complete, which invalidates ["setupState"] and re-renders App off
	// the wizard. Wait for the real complete POST so the assertion is server-truth.
	const [completeResponse] = await Promise.all([
		page.waitForResponse(
			(res) =>
				new URL(res.url()).pathname === "/api/v1/setup/complete" &&
				res.request().method() === "POST",
			{ timeout: 30_000 },
		),
		createCta.click(),
	]);
	expect(completeResponse.ok()).toBe(true);

	// ── The gate VANISHES to the normal shell ────────────────────────────────────
	await expect(gate).toHaveCount(0, { timeout: 30_000 });
	await expect(
		page.getByRole("main", { name: "Burrow workspace manager" }),
	).toBeVisible({ timeout: 30_000 });

	// The first workspace is in the sidebar list — assert the per-workspace landmark
	// (<li aria-label={name}>) by its exact name, NOT a substring text match (the repo
	// row also contains the name, e.g. `github.com/acme/<name> · main`).
	await expect(
		page
			.getByRole("navigation", { name: "Workspaces" })
			.getByRole("listitem", { name: wsName }),
	).toBeVisible({ timeout: 30_000 });

	// And the server now reports setup COMPLETE (a non-null timestamp) — the durable
	// side of the journey, and the state the sibling suites need left behind.
	expect(await readSetupState(page)).not.toBeNull();

	// Track the created workspace for the id-scoped afterAll cleanup.
	const id = await workspaceIdByName(page, wsName);
	createdIds.push(id);
});

// ── Test B — a configured Burrow SKIPS the gate ─────────────────────────────────
// Runs SECOND. By now setup is complete (Test A's walkthrough on a fresh DB, or an
// already-persisted DB). The POST is an idempotent belt-and-braces precondition that
// also leaves the DB in the complete state the sibling suites require. Proves
// SETUP-06's configured-skip path on every DB starting state.
test("a configured Burrow skips the gate and lands on the workspace list", async ({
	page,
}) => {
	// Idempotent precondition: ensure setup is marked complete (safe whether or not
	// Test A ran the full walkthrough — re-stamping is a no-op-equivalent).
	const completeRes = await page.request.post("/api/v1/setup/complete");
	expect(completeRes.ok()).toBe(true);
	expect(await readSetupState(page)).not.toBeNull();

	await page.goto("/");

	// The normal shell renders: the `Burrow workspace manager` landmark + the Navbar
	// `New workspace` button — never the gate.
	await expect(
		page.getByRole("main", { name: "Burrow workspace manager" }),
	).toBeVisible({ timeout: 30_000 });
	await expect(
		page.getByRole("button", { name: /New workspace/ }),
	).toBeVisible();

	// The `Set up Burrow` gate dialog is absent — a configured Burrow never shows it.
	await expect(page.getByRole("dialog", { name: /Set up Burrow/ })).toHaveCount(
		0,
	);
});
