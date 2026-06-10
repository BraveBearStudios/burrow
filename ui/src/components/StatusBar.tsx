// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// StatusBar is the fixed 32px bottom bar (UI-04, 02-UI-SPEC "Status bar"). Left
// group: running / stopped / error counts derived from the live workspace list
// (useWorkspaces) — gold mono numbers, status-colored dots, each paired with a
// text label so status is never color-only (a11y). Right group: a client-side
// session-uptime timer (wall-clock since mount, formatted `Xh Ym`, gold mono) and
// the highest node memory usage from useNodes (gold mono %). Loading shows `—`;
// zero workspaces still renders 0s; a poll error holds the last counts. The bar is
// a hard 32px that never grows (chrome invariant, criterion 15). Tokens-only (no
// hex); gold is reserved for the stats; weight ≤500.

import { useEffect, useState } from "react";
import { useNodes } from "../hooks/useNodes";
import { useWorkspaces } from "../hooks/useWorkspaces";
import { STATUS_COLOR } from "../lib/status";
import type { WorkspaceStatus } from "../types/workspace";

/** Tick the uptime once a minute is enough; tick every 30s for responsiveness. */
const UPTIME_TICK_MS = 30_000;

/** Format elapsed milliseconds as `Xh Ym` (02-UI-SPEC session uptime). */
function formatUptime(ms: number): string {
	const totalMinutes = Math.floor(ms / 60_000);
	const hours = Math.floor(totalMinutes / 60);
	const minutes = totalMinutes % 60;
	return `${hours}h ${minutes}m`;
}

const barStyle: React.CSSProperties = {
	display: "flex",
	alignItems: "center",
	gap: "var(--space-md)",
	height: "var(--h-statusbar)",
	flex: "0 0 var(--h-statusbar)",
	padding: "0 var(--space-md)",
	background: "var(--bg-surf)",
	borderTop: "0.5px solid var(--border)",
	fontFamily: "var(--font-sans)",
	fontSize: "11.5px",
	color: "var(--text-sub)",
	overflow: "hidden",
};

const goldMono: React.CSSProperties = {
	fontFamily: "var(--font-mono)",
	color: "var(--gold)",
};

/** One count chip: a status dot + gold mono number + a text label. */
function CountChip({
	status,
	label,
	count,
	testId,
}: {
	status: WorkspaceStatus;
	label: string;
	count: number | null;
	testId: string;
}) {
	return (
		<span
			data-testid={testId}
			style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}
		>
			<span
				aria-hidden="true"
				style={{
					width: "var(--sz-status-dot)",
					height: "var(--sz-status-dot)",
					borderRadius: "var(--radius-full)",
					background: STATUS_COLOR[status],
				}}
			/>
			<span style={goldMono}>{count === null ? "—" : count}</span>
			<span>{label}</span>
		</span>
	);
}

export function StatusBar() {
	const { data: workspaces, isLoading } = useWorkspaces();
	const { data: nodes } = useNodes();

	// Session uptime = wall-clock since mount (client timer, 02-UI-SPEC).
	const [mountedAt] = useState(() => Date.now());
	const [now, setNow] = useState(() => Date.now());
	useEffect(() => {
		const id = setInterval(() => setNow(Date.now()), UPTIME_TICK_MS);
		return () => clearInterval(id);
	}, []);

	// Counts derived from the live list (loading → null → renders `—`).
	const counts = (() => {
		if (isLoading || !workspaces) {
			return { running: null, stopped: null, error: null };
		}
		let running = 0;
		let stopped = 0;
		let error = 0;
		for (const w of workspaces) {
			if (w.status === "running") running += 1;
			else if (w.status === "stopped") stopped += 1;
			else if (w.status === "error") error += 1;
		}
		return { running, stopped, error };
	})();

	// Highest node memory usage (real fraction → %), 02-UI-SPEC capacity readout.
	const peakMem = (() => {
		const fractions = (nodes ?? [])
			.map((n) => n.memoryUsedFraction)
			.filter((f): f is number => f !== null);
		if (fractions.length === 0) {
			return null;
		}
		return Math.round(Math.max(...fractions) * 100);
	})();

	return (
		<footer style={barStyle}>
			<span style={{ display: "flex", alignItems: "center", gap: "18px" }}>
				<CountChip
					status="running"
					label="running"
					count={counts.running}
					testId="count-running"
				/>
				<CountChip
					status="stopped"
					label="stopped"
					count={counts.stopped}
					testId="count-stopped"
				/>
				<CountChip
					status="error"
					label="error"
					count={counts.error}
					testId="count-error"
				/>
			</span>

			<span style={{ flex: 1 }} />

			{peakMem !== null ? (
				<span
					data-testid="capacity"
					style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}
				>
					<span>peak mem</span>
					<span style={goldMono}>{`${peakMem}%`}</span>
				</span>
			) : null}

			<span
				data-testid="uptime"
				style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}
			>
				<span>session uptime</span>
				<span style={goldMono}>{formatUptime(now - mountedAt)}</span>
			</span>
		</footer>
	);
}
