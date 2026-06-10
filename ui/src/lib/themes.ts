// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// The four-theme registry (02-UI-SPEC Design System: ship all four —
// dark/dark-soft/medium/light, default dark). This is the single source of truth
// the Navbar swatch switcher and the App data-theme root share. The `swatch`
// value is each theme's OWN --bg hex (the swatch must depict the theme it
// switches TO, which by definition is not the active theme, so it can't resolve
// from a live --token). These literals are theme-identity DATA in a lib/ module,
// not component styling — every component still reads only --tokens (criterion 1).

/** The four shipped themes, in switcher order. */
export type ThemeName = "dark" | "dark-soft" | "medium" | "light";

export interface ThemeDef {
	name: ThemeName;
	label: string;
	/** This theme's own page background (--bg), for the switcher swatch. */
	swatch: string;
}

/** The default theme on first load (02-UI-SPEC: dark / hero). */
export const DEFAULT_THEME: ThemeName = "dark";

export const THEMES: ThemeDef[] = [
	{ name: "dark", label: "Dark theme", swatch: "#1a1c1a" },
	{ name: "dark-soft", label: "Dark soft theme", swatch: "#3a4740" },
	{ name: "medium", label: "Medium theme", swatch: "#6a8170" },
	{ name: "light", label: "Light theme", swatch: "#f0f2f0" },
];
