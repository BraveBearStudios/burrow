// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// useWorkspaces is the shared TanStack Query surface for the workspace list
// (UI-01): a ~3s poll plus create/stop/start/destroy mutations. The server is the
// source of truth (status never mirrors into Zustand); every mutation invalidates
// the list so the sidebar/status bar reconcile. A terminal error/close also
// invalidates the list (Pitfall 4: WS events are fresher than the poll) via the
// exported `useInvalidateWorkspaces` helper the TerminalPanel wires to its hook.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Workspace, WorkspaceCreate } from "../types/workspace";

/** The query key the list, mutations, and terminal-event reconciliation share. */
export const WORKSPACES_KEY = ["workspaces"] as const;

/** ~3s poll so the sidebar reflects creating→running transitions promptly. */
const POLL_INTERVAL_MS = 3000;

/** Poll the workspace list (UI-01). */
export function useWorkspaces() {
	return useQuery({
		queryKey: WORKSPACES_KEY,
		queryFn: () => api<Workspace[]>("/workspaces"),
		refetchInterval: POLL_INTERVAL_MS,
	});
}

/** A stable callback that invalidates the list (terminal error/close → refetch). */
export function useInvalidateWorkspaces(): () => void {
	const queryClient = useQueryClient();
	return () => {
		queryClient.invalidateQueries({ queryKey: WORKSPACES_KEY });
	};
}

/** Create a workspace (UI-03) → POST /api/v1/workspaces, then refetch the list. */
export function useCreateWorkspace() {
	const queryClient = useQueryClient();
	return useMutation({
		mutationFn: (body: WorkspaceCreate) =>
			api<Workspace>("/workspaces", {
				method: "POST",
				body: JSON.stringify(body),
			}),
		onSettled: () => {
			queryClient.invalidateQueries({ queryKey: WORKSPACES_KEY });
		},
	});
}

/** Drive a lifecycle transition (stop / start / destroy) for a workspace. */
function useWorkspaceAction(action: "stop" | "start" | "destroy") {
	const queryClient = useQueryClient();
	const method = action === "destroy" ? "DELETE" : "POST";
	const suffix = action === "destroy" ? "" : `/${action}`;
	return useMutation({
		mutationFn: (id: string) =>
			api<Workspace>(`/workspaces/${id}${suffix}`, { method }),
		onSettled: () => {
			queryClient.invalidateQueries({ queryKey: WORKSPACES_KEY });
		},
	});
}

export const useStopWorkspace = () => useWorkspaceAction("stop");
export const useStartWorkspace = () => useWorkspaceAction("start");
export const useDestroyWorkspace = () => useWorkspaceAction("destroy");
