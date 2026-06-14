// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// CSS-source guard for the V2/V3/V4 polish rules (UI-09/UI-10/UI-11). jsdom does
// not evaluate `:focus-visible`, `::-webkit-scrollbar`, or a width `@media`, so —
// exactly like tokens.test.ts — these assert the rule's PRESENCE and SHAPE in the
// raw src/index.css string. RED until Plan 03 adds the rules; a real regression
// guard thereafter (it goes RED again if anyone deletes a rule).

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

// Resolve from the vitest cwd (the ui/ project root) — robust in jsdom where
// import.meta.url is an http:// URL that fileURLToPath rejects (tokens.test.ts).
const cssPath = resolve(process.cwd(), "src/index.css");
const css = readFileSync(cssPath, "utf8");

describe("css-rules — responsive drawer width (UI-09 / V2)", () => {
	it("declares the --w-drawer token default min(360px, 100vw)", () => {
		expect(css).toMatch(/--w-drawer:\s*min\(\s*360px\s*,\s*100vw\s*\)/);
	});

	it("overrides --w-drawer to 100vw under @media (max-width: 375px) on :root", () => {
		// The token override is plain custom-property re-declaration on :root inside
		// the media block (NOT a nested @theme — Pitfall 6).
		expect(css).toMatch(
			/@media\s*\(\s*max-width:\s*375px\s*\)\s*\{[^{}]*:root\s*\{[^}]*--w-drawer:\s*100vw/s,
		);
	});
});

describe("css-rules — global focus-visible ring (UI-10 / V3)", () => {
	it("declares a :focus-visible rule with a 2px var(--accent-line) outline + 2px offset", () => {
		expect(css).toMatch(
			/:focus-visible\s*\{[^}]*outline:\s*2px\s+solid\s+var\(--accent-line\)[^}]*outline-offset:\s*2px/s,
		);
	});
});

describe("css-rules — global custom scrollbar (UI-11 / V4)", () => {
	it("styles ::-webkit-scrollbar-thumb with var(--border-mid)", () => {
		expect(css).toMatch(
			/::-webkit-scrollbar-thumb\s*\{[^}]*background:\s*var\(--border-mid\)/s,
		);
	});

	it("declares the Firefox scrollbar-width: thin + scrollbar-color tokens", () => {
		expect(css).toMatch(/scrollbar-width:\s*thin/);
		expect(css).toMatch(/scrollbar-color:\s*var\(--border-mid\)\s+transparent/);
	});
});
