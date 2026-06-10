// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

import { defineConfig, devices } from "@playwright/test";

// Tier-3 e2e config skeleton (Wave 5 / Plan 02-06 finalizes the webServer wiring
// over the FakeComputeProvider + stub ttyd). Browser binaries are installed in CI
// via `npx playwright install`; this plan only declares the dep + config.
export default defineConfig({
	testDir: "./tests/e2e",
	fullyParallel: true,
	forbidOnly: !!process.env.CI,
	retries: process.env.CI ? 2 : 0,
	reporter: "list",
	use: {
		baseURL: "http://localhost:4173",
		trace: "on-first-retry",
	},
	projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
	// webServer is finalized by the e2e plan (02-06): boot the vite preview server
	// + the FastAPI control plane over FakeComputeProvider + stub ttyd before specs.
	// webServer: { command: "npm run preview", url: "http://localhost:4173", reuseExistingServer: !process.env.CI },
});
