// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Tier-2 UI tests run in jsdom with global describe/it/expect; tests/setup.ts
// installs the jest-dom matchers and starts the MSW server for /api/v1 mocking.
export default defineConfig({
	plugins: [react()],
	// react-mosaic-component pulls react-dnd-multi-backend, whose react/react-dom
	// peer excludes 19 — npm would nest an older react-dom and crash against root
	// React 19. The package.json `overrides` pin collapses that; `dedupe` keeps a
	// single runtime in the test bundle too (defense in depth).
	resolve: {
		dedupe: ["react", "react-dom"],
	},
	test: {
		globals: true,
		environment: "jsdom",
		setupFiles: ["./tests/setup.ts"],
		include: ["src/**/*.test.{ts,tsx}", "tests/**/*.test.{ts,tsx}"],
		exclude: ["tests/e2e/**", "node_modules/**"],
	},
});
