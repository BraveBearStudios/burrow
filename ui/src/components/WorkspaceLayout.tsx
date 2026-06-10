// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// WorkspaceLayout is the react-mosaic terminal grid (UI-02): it binds <Mosaic> to
// the Zustand layoutStore (value=mosaicNode / onChange=setNode) and renders a
// TerminalPanel per leaf. On the first useWorkspaces success it reconciles the
// persisted tree against the live list (UI-05) — gone leaves drop, still-running
// panels remount and their terminals reconnect to the live session. The active
// panel carries a 1px --accent-line ring synced to layoutStore.activeWorkspaceId;
// clicking a panel calls setActive (the sidebar reads/writes the same field in
// Wave 4). Mosaic's Blueprint chrome is suppressed: we pass our own className
// (NOT mosaic-blueprint-theme) and import only the base layout CSS, styling the
// splitters / drop-targets / empty-state with Burrow tokens (see index.css
// `.burrow-mosaic`). <Mosaic> bundles its own react-dnd DndProvider, so we never
// wrap a second one (Pitfall 6: "Cannot have two HTML5 backends").

import { useEffect, useMemo } from "react";
import type { MosaicNode } from "react-mosaic-component";
import { Mosaic } from "react-mosaic-component";
import "react-mosaic-component/react-mosaic-component.css";
import { useWorkspaces } from "../hooks/useWorkspaces";
import { useLayoutStore } from "../store/layoutStore";
import type { Workspace } from "../types/workspace";
import { TerminalPanel } from "./TerminalPanel";

/** 02-UI-SPEC Copywriting: the empty grid state. */
const EMPTY_HEADING = "No open terminals";
const EMPTY_BODY =
	"Pick a workspace from the sidebar, or create one with + New workspace.";

const gridStyle: React.CSSProperties = {
	position: "relative",
	flex: 1,
	minHeight: 0,
	padding: "11px",
	background: "var(--bg)",
};

const emptyStyle: React.CSSProperties = {
	flex: 1,
	display: "flex",
	flexDirection: "column",
	alignItems: "center",
	justifyContent: "center",
	gap: "6px",
	textAlign: "center",
	color: "var(--text-muted)",
	fontFamily: "var(--font-sans)",
};

/** A single leaf's panel, wrapped so a click marks it active (focus ring). */
function LeafPanel({ id, workspace }: { id: string; workspace?: Workspace }) {
	const activeWorkspaceId = useLayoutStore((s) => s.activeWorkspaceId);
	const setActive = useLayoutStore((s) => s.setActive);
	const closePanel = useLayoutStore((s) => s.closePanel);
	const splitPanel = useLayoutStore((s) => s.splitPanel);
	const isActive = activeWorkspaceId === id;

	return (
		// Active sync (UI-02) is driven by focus, not a click handler: clicking into
		// the terminal body / a header button focuses it, bubbling onFocusCapture
		// here → setActive. This keeps the wrapper a non-interactive container
		// (keyboard focus + a11y handled by the real controls inside).
		<div
			onFocusCapture={() => setActive(id)}
			onPointerDownCapture={() => setActive(id)}
			data-active={isActive ? "true" : undefined}
			style={{
				height: "100%",
				// The active panel's 1px --accent-line ring replaces the hairline
				// (02-UI-SPEC UI-02 focus); others render their own panel border.
				outline: isActive ? "1px solid var(--accent-line)" : "none",
				outlineOffset: "-1px",
				borderRadius: "var(--radius-panel)",
			}}
		>
			<TerminalPanel
				id={id}
				name={workspace?.name ?? id}
				status={workspace?.status ?? "running"}
				branch={workspace?.projectBranch}
				onSplit={(panelId) => splitPanel(panelId, "row")}
				onTerminate={(panelId) => closePanel(panelId)}
			/>
		</div>
	);
}

export function WorkspaceLayout() {
	const mosaicNode = useLayoutStore((s) => s.mosaicNode);
	const setNode = useLayoutStore((s) => s.setNode);
	const reconcile = useLayoutStore((s) => s.reconcile);

	const { data: workspaces, isSuccess } = useWorkspaces();

	// Index the live list by id so each leaf resolves its workspace cheaply.
	const byId = useMemo(() => {
		const map = new Map<string, Workspace>();
		for (const w of workspaces ?? []) {
			map.set(w.id, w);
		}
		return map;
	}, [workspaces]);

	// Restore-after-refresh reconcile (UI-05): once the live list arrives, drop
	// persisted leaves whose workspace is gone/destroyed; survivors remount and
	// their terminals reconnect. Re-runs whenever the live id set changes so a
	// destroyed workspace's panel also drops on a later poll.
	useEffect(() => {
		if (!isSuccess) {
			return;
		}
		const liveIds = new Set((workspaces ?? []).map((w) => w.id));
		reconcile(liveIds);
	}, [isSuccess, workspaces, reconcile]);

	if (mosaicNode === null) {
		return (
			<section style={gridStyle} aria-label="Terminal grid">
				<div style={emptyStyle}>
					<p
						style={{
							fontFamily: "var(--font-sans)",
							fontWeight: 500,
							fontSize: "16px",
							color: "var(--text-sub)",
						}}
					>
						{EMPTY_HEADING}
					</p>
					<p style={{ fontSize: "13px", maxWidth: "320px" }}>{EMPTY_BODY}</p>
				</div>
			</section>
		);
	}

	return (
		<section style={gridStyle} aria-label="Terminal grid">
			<Mosaic<string>
				className="burrow-mosaic"
				value={mosaicNode}
				onChange={(node: MosaicNode<string> | null) => setNode(node)}
				renderTile={(id) => <LeafPanel id={id} workspace={byId.get(id)} />}
			/>
		</section>
	);
}
