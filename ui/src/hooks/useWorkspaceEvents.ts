// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// useWorkspaceEvents is the activity-drawer's data source (UI-06): a ~3s TanStack
// Query poll of GET /api/v1/workspaces/{id}/events, mirroring useWorkspaces. The
// `enabled` gate is load-bearing — the poll runs ONLY while the drawer is open
// (04-UI-SPEC criterion 5: `enabled: drawerOpen && !!id`), so closing the drawer
// stops the network traffic. The endpoint returns events OLDEST-first; the drawer
// reverses client-side for the newest-first contract. The drawer makes only this
// same-origin read — no second request, no un-redact (threat T-04-03A).

import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { WorkspaceEvent } from "../types/event";

/** ~3s poll to match the workspace-list cadence (one live tempo across the app). */
const POLL_INTERVAL_MS = 3000;

/** The query key the drawer's events poll keys on (scoped per workspace id). */
export const WORKSPACE_EVENTS_KEY = "workspace-events";

/**
 * Poll a workspace's event log (UI-06). `enabled` is `drawerOpen` — combined with
 * a non-null `id` it gates the poll so it only runs while the drawer is open.
 */
export function useWorkspaceEvents(id: string | null, enabled: boolean) {
	return useQuery({
		queryKey: [WORKSPACE_EVENTS_KEY, id],
		queryFn: () => api<WorkspaceEvent[]>(`/workspaces/${id}/events`),
		// WR-04: stop polling once the query is in an error state (e.g. the
		// workspace was destroyed and the events endpoint now 404s). A static 3s
		// interval kept hammering a permanently-gone workspace for as long as the
		// drawer stayed open; the function form backs off on error and keeps the
		// live tempo only while the query is healthy.
		refetchInterval: (query) =>
			query.state.status === "error" ? false : POLL_INTERVAL_MS,
		enabled: enabled && !!id,
	});
}
