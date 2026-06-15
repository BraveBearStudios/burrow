// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// TerminalPanel mounts useTerminal for one workspace and renders the 02-UI-SPEC
// panel: a 36px header (drag grip, name, branch chip, gold model label, split /
// detach / terminate icon buttons) over a `.term` body div bound to the hook's
// containerRef. The connecting / reconnecting / error overlays (Task 3) render
// over the body per the hook's status. Icon buttons are inline outline SVG
// (no icon font / CDN — 02-UI-SPEC Registry Safety) wired to optional no-op props
// (Wave 3/4 connects split/detach/terminate).

import { useState } from "react";
import { useTerminal } from "../hooks/useTerminal";
import type { WorkspaceStatus } from "../types/workspace";
import { ActivityDrawer } from "./ActivityDrawer";

export interface TerminalPanelProps {
	id: string;
	name: string;
	status: WorkspaceStatus;
	branch?: string;
	model?: string;
	onSplit?: (id: string) => void;
	onDetach?: (id: string) => void;
	onTerminate?: (id: string) => void;
	/**
	 * Fire the WS-06 lifecycle stop for this workspace (UI-07). Owned by
	 * `LeafPanel` (`useStopWorkspace`), passed in like `onTerminate`. Plan 02 wires
	 * the gated header button + the body branch that call this; the prop is declared
	 * here so the Wave-0 failing-first tests compile against the locked seam.
	 */
	onStop?: (id: string) => void;
	/** Fire the WS-07 lifecycle start for this workspace (UI-08). See `onStop`. */
	onStart?: (id: string) => void;
	/** True while the stop mutation is in flight (disables the button, aria-busy). */
	stopPending?: boolean;
	/** True while the start mutation is in flight (disables Start affordances). */
	startPending?: boolean;
	/** Fired when the terminal hits a terminal state (Pitfall 4: invalidate list). */
	onTerminalEvent?: (event: "error" | "closed") => void;
}

/** Human-readable reason for the error overlay (02-UI-SPEC Copywriting). */
const ERROR_REASON = "the worker isn't ready";

/** 02-UI-SPEC Copywriting — the terminate confirmation copy ({name} interpolated). */
const terminateConfirmCopy = (name: string) =>
	`Destroy ${name}? The container and its session are gone for good.`;

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

/** Stop glyph (UI-07): an outline rounded square — neutral, never the solid block. */
function StopIcon() {
	return (
		<svg
			width="15"
			height="15"
			viewBox="0 0 24 24"
			aria-hidden="true"
			{...ICON}
		>
			<rect x="6" y="6" width="12" height="12" rx="1.5" />
		</svg>
	);
}

/** Start glyph (UI-08): an outline play-triangle, matching the outline icon set. */
function StartIcon() {
	return (
		<svg
			width="15"
			height="15"
			viewBox="0 0 24 24"
			aria-hidden="true"
			{...ICON}
		>
			<path d="M8 5v14l11-7z" />
		</svg>
	);
}

/** Activity-log glyph (a pulse/list line) — opens the per-workspace event drawer. */
function ActivityIcon() {
	return (
		<svg
			width="15"
			height="15"
			viewBox="0 0 24 24"
			aria-hidden="true"
			{...ICON}
		>
			<path d="M3 12h4l2 6 4-14 2 8h6" />
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

const overlayBase: React.CSSProperties = {
	position: "absolute",
	inset: 0,
	display: "flex",
	flexDirection: "column",
	alignItems: "center",
	justifyContent: "center",
	gap: "9px",
	fontFamily: "var(--font-sans)",
	fontSize: "12px",
	color: "var(--text-sub)",
};

const overlayButton: React.CSSProperties = {
	font: "inherit",
	color: "var(--text)",
	background: "var(--bg-panel-alt)",
	border: "0.5px solid var(--border-mid)",
	borderRadius: "var(--radius-control)",
	padding: "5px 12px",
	cursor: "pointer",
};

/** A 22px ring spinner; the top arc is gold (02-UI-SPEC reconnecting overlay). */
function Spinner({ gold }: { gold?: boolean }) {
	return (
		<span
			aria-hidden="true"
			style={{
				width: "22px",
				height: "22px",
				borderRadius: "var(--radius-full)",
				border: "2px solid var(--border-mid)",
				borderTopColor: gold ? "var(--gold)" : "var(--accent-line)",
				animation: "spin 0.8s linear infinite",
			}}
		/>
	);
}

/**
 * A 14px ring spinner for the in-flight Stop/Start header button (UI-07/UI-08).
 * Sized down from the 22px overlay `Spinner` so the 24px icon button does not
 * reflow; track `--border-mid`, top-arc `--accent-line` (never gold).
 */
function HeaderSpinner() {
	return (
		<span
			aria-hidden="true"
			style={{
				width: "14px",
				height: "14px",
				borderRadius: "var(--radius-full)",
				border: "2px solid var(--border-mid)",
				borderTopColor: "var(--accent-line)",
				animation: "spin 0.8s linear infinite",
			}}
		/>
	);
}

/** 05-UI-SPEC Copywriting — the `stopped` placeholder heading + body copy. */
const STOPPED_HEADING = "Workspace stopped";
const STOPPED_BODY =
	"This workspace is stopped. Start it to reconnect the terminal and pick up where you left off.";

export function TerminalPanel({
	id,
	name,
	status,
	branch,
	model,
	onSplit,
	onDetach,
	onTerminate,
	onStop,
	onStart,
	stopPending,
	startPending,
	onTerminalEvent,
}: TerminalPanelProps) {
	const {
		containerRef,
		status: termStatus,
		reconnectAttempts,
		reattach,
		detach,
	} = useTerminal(id, status, { onTerminalEvent });

	// Terminate (×) is confirm-gated + distinct from detach (UI-SPEC criterion 12):
	// the × opens a confirm overlay (dimming the panel) and only `Destroy` removes it.
	const [isConfirmingTerminate, setConfirmingTerminate] = useState(false);

	// The activity drawer's ephemeral target (UI-06): a single non-persisted id,
	// exactly one drawer open at a time. Null = closed (no poll, no render).
	const [activeEventsWorkspaceId, setActiveEventsWorkspaceId] = useState<
		string | null
	>(null);

	return (
		<section
			// Stable per-panel hook (CICD-09): scopes every e2e locator to THIS
			// workspace's panel so a multi-panel layout never leaks a `.first()` /
			// global `[data-testid^="term-"]` assertion across sibling panels.
			data-testid={`panel-${id}`}
			style={{
				display: "flex",
				flexDirection: "column",
				height: "100%",
				background: "var(--bg-surf)",
				border: "0.5px solid var(--border)",
				borderRadius: "var(--radius-panel)",
				overflow: "hidden",
				// Dim the panel while the terminate confirm is pending (UI-SPEC).
				opacity: isConfirmingTerminate ? 0.4 : 1,
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
					aria-label="Activity log"
					style={iconButtonStyle}
					onClick={() => setActiveEventsWorkspaceId(id)}
				>
					<ActivityIcon />
				</button>
				{/* Show-only-applicable lifecycle control (UI-07/UI-08): exactly one of
					Stop (running) / Start (stopped) occupies this slot, left of Split;
					creating/error/destroyed render neither (the UI offers no illegal
					action). Stop fires immediately (reversible, no confirm); both
					disable + aria-busy while their mutation is pending (no double-fire). */}
				{status === "running" ? (
					<button
						type="button"
						aria-label="Stop workspace"
						style={iconButtonStyle}
						disabled={stopPending}
						aria-busy={stopPending || undefined}
						onClick={() => onStop?.(id)}
					>
						{stopPending ? <HeaderSpinner /> : <StopIcon />}
					</button>
				) : status === "stopped" ? (
					<button
						type="button"
						aria-label="Start workspace"
						style={iconButtonStyle}
						disabled={startPending}
						aria-busy={startPending || undefined}
						onClick={() => onStart?.(id)}
					>
						{startPending ? <HeaderSpinner /> : <StartIcon />}
					</button>
				) : null}
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
					onClick={() => {
						// Non-destructive: close the live socket (reconnecting overlay), then
						// let the parent know. The session survives — distinct from terminate.
						detach();
						onDetach?.(id);
					}}
				>
					<PlugIcon />
				</button>
				<button
					type="button"
					aria-label="Terminate"
					style={iconButtonStyle}
					onClick={() => setConfirmingTerminate(true)}
				>
					<CloseIcon />
				</button>
			</header>

			<div
				style={{
					position: "relative",
					flex: 1,
					minHeight: 0,
				}}
			>
				{/* A stopped workspace is a calm resting state — branch the body on
					`status === "stopped"` BEFORE the termStatus overlays so a transient
					termStatus during the running→stopped tear-down can't flash an error
					scrim. The placeholder (role=status, NOT alert) covers the body over a
					calm --bg-surf wash; the Start CTA fires the same start mutation as the
					header button and shares startPending so both disable together. */}
				{status === "stopped" ? (
					<div
						style={{
							...overlayBase,
							inset: 0,
							gap: "var(--space-sm)",
							padding: "var(--space-xl) var(--space-lg)",
							background: "var(--bg-surf)",
						}}
						role="status"
						aria-live="polite"
					>
						<span
							style={{
								fontFamily: "var(--font-display)",
								fontSize: "16px",
								fontWeight: 500,
								color: "var(--text-sub)",
							}}
						>
							{STOPPED_HEADING}
						</span>
						<span
							style={{
								color: "var(--text-muted)",
								maxWidth: "260px",
								textAlign: "center",
								lineHeight: 1.5,
							}}
						>
							{STOPPED_BODY}
						</span>
						<button
							type="button"
							aria-label="Start workspace"
							style={{
								...overlayButton,
								display: "inline-flex",
								alignItems: "center",
								gap: "6px",
							}}
							disabled={startPending}
							aria-busy={startPending || undefined}
							onClick={() => onStart?.(id)}
						>
							{startPending ? <Spinner /> : <StartIcon />}
							Start workspace
						</button>
					</div>
				) : (
					<>
						<div
							ref={containerRef}
							className="term"
							data-testid={`term-${id}`}
							style={{
								position: "absolute",
								inset: 0,
								padding: "11px 13px",
								background: "var(--bg-surf)",
								color: "var(--text-sub)",
								fontFamily: "var(--font-mono)",
								fontSize: "12px",
								lineHeight: 1.6,
								overflowY: "auto",
							}}
						/>

						{termStatus === "connecting" ? (
							<div
								style={{ ...overlayBase, background: "rgba(26,28,26,.45)" }}
								role="status"
								aria-live="polite"
							>
								<Spinner />
								<span>Connecting…</span>
							</div>
						) : null}

						{termStatus === "reconnecting" ? (
							<div
								style={{ ...overlayBase, background: "rgba(26,28,26,.78)" }}
								role="status"
								aria-live="polite"
							>
								<Spinner gold />
								<span>{`reconnecting… attempt ${reconnectAttempts} / 5`}</span>
								<button type="button" style={overlayButton} onClick={reattach}>
									Reattach
								</button>
							</div>
						) : null}

						{termStatus === "error" ? (
							<div
								style={{ ...overlayBase, background: "rgba(26,28,26,.78)" }}
								role="alert"
								aria-live="assertive"
							>
								<span
									aria-hidden="true"
									style={{
										width: "22px",
										height: "22px",
										display: "grid",
										placeItems: "center",
										color: "var(--err)",
										fontSize: "18px",
									}}
								>
									!
								</span>
								<span>{`Session unavailable. ${ERROR_REASON}.`}</span>
								<button type="button" style={overlayButton} onClick={reattach}>
									Retry
								</button>
							</div>
						) : null}

						{isConfirmingTerminate ? (
							<div
								style={{
									...overlayBase,
									background: "rgba(26,28,26,.92)",
									opacity: 1,
								}}
								role="alertdialog"
								aria-label={`Terminate ${name}`}
								aria-live="assertive"
							>
								<span style={{ maxWidth: "260px", textAlign: "center" }}>
									{terminateConfirmCopy(name)}
								</span>
								<div style={{ display: "flex", gap: "8px" }}>
									<button
										type="button"
										style={overlayButton}
										onClick={() => setConfirmingTerminate(false)}
									>
										Cancel
									</button>
									<button
										type="button"
										style={{ ...overlayButton, color: "var(--err)" }}
										onClick={() => {
											setConfirmingTerminate(false);
											onTerminate?.(id);
										}}
									>
										Destroy
									</button>
								</div>
							</div>
						) : null}
					</>
				)}
			</div>

			{/* Per-workspace activity drawer (UI-06); closed when the id is null. */}
			<ActivityDrawer
				workspaceId={activeEventsWorkspaceId}
				workspaceName={name}
				onClose={() => setActiveEventsWorkspaceId(null)}
			/>
		</section>
	);
}
