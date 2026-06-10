// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// The MVP one-panel shell: render a single TerminalPanel for the first running
// workspace so an operator can see + type into a live terminal. The full top-bar /
// sidebar / react-mosaic grid / status-bar shell lands in Waves 3-4 (02-04/05);
// QueryClientProvider + data-theme="dark" are provided by main.tsx / index.html.

import { useQuery } from "@tanstack/react-query";
import { api } from "./api/client";
import { TerminalPanel } from "./components/TerminalPanel";
import type { Workspace } from "./types/workspace";

const shellStyle: React.CSSProperties = {
	display: "flex",
	flexDirection: "column",
	height: "100vh",
	padding: "11px",
	background: "var(--bg)",
	color: "var(--text)",
};

export function App() {
	const { data: workspaces } = useQuery({
		queryKey: ["workspaces"],
		queryFn: () => api<Workspace[]>("/workspaces"),
		refetchInterval: 3000,
	});

	const running = workspaces?.find((w) => w.status === "running");

	return (
		<main style={shellStyle} aria-label="Burrow workspace manager">
			{running ? (
				<TerminalPanel
					id={running.id}
					name={running.name}
					status={running.status}
					branch={running.projectBranch}
				/>
			) : (
				<div
					style={{
						flex: 1,
						display: "grid",
						placeItems: "center",
						color: "var(--text-muted)",
						fontFamily: "var(--font-sans)",
					}}
				>
					<p>No running workspaces yet.</p>
				</div>
			)}
		</main>
	);
}
