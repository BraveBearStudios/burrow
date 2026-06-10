// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// Foundation guard: every data-theme block in index.css defines the FULL token
// set (no orphaned hue on theme swap) and the sheet ships no external font CDN.
// This reads the raw CSS source so it stays valid even before any component exists.

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

// Resolve from the vitest cwd (the ui/ project root) — robust in jsdom where
// import.meta.url is an http:// URL that fileURLToPath rejects.
const cssPath = resolve(process.cwd(), "src/index.css");
const css = readFileSync(cssPath, "utf8");

const THEMES = ["dark", "dark-soft", "medium", "light"] as const;
const REQUIRED_TOKENS = [
	"--bg",
	"--bg-surf",
	"--bg-panel",
	"--bg-panel-alt",
	"--bg-hover",
	"--border",
	"--border-mid",
	"--text",
	"--text-sub",
	"--text-muted",
	"--accent",
	"--accent-bg",
	"--accent-line",
	"--gold",
	"--gold-bg",
	"--ok",
	"--warn",
	"--err",
];

function themeBlock(theme: string): string {
	const start = css.indexOf(`[data-theme="${theme}"]`);
	expect(
		start,
		`theme block [data-theme="${theme}"] must exist`,
	).toBeGreaterThan(-1);
	const open = css.indexOf("{", start);
	const close = css.indexOf("}", open);
	return css.slice(open, close);
}

describe("design tokens", () => {
	for (const theme of THEMES) {
		it(`[data-theme="${theme}"] defines the full token set`, () => {
			const block = themeBlock(theme);
			for (const token of REQUIRED_TOKENS) {
				expect(block, `${theme} is missing ${token}`).toContain(`${token}:`);
			}
		});
	}

	it("declares the three font-family tokens", () => {
		expect(css).toContain("--font-display:");
		expect(css).toContain("--font-sans:");
		expect(css).toContain("--font-mono:");
	});

	it("references no external font/icon CDN", () => {
		expect(css).not.toMatch(/googleapis|gstatic|jsdelivr/);
	});
});
