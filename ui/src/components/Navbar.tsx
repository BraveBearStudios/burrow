// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// Navbar is the 52px top bar (02-UI-SPEC "Top bar"): the brand mark (an --accent
// square with a gold hexagon SVG) + the `Workspaces` gold overline, one capacity
// chip per node (useNodes), the four-swatch theme switcher, and the green
// `+ New workspace` button. The capacity chip groups the live workspace list by
// `node` for the running count and shows the REAL memoryUsedFraction as a percent
// (no fabricated GB) — gold mono on both numbers (prestige discipline). Theme
// swatches switch the data-theme root (controlled by the App) with aria-pressed on
// the active one; the + button calls the onNewWorkspace prop the App wires to the
// modal. ALL colors are tokens (no hex); green is reserved for the button; gold is
// reserved for the stats; icons are inline outline SVG (no icon font / CDN).

import { useMemo } from "react";
import { useNodes } from "../hooks/useNodes";
import { useWorkspaces } from "../hooks/useWorkspaces";
import type { ThemeName } from "../lib/themes";
import { THEMES } from "../lib/themes";
import type { NodeCapacity } from "../types/workspace";

export interface NavbarProps {
	/** The active theme (the App owns the data-theme root). */
	theme: ThemeName;
	/** Switch the active theme (swatch click). */
	onThemeChange: (theme: ThemeName) => void;
	/** Open the New Workspace modal (the green + button). */
	onNewWorkspace: () => void;
}

const ICON = {
	stroke: "currentColor",
	strokeWidth: 1.5,
	fill: "none",
	strokeLinecap: "round" as const,
	strokeLinejoin: "round" as const,
};

/** The gold hexagon brand glyph (inline SVG — no icon font, 02-UI-SPEC). */
function HexMark() {
	return (
		<svg
			width="16"
			height="16"
			viewBox="0 0 24 24"
			aria-hidden="true"
			{...ICON}
			strokeWidth={1.8}
			stroke="var(--gold)"
		>
			<path d="M12 2 21 7v10l-9 5-9-5V7z" />
		</svg>
	);
}

/** The inline `+` for the primary button. */
function PlusIcon() {
	return (
		<svg
			width="14"
			height="14"
			viewBox="0 0 24 24"
			aria-hidden="true"
			{...ICON}
		>
			<line x1="12" y1="5" x2="12" y2="19" />
			<line x1="5" y1="12" x2="19" y2="12" />
		</svg>
	);
}

const barStyle: React.CSSProperties = {
	display: "flex",
	alignItems: "center",
	gap: "var(--space-md)",
	height: "var(--h-topbar)",
	flex: "0 0 var(--h-topbar)",
	padding: "0 var(--space-md)",
	background: "var(--bg-surf)",
	borderBottom: "0.5px solid var(--border)",
};

const goldMono: React.CSSProperties = {
	fontFamily: "var(--font-mono)",
	color: "var(--gold)",
};

/** Render the real used-memory fraction as a percent, or `—` when unknown. */
function capacityText(node: NodeCapacity): string {
	if (node.memoryUsedFraction === null) {
		return "—";
	}
	return `${Math.round(node.memoryUsedFraction * 100)}%`;
}

/** One capacity chip: a status dot + node name + gold running count + gold mem%. */
function CapacityChip({
	node,
	runningCount,
}: {
	node: NodeCapacity;
	runningCount: number;
}) {
	return (
		<span
			style={{
				display: "inline-flex",
				alignItems: "center",
				gap: "6px",
				padding: "4px 10px",
				background: "var(--bg-panel)",
				border: "0.5px solid var(--border)",
				borderRadius: "var(--radius-control)",
				fontFamily: "var(--font-sans)",
				fontSize: "12px",
				color: "var(--text-sub)",
			}}
		>
			<span
				aria-hidden="true"
				style={{
					width: "var(--sz-status-dot)",
					height: "var(--sz-status-dot)",
					borderRadius: "var(--radius-full)",
					background: node.overThreshold ? "var(--err)" : "var(--ok)",
				}}
			/>
			<span>{node.node} · </span>
			<span style={goldMono}>{runningCount}</span>
			<span> running · </span>
			<span style={goldMono}>{capacityText(node)}</span>
			<span> mem</span>
		</span>
	);
}

export function Navbar({ theme, onThemeChange, onNewWorkspace }: NavbarProps) {
	const { data: nodes } = useNodes();
	const { data: workspaces } = useWorkspaces();

	// Group the live list by node for each chip's running count (02-UI-SPEC).
	const runningByNode = useMemo(() => {
		const counts = new Map<string, number>();
		for (const w of workspaces ?? []) {
			if (w.status === "running") {
				counts.set(w.node, (counts.get(w.node) ?? 0) + 1);
			}
		}
		return counts;
	}, [workspaces]);

	return (
		<header style={barStyle}>
			<span
				style={{
					display: "flex",
					alignItems: "center",
					gap: "var(--space-sm)",
				}}
			>
				<span
					aria-hidden="true"
					style={{
						display: "grid",
						placeItems: "center",
						width: "var(--sz-brand-mark)",
						height: "var(--sz-brand-mark)",
						borderRadius: "7px",
						background: "var(--accent)",
					}}
				>
					<HexMark />
				</span>
				<span style={{ display: "flex", flexDirection: "column" }}>
					<span
						style={{
							fontFamily: "var(--font-display)",
							fontWeight: 500,
							fontSize: "15px",
							letterSpacing: "-0.2px",
							color: "var(--text)",
						}}
					>
						Burrow
					</span>
					<span
						style={{
							fontFamily: "var(--font-sans)",
							fontSize: "9.5px",
							fontWeight: 500,
							letterSpacing: "2px",
							textTransform: "uppercase",
							color: "var(--gold)",
						}}
					>
						Workspaces
					</span>
				</span>
			</span>

			<nav
				aria-label="Node capacity"
				style={{
					display: "flex",
					alignItems: "center",
					gap: "var(--space-sm)",
				}}
			>
				{(nodes ?? []).map((node) => (
					<CapacityChip
						key={node.node}
						node={node}
						runningCount={runningByNode.get(node.node) ?? 0}
					/>
				))}
			</nav>

			<span style={{ flex: 1 }} />

			{/* Theme swatches: each is individually keyboard-focusable + aria-labelled
			    (e.g. "Dark theme"), so the wrapper stays presentational. */}
			<div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
				{THEMES.map((t) => (
					<button
						key={t.name}
						type="button"
						aria-label={t.label}
						aria-pressed={theme === t.name}
						onClick={() => onThemeChange(t.name)}
						style={{
							width: "14px",
							height: "14px",
							padding: 0,
							borderRadius: "var(--radius-full)",
							background: t.swatch,
							border:
								theme === t.name
									? "1.5px solid var(--accent-line)"
									: "0.5px solid var(--border-mid)",
							cursor: "pointer",
						}}
					/>
				))}
			</div>

			<button
				type="button"
				onClick={onNewWorkspace}
				style={{
					display: "inline-flex",
					alignItems: "center",
					gap: "6px",
					height: "32px",
					padding: "0 12px",
					background: "var(--accent)",
					color: "var(--btn-pri-text)",
					border: "none",
					borderRadius: "var(--radius-control)",
					fontFamily: "var(--font-sans)",
					fontSize: "13px",
					fontWeight: 500,
					cursor: "pointer",
				}}
			>
				<PlusIcon />
				New workspace
			</button>
		</header>
	);
}
