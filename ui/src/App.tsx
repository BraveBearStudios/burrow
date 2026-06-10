// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// Placeholder shell. The real top-bar / sidebar / mosaic grid / status-bar shell
// is assembled in Waves 2-4 (Plans 02-03/04/05); this only proves the app mounts
// and the design tokens resolve so the foundation build is green.
export function App() {
	return (
		<main
			style={{
				display: "grid",
				placeItems: "center",
				height: "100vh",
				background: "var(--bg)",
				color: "var(--text)",
				fontFamily: "var(--font-display)",
			}}
		>
			<p>Burrow</p>
		</main>
	);
}
