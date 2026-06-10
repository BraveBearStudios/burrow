// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// WorkspaceList is the 228px sidebar (UI-01): a live-polled list of workspaces
// (useWorkspaces, ~3s) rendered to the binding 02-UI-SPEC sidebar contract. Each
// row = a 7px status dot colored per status (criterion 7), the name, a muted
// mono `repo · branch` line, and — for non-running states — an inline status
// overline. A `creating` row's dot pulses (reuse index.css @keyframes pulse).
// `destroyed` rows are filtered out. Clicking a row opens its panel + marks it
// active (layoutStore.openPanel + setActive); the active row (bound to
// activeWorkspaceId, two-way synced with the focused Mosaic panel — Wave 3)
// shows the --accent-bg fill + a 2px --accent-line left bar and is aria-current.
// Loading → shimmer rows; empty → the `No workspaces yet` copy; poll error → an
// --err strip above the last-known rows. ALL colors are tokens (no hex); gold is
// never used here (status dots are --ok/--warn/--err/--text-muted only). A
// pinned footer carries the static self-host user row (no auth — LAN-only).

import { useWorkspaces } from "../hooks/useWorkspaces";
import { isVisibleStatus, STATUS_COLOR } from "../lib/status";
import { useLayoutStore } from "../store/layoutStore";
import type { Workspace, WorkspaceStatus } from "../types/workspace";

/** 02-UI-SPEC Copywriting: the sidebar empty + poll-error states. */
const EMPTY_HEADING = "No workspaces yet";
const EMPTY_BODY =
	"Spin one up with + New workspace to watch Claude Code run in the browser.";
const POLL_ERROR = "Couldn't reach the control plane. Retrying…";

/** Statuses that render an inline overline after the name (running shows none). */
function overlineFor(status: WorkspaceStatus): string | null {
	return status === "running" ? null : status;
}

const sidebarStyle: React.CSSProperties = {
	display: "flex",
	flexDirection: "column",
	width: "var(--w-sidebar)",
	flex: "0 0 var(--w-sidebar)",
	background: "var(--bg-surf)",
	borderRight: "0.5px solid var(--border)",
	overflow: "hidden",
};

const headerStyle: React.CSSProperties = {
	display: "flex",
	alignItems: "center",
	justifyContent: "space-between",
	padding: "var(--space-md) var(--space-md) var(--space-sm)",
};

const overlineLabelStyle: React.CSSProperties = {
	fontFamily: "var(--font-sans)",
	fontSize: "11px",
	fontWeight: 500,
	letterSpacing: "1.3px",
	textTransform: "uppercase",
	color: "var(--text-muted)",
};

const listStyle: React.CSSProperties = {
	listStyle: "none",
	margin: 0,
	padding: "0 var(--space-sm)",
	flex: 1,
	minHeight: 0,
	overflowY: "auto",
};

const rowButtonBase: React.CSSProperties = {
	position: "relative",
	display: "flex",
	alignItems: "flex-start",
	gap: "var(--space-sm)",
	width: "100%",
	textAlign: "left",
	border: "none",
	background: "transparent",
	color: "var(--text)",
	borderRadius: "var(--radius-control)",
	padding: "10px 11px",
	marginBottom: "2px",
	cursor: "pointer",
	font: "inherit",
};

const dotStyle = (status: WorkspaceStatus): React.CSSProperties => ({
	flex: "0 0 auto",
	width: "var(--sz-status-dot)",
	height: "var(--sz-status-dot)",
	marginTop: "5px",
	borderRadius: "var(--radius-full)",
	background: STATUS_COLOR[status],
	// A creating row's dot pulses until it resolves (live indication, UI-01).
	// Longhand so the running dot's animationName is "" (no pulse), not "none".
	...(status === "creating"
		? {
				animationName: "pulse",
				animationDuration: "1.4s",
				animationTimingFunction: "ease-in-out",
				animationIterationCount: "infinite",
			}
		: {}),
});

const nameStyle: React.CSSProperties = {
	fontFamily: "var(--font-sans)",
	fontWeight: 500,
	fontSize: "13px",
	color: "var(--text)",
};

const repoLineStyle: React.CSSProperties = {
	fontFamily: "var(--font-mono)",
	fontSize: "11.5px",
	color: "var(--text-muted)",
	marginTop: "2px",
};

/** The 2px --accent-line rounded left-edge bar on the active row (criterion 8). */
const activeBarStyle: React.CSSProperties = {
	position: "absolute",
	left: 0,
	top: "9px",
	bottom: "9px",
	width: "2px",
	borderRadius: "var(--radius-full)",
	background: "var(--accent-line)",
};

/** A single sidebar row — the only interactive element per workspace. */
function WorkspaceRow({ workspace }: { workspace: Workspace }) {
	const activeWorkspaceId = useLayoutStore((s) => s.activeWorkspaceId);
	const openPanel = useLayoutStore((s) => s.openPanel);
	const setActive = useLayoutStore((s) => s.setActive);
	const isActive = activeWorkspaceId === workspace.id;
	const overline = overlineFor(workspace.status);

	const onClick = () => {
		openPanel(workspace.id);
		setActive(workspace.id);
	};

	return (
		<li aria-label={workspace.name}>
			<button
				type="button"
				onClick={onClick}
				aria-current={isActive ? "true" : undefined}
				style={{
					...rowButtonBase,
					background: isActive ? "var(--accent-bg)" : "transparent",
				}}
			>
				{isActive ? <span aria-hidden="true" style={activeBarStyle} /> : null}
				<span
					data-testid="status-dot"
					data-status={workspace.status}
					aria-hidden="true"
					style={dotStyle(workspace.status)}
				/>
				<span style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
					<span style={{ display: "flex", alignItems: "baseline", gap: "8px" }}>
						<span style={nameStyle}>{workspace.name}</span>
						{overline ? (
							<span
								style={{
									...overlineLabelStyle,
									color: STATUS_COLOR[workspace.status],
								}}
							>
								{overline}
							</span>
						) : null}
					</span>
					<span style={repoLineStyle}>
						{`${workspace.projectRepo} · ${workspace.projectBranch}`}
					</span>
				</span>
			</button>
		</li>
	);
}

/** Loading shimmer rows — soft placeholders while the first poll lands. */
function ShimmerRows() {
	return (
		<ul style={listStyle} aria-hidden="true">
			{[0, 1, 2, 3].map((i) => (
				<li
					key={i}
					style={{
						height: "44px",
						margin: "0 0 2px",
						borderRadius: "var(--radius-control)",
						background: "var(--bg-hover)",
						animation: "pulse 1.4s ease-in-out infinite",
						opacity: 0.5,
					}}
				/>
			))}
		</ul>
	);
}

const footerStyle: React.CSSProperties = {
	display: "flex",
	alignItems: "center",
	gap: "var(--space-sm)",
	padding: "var(--space-sm) var(--space-md)",
	borderTop: "0.5px solid var(--border)",
};

/** The pinned, static self-host user row (no auth in v1 — LAN-only). */
function SidebarFooter() {
	return (
		<div style={footerStyle}>
			<span
				aria-hidden="true"
				style={{
					display: "grid",
					placeItems: "center",
					width: "var(--sz-avatar)",
					height: "var(--sz-avatar)",
					borderRadius: "var(--radius-full)",
					background: "var(--accent-bg)",
					color: "var(--accent-line)",
					border: "0.5px solid var(--border)",
					fontFamily: "var(--font-sans)",
					fontSize: "12px",
					fontWeight: 500,
				}}
			>
				m
			</span>
			<span style={{ display: "flex", flexDirection: "column", flex: 1 }}>
				<span
					style={{
						fontFamily: "var(--font-sans)",
						fontSize: "12.5px",
						fontWeight: 500,
						color: "var(--text)",
					}}
				>
					maintainer
				</span>
				<span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
					self-hosted
				</span>
			</span>
		</div>
	);
}

export function WorkspaceList() {
	const { data, isLoading, isError } = useWorkspaces();
	const rows = (data ?? []).filter((w) => isVisibleStatus(w.status));

	return (
		<nav aria-label="Workspaces" style={sidebarStyle}>
			<div style={headerStyle}>
				<span style={overlineLabelStyle}>Workspaces</span>
			</div>

			{isError ? (
				<div
					role="alert"
					style={{
						margin: "0 var(--space-sm) var(--space-sm)",
						padding: "8px 11px",
						borderRadius: "var(--radius-control)",
						background: "var(--bg-panel-alt)",
						borderLeft: "2px solid var(--err)",
						color: "var(--err)",
						fontSize: "11.5px",
					}}
				>
					{POLL_ERROR}
				</div>
			) : null}

			{isLoading ? (
				<ShimmerRows />
			) : rows.length === 0 ? (
				<div
					style={{
						flex: 1,
						display: "flex",
						flexDirection: "column",
						alignItems: "center",
						justifyContent: "center",
						gap: "6px",
						textAlign: "center",
						padding: "0 var(--space-lg)",
					}}
				>
					<p
						style={{
							fontFamily: "var(--font-sans)",
							fontWeight: 500,
							fontSize: "14px",
							color: "var(--text-sub)",
						}}
					>
						{EMPTY_HEADING}
					</p>
					<p style={{ fontSize: "12px", color: "var(--text-muted)" }}>
						{EMPTY_BODY}
					</p>
				</div>
			) : (
				<ul style={listStyle}>
					{rows.map((w) => (
						<WorkspaceRow key={w.id} workspace={w} />
					))}
				</ul>
			)}

			<SidebarFooter />
		</nav>
	);
}
