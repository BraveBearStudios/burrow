// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// ActivityDrawer is the per-workspace event-log drawer (UI-06) to the binding
// 04-UI-SPEC contract: a right-anchored 360px slide-in over the grid, opened iff
// `workspaceId` is non-null. It polls GET /api/v1/workspaces/{id}/events via
// useWorkspaceEvents ONLY while open (criterion 5), reverses the oldest-first feed
// to newest-first (criterion 2), and renders each event as a color-coded badge
// (badgeFor / EVENT_BADGE) + a mono HH:MM:SS timestamp + a redacted `data` summary.
// boot.error rows are emphasized (2px --err left bar + --err-tinted bg + the
// redacted reason in red mono, criterion 4); no other row gets a bar/tint. Four
// data states: loading→shimmer, empty→"No activity yet", error→the --err strip over
// kept rows, populated→the live list. A11y: role=dialog, focus trap, Esc closes,
// focus RETURNS to the trigger on close, --accent-line focus ring, aria-live=polite,
// status never color-only (dot + text label). Tokens only — no hex, no --gold. The
// drawer is read-only: it renders the server-redacted `data` verbatim and makes only
// the same-origin events poll (threat T-04-03A/B) — no CTA, no mutation.

import { useEffect, useMemo, useRef } from "react";
import { useWorkspaceEvents } from "../hooks/useWorkspaceEvents";
import { badgeFor } from "../lib/events";
import type { WorkspaceEvent } from "../types/event";

export interface ActivityDrawerProps {
	/** The workspace whose log to show; null = closed (no poll, no render). */
	workspaceId: string | null;
	/** The workspace name for the title / aria-label (falls back to "Workspace"). */
	workspaceName?: string;
	/** Close the drawer (×, Esc, or scrim click). */
	onClose: () => void;
}

/** 04-UI-SPEC Copywriting: the drawer empty + poll-error states. */
const EMPTY_HEADING = "No activity yet";
const EMPTY_BODY =
	"Events appear here as this workspace boots, connects, and stops.";
const POLL_ERROR = "Couldn't load the event log. Retrying…";

/** Drawer width: 360px desktop, min(360px,80vw) tablet, 100vw phone (criterion 10). */
const DRAWER_WIDTH = "min(360px, 100vw)";

const ICON = {
	stroke: "currentColor",
	strokeWidth: 1.5,
	fill: "none",
	strokeLinecap: "round" as const,
	strokeLinejoin: "round" as const,
};

/** The × close glyph (reuses the TerminalPanel CloseIcon shape). */
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

const drawerStyle: React.CSSProperties = {
	position: "fixed",
	top: 0,
	right: 0,
	bottom: 0,
	width: DRAWER_WIDTH,
	display: "flex",
	flexDirection: "column",
	background: "var(--bg-surf)",
	borderLeft: "0.5px solid var(--border)",
	// Slide in from the right; the global prefers-reduced-motion block stills it.
	transform: "translateX(0)",
	transition: "transform 200ms var(--ease-ui)",
	zIndex: 60,
	outline: "none",
};

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

const titleStyle: React.CSSProperties = {
	fontFamily: "var(--font-display)",
	fontWeight: 500,
	fontSize: "16px",
	color: "var(--text)",
	flex: 1,
	minWidth: 0,
	overflow: "hidden",
	textOverflow: "ellipsis",
	whiteSpace: "nowrap",
};

const listStyle: React.CSSProperties = {
	listStyle: "none",
	margin: 0,
	padding: 0,
	flex: 1,
	minHeight: 0,
	overflowY: "auto",
};

const badgeStyle = (token: string, mono?: boolean): React.CSSProperties => ({
	display: "inline-flex",
	alignItems: "center",
	height: "18px",
	padding: "0 6px",
	background: "var(--bg-panel-alt)",
	border: "0.5px solid var(--border)",
	borderRadius: "var(--radius-chip)",
	fontFamily: mono ? "var(--font-mono)" : "var(--font-sans)",
	fontWeight: 500,
	fontSize: "12px",
	color: token,
});

const dotStyle = (token: string): React.CSSProperties => ({
	flex: "0 0 auto",
	width: "var(--sz-status-dot)",
	height: "var(--sz-status-dot)",
	borderRadius: "var(--radius-full)",
	background: token,
});

const timestampStyle: React.CSSProperties = {
	marginLeft: "auto",
	fontFamily: "var(--font-mono)",
	fontSize: "11.5px",
	color: "var(--text-muted)",
};

/** Render the redacted `data` as compact `key: value · key: value` mono text. */
function dataSummary(data: Record<string, unknown>): string {
	return Object.entries(data)
		.map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`)
		.join(" · ");
}

/** Absolute HH:MM:SS from an ISO createdAt (the canonical per-row time). */
function formatTime(createdAt: string): string {
	const d = new Date(createdAt);
	if (Number.isNaN(d.getTime())) {
		return createdAt;
	}
	return d.toLocaleTimeString("en-GB", { hour12: false });
}

/** Loading shimmer rows — copy of the WorkspaceList ShimmerRows treatment. */
function ShimmerRows() {
	return (
		<ul style={listStyle} aria-hidden="true">
			{[0, 1, 2, 3].map((i) => (
				<li
					key={i}
					style={{
						height: "44px",
						margin: "8px 16px",
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

/** A single read-only event row (non-interactive <li>). */
function EventRow({ event }: { event: WorkspaceEvent }) {
	const badge = badgeFor(event.type, event.data);
	const isBootError = event.type === "boot.error";
	const summary = dataSummary(event.data);

	return (
		<li
			style={{
				display: "flex",
				flexDirection: "column",
				gap: "4px",
				minHeight: "44px",
				padding: "10px 16px",
				borderBottom: "0.5px solid var(--border)",
				// boot.error emphasis: the 2px --err left bar + the --err-tinted bg
				// (reuse the WorkspaceList poll-error treatment); no other row gets this.
				...(isBootError
					? {
							background: "var(--bg-panel-alt)",
							borderLeft: "2px solid var(--err)",
						}
					: {}),
			}}
		>
			<div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
				<span aria-hidden="true" style={dotStyle(badge.token)} />
				<span style={badgeStyle(badge.token, badge.mono)}>{badge.label}</span>
				<span style={timestampStyle}>{formatTime(event.createdAt)}</span>
			</div>
			{summary !== "" ? (
				<span
					style={{
						fontFamily: "var(--font-mono)",
						fontSize: "11.5px",
						lineHeight: 1.5,
						wordBreak: "break-word",
						// boot.error's redacted reason surfaces in --err mono.
						color: isBootError ? "var(--err)" : "var(--text-sub)",
					}}
				>
					{summary}
				</span>
			) : null}
		</li>
	);
}

export function ActivityDrawer({
	workspaceId,
	workspaceName,
	onClose,
}: ActivityDrawerProps) {
	const isOpen = workspaceId !== null;
	const { data, isLoading, isError } = useWorkspaceEvents(workspaceId, isOpen);
	// Newest-first: the endpoint returns oldest-first → reverse client-side.
	const rows = useMemo(() => [...(data ?? [])].reverse(), [data]);

	const drawerRef = useRef<HTMLElement>(null);
	const closeRef = useRef<HTMLButtonElement>(null);
	// The element focused before the drawer opened, so focus can RETURN on close.
	const triggerRef = useRef<HTMLElement | null>(null);

	// On open: stash the trigger + move focus into the drawer. On close: restore
	// focus to the trigger (04-UI-SPEC a11y — NewWorkspaceModal does not do this).
	useEffect(() => {
		if (!isOpen) {
			return;
		}
		triggerRef.current = document.activeElement as HTMLElement | null;
		closeRef.current?.focus();
		return () => {
			triggerRef.current?.focus?.();
		};
	}, [isOpen]);

	if (!isOpen) {
		return null;
	}

	const title = workspaceName ? `${workspaceName} activity` : "Activity";

	// Focus trap: keep Tab cycling within the drawer's focusable controls.
	const onKeyDown = (e: React.KeyboardEvent) => {
		if (e.key === "Escape") {
			onClose();
			return;
		}
		if (e.key !== "Tab") {
			return;
		}
		const focusables = drawerRef.current?.querySelectorAll<HTMLElement>(
			'button, [href], [tabindex]:not([tabindex="-1"])',
		);
		if (!focusables || focusables.length === 0) {
			return;
		}
		const first = focusables[0];
		const last = focusables[focusables.length - 1];
		if (e.shiftKey && document.activeElement === first) {
			e.preventDefault();
			last.focus();
		} else if (!e.shiftKey && document.activeElement === last) {
			e.preventDefault();
			first.focus();
		}
	};

	return (
		<>
			{/* The scrim is a real <button> so click-to-dismiss is keyboard-accessible
			    and lint-clean; the drawer (Esc-closable) sits above it. */}
			<button
				type="button"
				aria-label="Dismiss activity log"
				onClick={onClose}
				style={{
					position: "fixed",
					inset: 0,
					width: "100%",
					height: "100%",
					border: "none",
					background: "var(--bg)",
					opacity: 0.4,
					cursor: "default",
					zIndex: 59,
				}}
			/>
			<aside
				ref={drawerRef}
				role="dialog"
				aria-modal="true"
				aria-label={`${workspaceName ?? "Workspace"} activity log`}
				tabIndex={-1}
				onKeyDown={onKeyDown}
				style={drawerStyle}
			>
				<header style={headerStyle}>
					<span style={titleStyle}>{title}</span>
					<button
						ref={closeRef}
						type="button"
						aria-label="Close activity log"
						onClick={onClose}
						style={iconButtonStyle}
					>
						<CloseIcon />
					</button>
				</header>

				{isError ? (
					<div
						role="alert"
						style={{
							margin: "8px 16px",
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
							padding: "var(--space-xl) var(--space-lg)",
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
					// aria-live=polite so a newly-polled event is announced (a11y).
					<ul style={listStyle} aria-live="polite">
						{rows.map((event) => (
							<EventRow key={event.id} event={event} />
						))}
					</ul>
				)}
			</aside>
		</>
	);
}
