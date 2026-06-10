// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// TerminalPanel mounts useTerminal for one workspace and renders the 02-UI-SPEC
// panel: a 36px header (drag grip, name, branch chip, gold model label, split /
// detach / terminate icon buttons) over a `.term` body div bound to the hook's
// containerRef. The connecting / reconnecting / error overlays (Task 3) render
// over the body per the hook's status. Icon buttons are inline outline SVG
// (no icon font / CDN — 02-UI-SPEC Registry Safety) wired to optional no-op props
// (Wave 3/4 connects split/detach/terminate).

import { useTerminal } from "../hooks/useTerminal";
import type { WorkspaceStatus } from "../types/workspace";

export interface TerminalPanelProps {
	id: string;
	name: string;
	status: WorkspaceStatus;
	branch?: string;
	model?: string;
	onSplit?: (id: string) => void;
	onDetach?: (id: string) => void;
	onTerminate?: (id: string) => void;
}

const ICON = {
	stroke: "currentColor",
	strokeWidth: 1.5,
	fill: "none",
	strokeLinecap: "round" as const,
	strokeLinejoin: "round" as const,
};

function GripIcon() {
	return (
		<svg
			width="14"
			height="14"
			viewBox="0 0 24 24"
			aria-hidden="true"
			{...ICON}
		>
			<circle cx="9" cy="6" r="1" />
			<circle cx="9" cy="12" r="1" />
			<circle cx="9" cy="18" r="1" />
			<circle cx="15" cy="6" r="1" />
			<circle cx="15" cy="12" r="1" />
			<circle cx="15" cy="18" r="1" />
		</svg>
	);
}

function SplitIcon() {
	return (
		<svg
			width="15"
			height="15"
			viewBox="0 0 24 24"
			aria-hidden="true"
			{...ICON}
		>
			<rect x="3" y="4" width="18" height="16" rx="2" />
			<line x1="12" y1="4" x2="12" y2="20" />
		</svg>
	);
}

function PlugIcon() {
	return (
		<svg
			width="15"
			height="15"
			viewBox="0 0 24 24"
			aria-hidden="true"
			{...ICON}
		>
			<path d="M9 7V3M15 7V3" />
			<path d="M7 7h10v4a5 5 0 0 1-10 0V7Z" />
			<line x1="12" y1="16" x2="12" y2="21" />
		</svg>
	);
}

function CloseIcon() {
	return (
		<svg
			width="15"
			height="15"
			viewBox="0 0 24 24"
			aria-hidden="true"
			{...ICON}
		>
			<line x1="6" y1="6" x2="18" y2="18" />
			<line x1="18" y1="6" x2="6" y2="18" />
		</svg>
	);
}

const headerStyle: React.CSSProperties = {
	display: "flex",
	alignItems: "center",
	gap: "var(--space-sm)",
	height: "var(--h-panel-header)",
	padding: "0 var(--space-md)",
	background: "var(--bg-panel)",
	borderBottom: "0.5px solid var(--border)",
	flex: "0 0 auto",
};

const iconButtonStyle: React.CSSProperties = {
	display: "grid",
	placeItems: "center",
	width: "24px",
	height: "24px",
	border: "none",
	background: "transparent",
	color: "var(--text-muted)",
	borderRadius: "var(--radius-control)",
	cursor: "pointer",
};

export function TerminalPanel({
	id,
	name,
	status,
	branch,
	model,
	onSplit,
	onDetach,
	onTerminate,
}: TerminalPanelProps) {
	const { containerRef } = useTerminal(id, status);

	return (
		<section
			style={{
				display: "flex",
				flexDirection: "column",
				height: "100%",
				background: "var(--bg-surf)",
				border: "0.5px solid var(--border)",
				borderRadius: "var(--radius-panel)",
				overflow: "hidden",
			}}
		>
			<header style={headerStyle}>
				<span style={{ color: "var(--text-muted)", cursor: "grab" }}>
					<GripIcon />
				</span>
				<span
					style={{
						fontFamily: "var(--font-sans)",
						fontWeight: 500,
						fontSize: "12.5px",
						color: "var(--text)",
					}}
				>
					{name}
				</span>
				{branch ? (
					<span
						style={{
							fontFamily: "var(--font-mono)",
							fontSize: "11px",
							color: "var(--text-sub)",
							background: "var(--bg-panel-alt)",
							border: "0.5px solid var(--border)",
							borderRadius: "var(--radius-chip)",
							padding: "1px 6px",
						}}
					>
						{branch}
					</span>
				) : null}
				{model ? (
					<span
						style={{
							fontFamily: "var(--font-mono)",
							fontSize: "10.5px",
							color: "var(--gold)",
						}}
					>
						{model}
					</span>
				) : null}
				<span style={{ flex: 1 }} />
				<button
					type="button"
					aria-label="Split"
					style={iconButtonStyle}
					onClick={() => onSplit?.(id)}
				>
					<SplitIcon />
				</button>
				<button
					type="button"
					aria-label="Detach (keeps the session running)"
					style={iconButtonStyle}
					onClick={() => onDetach?.(id)}
				>
					<PlugIcon />
				</button>
				<button
					type="button"
					aria-label="Terminate"
					style={iconButtonStyle}
					onClick={() => onTerminate?.(id)}
				>
					<CloseIcon />
				</button>
			</header>

			<div
				ref={containerRef}
				className="term"
				data-testid={`term-${id}`}
				style={{
					position: "relative",
					flex: 1,
					minHeight: 0,
					padding: "11px 13px",
					background: "var(--bg-surf)",
					color: "var(--text-sub)",
					fontFamily: "var(--font-mono)",
					fontSize: "12px",
					lineHeight: 1.6,
					overflowY: "auto",
				}}
			/>
		</section>
	);
}
