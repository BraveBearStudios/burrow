// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

import { defineConfig, devices } from "@playwright/test";

// Tier-3 e2e config (docs/ci-cd-and-testing.md §4.4): Playwright drives a real
// browser through the full journey — create → terminal echoes → split/drag →
// detach→reconnect → terminate — over the FakeComputeProvider + a protocol-accurate
// stub ttyd, with NO real infrastructure.
//
// Two ways to bring up the stack:
//
//   • Local / single-host (this config's `webServer`): three local processes —
//     the standalone stub ttyd (api/tests/e2e/stub_ttyd_server.py) on 127.0.0.1:7681,
//     the FastAPI control plane over BURROW_COMPUTE=fake (with BURROW_E2E_TTYD_HOST
//     pointing the bridge's dial at the local stub instead of the unroutable
//     10.99.0.x worker IP), and `vite preview` serving the built SPA on :4173.
//   • Containerized CI: `docker-compose.e2e.yml` (api + stub-ttyd + nginx-served ui).
//     Set BURROW_E2E_USE_COMPOSE=1 and start the compose stack out-of-band; this
//     config then just points Playwright at the running UI.
//
// Browser binaries are installed in CI via `npx playwright install chromium`.

const UI_PORT = 4173;
const API_PORT = 8000;
const STUB_TTYD_PORT = 7681;
const BASE_URL = `http://localhost:${UI_PORT}`;

// When the compose stack is already up (CI), skip the local webServer processes.
const useCompose = process.env.BURROW_E2E_USE_COMPOSE === "1";

const localWebServers = [
	// 1) Standalone protocol-accurate stub ttyd (the worker terminal stand-in).
	{
		command: `python -m tests.e2e.stub_ttyd_server --host 127.0.0.1 --port ${STUB_TTYD_PORT}`,
		cwd: "../api",
		port: STUB_TTYD_PORT,
		reuseExistingServer: !process.env.CI,
		stdout: "pipe" as const,
		stderr: "pipe" as const,
	},
	// 2) FastAPI control plane over the FakeComputeProvider. BURROW_E2E_TTYD_HOST
	//    retargets the bridge's upstream dial at the local stub (operator env, not
	//    client input — SSRF posture unchanged); ALLOWED_ORIGIN matches the SPA origin
	//    so the WS CSWSH allow-list accepts the browser's upgrade.
	{
		command: `uv run uvicorn main:app --host 127.0.0.1 --port ${API_PORT}`,
		cwd: "../api",
		url: `http://127.0.0.1:${API_PORT}/api/v1/health`,
		reuseExistingServer: !process.env.CI,
		env: {
			BURROW_COMPUTE: "fake",
			BURROW_DB: "sqlite",
			DATABASE_PATH: "./burrow-e2e.db",
			ALLOWED_ORIGIN: BASE_URL,
			BURROW_E2E_TTYD_HOST: "127.0.0.1",
		},
		stdout: "pipe" as const,
		stderr: "pipe" as const,
	},
	// 3) The built SPA served by `vite preview` (preview.proxy forwards /api/v1 + /ws
	//    to the api, same-origin). `npm run build` must have produced ui/dist first.
	{
		command: "npm run preview",
		port: UI_PORT,
		reuseExistingServer: !process.env.CI,
		stdout: "pipe" as const,
		stderr: "pipe" as const,
	},
];

export default defineConfig({
	testDir: "./tests/e2e",
	fullyParallel: false,
	forbidOnly: !!process.env.CI,
	retries: process.env.CI ? 2 : 0,
	reporter: "list",
	use: {
		baseURL: BASE_URL,
		trace: "on-first-retry",
		video: "retain-on-failure",
		screenshot: "only-on-failure",
	},
	projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
	webServer: useCompose ? undefined : localWebServers,
});
