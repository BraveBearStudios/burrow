// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Tier-2 UI tests run in jsdom with global describe/it/expect; tests/setup.ts
// installs the jest-dom matchers and starts the MSW server for /api/v1 mocking.
export default defineConfig({
	plugins: [react()],
	test: {
		globals: true,
		environment: "jsdom",
		setupFiles: ["./tests/setup.ts"],
		include: ["src/**/*.test.{ts,tsx}", "tests/**/*.test.{ts,tsx}"],
		exclude: ["tests/e2e/**", "node_modules/**"],
	},
});
