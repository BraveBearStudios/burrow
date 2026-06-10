// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// The single source of truth for the 02-UI-SPEC status→color contract (the
// binding "Status colors" map + criterion 7). Both the sidebar (WorkspaceList)
// dots/overlines and the status-bar (StatusBar) count dots read from here so the
// color discipline (status dots use --ok/--warn/--err/--text-muted, NEVER gold)
// stays consistent across surfaces. `destroyed` maps to a muted token for safety
// but those rows are filtered out of the list, never shown.

import type { WorkspaceStatus } from "../types/workspace";

/** status → the CSS color token for its dot / overline / count (criterion 7). */
export const STATUS_COLOR: Record<WorkspaceStatus, string> = {
	running: "var(--ok)",
	creating: "var(--warn)",
	error: "var(--err)",
	stopped: "var(--text-muted)",
	destroyed: "var(--text-muted)",
};

/** True when a row should be visible (destroyed rows drop out of the list). */
export function isVisibleStatus(status: WorkspaceStatus): boolean {
	return status !== "destroyed";
}
