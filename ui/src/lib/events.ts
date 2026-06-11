// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// The single source of truth for the 04-UI-SPEC "Event type → badge color map"
// (the binding table + criteria 3/4). The activity drawer (ActivityDrawer) reads
// each event's badge token + label from here so the drawer speaks the same color
// language as the sidebar (mirrors the status.ts STATUS_COLOR pattern: tokens
// only, NO hex, NO --gold). The map keys off the REAL namespaced backend strings
// (verified in api/services/workspaceService.py + api/routers/terminal.py), with a
// reaper.* prefix match and an unknown → raw-mono fallback so a new backend event
// never breaks the drawer (forward-compatible, criterion 3).

/** A resolved badge: the CSS color token for the dot/label + the human label. */
export interface EventBadge {
	/** The dot + label color token (e.g. "var(--ok)"). */
	token: string;
	/** The sentence-case human label rendered in the pill. */
	label: string;
	/** True when the raw type string should render in mono (the unknown fallback). */
	mono?: boolean;
}

/**
 * type → badge for the verified namespaced backend strings (binding table). The
 * background is always the neutral --bg-panel-alt (set by the component); only the
 * dot + label token varies. reaper.* + the workspace.stopped reason:idle special
 * case + the unknown fallback are resolved in {@link badgeFor}, not this record.
 */
export const EVENT_BADGE: Record<string, EventBadge> = {
	"workspace.created": { token: "var(--ok)", label: "Created" },
	"workspace.started": { token: "var(--ok)", label: "Started" },
	"workspace.stopped": { token: "var(--text-muted)", label: "Stopped" },
	"workspace.destroyed": { token: "var(--err)", label: "Destroyed" },
	"terminal.connected": {
		token: "var(--accent-line)",
		label: "Terminal connected",
	},
	"terminal.disconnected": {
		token: "var(--text-muted)",
		label: "Terminal disconnected",
	},
	"boot.error": { token: "var(--err)", label: "Boot error" },
	"bootconfig.persisted": {
		token: "var(--text-sub)",
		label: "Boot config persisted",
	},
};

/** Capitalize a reaper suffix into sentence case (e.g. "vmid_freed" → "Vmid freed"). */
function humanizeSuffix(suffix: string): string {
	const spaced = suffix.replace(/_/g, " ").trim();
	if (spaced === "") {
		return "event";
	}
	return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

/**
 * Resolve an event's badge (04-UI-SPEC binding map). Special cases, in order:
 *   1. workspace.stopped with data.reason === "idle" → "Auto-stopped (idle)", --warn
 *   2. a reaper.*-prefixed type → "Reaper · {suffix}", --warn (the new reconciler)
 *   3. a known namespaced type → its EVENT_BADGE entry
 *   4. any other (unknown) type → the raw type string in mono, --text-sub
 */
export function badgeFor(
	type: string,
	data: Record<string, unknown>,
): EventBadge {
	if (type === "workspace.stopped" && data.reason === "idle") {
		return { token: "var(--warn)", label: "Auto-stopped (idle)" };
	}
	if (type.startsWith("reaper.")) {
		return {
			token: "var(--warn)",
			label: `Reaper · ${humanizeSuffix(type.slice("reaper.".length))}`,
		};
	}
	const known = EVENT_BADGE[type];
	if (known) {
		return known;
	}
	// Forward-compatible fallback: a new backend event renders its raw string in
	// mono (criterion 3) — never a crash, never a blank.
	return { token: "var(--text-sub)", label: type, mono: true };
}
