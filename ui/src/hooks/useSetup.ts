// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// useSetup is the TanStack Query surface the first-run gate (App.tsx) + the setup
// wizard consume (SETUP-04/05). useSetupState reads the gate signal (a timestamp);
// the three mutations drive the wizard steps. The Proxmox token passed to
// useTestConnection is a TRANSIENT mutation argument ONLY — it is never written to
// the query cache, Zustand, or localStorage, and never logged (T-13-04/T-13-05).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type {
	ConnectionResult,
	SetupState,
	TemplateResult,
	TestConnectionBody,
	VerifyTemplateBody,
} from "../types/setup";

/** The query key the gate reads and useCompleteSetup invalidates. */
export const SETUP_STATE_KEY = ["setupState"] as const;

/** Read the first-run gate signal (read on mount + invalidated, NOT polled). */
export function useSetupState() {
	return useQuery({
		queryKey: SETUP_STATE_KEY,
		queryFn: () => api<SetupState>("/setup/state"),
	});
}

/** Step 1 — validate the operator-typed Proxmox token in memory (never stored). */
export function useTestConnection() {
	return useMutation({
		mutationFn: (body: TestConnectionBody) =>
			api<ConnectionResult>("/setup/test-connection", {
				method: "POST",
				body: JSON.stringify(body),
			}),
	});
}

/** Step 2 — verify the worker template exists + is usable on the target node. */
export function useVerifyTemplate() {
	return useMutation({
		mutationFn: (body: VerifyTemplateBody) =>
			api<TemplateResult>("/setup/verify-template", {
				method: "POST",
				body: JSON.stringify(body),
			}),
	});
}

/** Step 4 — mark setup complete, then invalidate ["setupState"] so the gate flips off. */
export function useCompleteSetup() {
	const queryClient = useQueryClient();
	return useMutation({
		mutationFn: () => api<SetupState>("/setup/complete", { method: "POST" }),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: SETUP_STATE_KEY });
		},
	});
}
