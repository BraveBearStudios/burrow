// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// The Burrow app shell — Wave 4 (02-05) assembles the full themed surface: the
// Navbar (52px) over a middle row of the WorkspaceList sidebar (228px) + the
// react-mosaic WorkspaceLayout grid (fills), with the StatusBar (32px) pinned
// below. The root carries `data-theme` (default `dark`) + the
// `aria-label="Burrow workspace manager"` landmark; the four theme swatches in the
// Navbar switch it (02-UI-SPEC: ship all four themes). The Navbar's
// `+ New workspace` button opens the NewWorkspaceModal, which on a successful
// create opens the new panel (layoutStore.openPanel) and closes itself.
//
// Chrome invariants (criterion 15): the top bar (52px) and status bar (32px) never
// grow or shrink; only the inner columns (sidebar list + Mosaic grid) scroll
// (`overflow: hidden` containers + inner scroll). Tokens-only — no hex; the theme
// is the single source of every color (index.css [data-theme] blocks).

import { useState } from "react";
import { Navbar } from "./components/Navbar";
import { NewWorkspaceModal } from "./components/NewWorkspaceModal";
import { StatusBar } from "./components/StatusBar";
import { WorkspaceLayout } from "./components/WorkspaceLayout";
import { WorkspaceList } from "./components/WorkspaceList";
import { DEFAULT_THEME, type ThemeName } from "./lib/themes";

const rootStyle: React.CSSProperties = {
	display: "flex",
	flexDirection: "column",
	height: "100vh",
	background: "var(--bg)",
	color: "var(--text)",
	overflow: "hidden",
};

const middleRowStyle: React.CSSProperties = {
	display: "flex",
	flex: 1,
	minHeight: 0,
	overflow: "hidden",
};

export function App() {
	const [theme, setTheme] = useState<ThemeName>(DEFAULT_THEME);
	const [isModalOpen, setModalOpen] = useState(false);

	return (
		<div data-theme={theme} style={rootStyle}>
			<main
				aria-label="Burrow workspace manager"
				style={{
					display: "flex",
					flexDirection: "column",
					flex: 1,
					minHeight: 0,
				}}
			>
				<Navbar
					theme={theme}
					onThemeChange={setTheme}
					onNewWorkspace={() => setModalOpen(true)}
				/>
				<div style={middleRowStyle}>
					<WorkspaceList />
					<WorkspaceLayout />
				</div>
				<StatusBar />
			</main>

			{isModalOpen ? (
				<NewWorkspaceModal onClose={() => setModalOpen(false)} />
			) : null}
		</div>
	);
}
