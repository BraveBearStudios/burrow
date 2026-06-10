// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// The Burrow app shell. Wave 3 swaps the Wave-2 single TerminalPanel for the
// react-mosaic tiling layout (WorkspaceLayout, UI-02): an operator can open /
// split / drag / resize several terminals and the arrangement survives a refresh
// (persisted + reconciled against the live workspace list, UI-05). The top bar /
// sidebar / status bar land in Wave 4 (02-05); QueryClientProvider +
// data-theme="dark" are provided by main.tsx / index.html.

import { WorkspaceLayout } from "./components/WorkspaceLayout";

const shellStyle: React.CSSProperties = {
	display: "flex",
	flexDirection: "column",
	height: "100vh",
	background: "var(--bg)",
	color: "var(--text)",
};

export function App() {
	return (
		<main style={shellStyle} aria-label="Burrow workspace manager">
			<WorkspaceLayout />
		</main>
	);
}
