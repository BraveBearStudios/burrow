// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Tailwind v4 is CSS-first (ADR-0008): no tailwind.config.ts, the @theme block
// in src/index.css is the token source. The dev proxy forwards the control-plane
// REST + WS traffic to the FastAPI backend so the SPA can use same-origin paths.
const CONTROL_PLANE = "http://localhost:8000";

export default defineConfig({
	plugins: [react(), tailwindcss()],
	server: {
		proxy: {
			"/api/v1": { target: CONTROL_PLANE, changeOrigin: true },
			"/ws": { target: CONTROL_PLANE, changeOrigin: true, ws: true },
		},
	},
});
