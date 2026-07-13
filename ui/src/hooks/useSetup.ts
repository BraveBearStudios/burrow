// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// useSetup is the TanStack Query surface the first-run gate (App.tsx) + the setup
// wizard consume (SETUP-04/05). useSetupState reads the gate signal (a timestamp);
// the three mutations drive the wizard steps. The Proxmox token passed to
// useTestConnection is a TRANSIENT mutation argument ONLY — it is never written to
// the query cache, Zustand, or localStorage, and never logged (T-13-04/T-13-05).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, api } from "../api/client";
import { useAdminStore } from "../store/useAdminStore";
import type {
	AdminSecretBody,
	AuditList,
	ConnectionResult,
	CredentialStatus,
	SaveCredentialsBody,
	SetupState,
	TemplateResult,
	TestConnectionBody,
	VerifyTemplateBody,
} from "../types/setup";

/** The query key the gate reads and useCompleteSetup invalidates. */
export const SETUP_STATE_KEY = ["setupState"] as const;

/** Query keys for the admin-gated credential surface (invalidated after a save). */
export const CREDENTIAL_STATUS_KEY = ["credentialStatus"] as const;
export const AUDIT_KEY = ["audit"] as const;

/** The stable admin-gate rejection code (api/lib/errors.py AdminAuthError → 401). */
export const ADMIN_AUTH_CODE = "admin_unauthorized";

/** The admin-secret request header the credential surface gates on (ADR-0015). */
const ADMIN_HEADER = "X-Burrow-Admin";

/**
 * On an admin-gate rejection (401 `admin_unauthorized`) drop the in-memory secret
 * so the UI re-prompts; always rethrow so the caller/query still sees the error.
 * Return type `never`: it never returns normally, so a caller's `try { return … }
 * catch { handleAdminError(err) }` still type-checks as returning the happy value.
 */
function handleAdminError(error: unknown): never {
	if (error instanceof ApiError && error.code === ADMIN_AUTH_CODE) {
		useAdminStore.getState().clear();
	}
	throw error;
}

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

// ── Credential store hooks (ADR-0015 / CRED-02..05) ────────────────────────

/**
 * Set (or change) the admin secret. First-run in the wizard is UNAUTHENTICATED by
 * design (no admin header) — the backend allows the first set under the LAN-only
 * trust boundary. The secret is a transient argument; the caller stores it in the
 * in-memory useAdminStore only on success.
 */
export function useSetAdminSecret() {
	return useMutation({
		mutationFn: (body: AdminSecretBody) =>
			api<{ adminSecretSet: boolean }>("/setup/admin-secret", {
				method: "POST",
				body: JSON.stringify(body),
			}),
	});
}

/**
 * Save/rotate the Proxmox token and/or GitHub PAT (admin-gated). The admin secret
 * is read from the store at call time and sent as the `X-Burrow-Admin` header via
 * the client's RequestInit passthrough (the api() client itself stays uncoupled).
 * A save writes audit rows and may change status, so both queries are invalidated.
 */
export function useSaveCredentials() {
	const queryClient = useQueryClient();
	return useMutation({
		mutationFn: async (body: SaveCredentialsBody) => {
			const secret = useAdminStore.getState().secret;
			try {
				return await api<CredentialStatus>("/setup/credentials", {
					method: "POST",
					body: JSON.stringify(body),
					headers: { [ADMIN_HEADER]: secret ?? "" },
				});
			} catch (error) {
				handleAdminError(error);
			}
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: CREDENTIAL_STATUS_KEY });
			queryClient.invalidateQueries({ queryKey: AUDIT_KEY });
		},
	});
}

/**
 * Read credential status (set + last4 + updatedAt), admin-gated. Enabled ONLY when
 * a secret is present, so no request fires before the operator unlocks; retry is
 * off because a 401 will not succeed on retry (it just delays the re-prompt).
 */
export function useCredentialStatus() {
	const secret = useAdminStore((state) => state.secret);
	return useQuery({
		queryKey: CREDENTIAL_STATUS_KEY,
		enabled: secret != null,
		retry: false,
		queryFn: async () => {
			try {
				return await api<CredentialStatus>("/setup/credentials", {
					headers: { [ADMIN_HEADER]: secret ?? "" },
				});
			} catch (error) {
				handleAdminError(error);
			}
		},
	});
}

/** Read the credential audit trail (newest-first), admin-gated. Same gate/retry
 *  discipline as useCredentialStatus. */
export function useAudit() {
	const secret = useAdminStore((state) => state.secret);
	return useQuery({
		queryKey: AUDIT_KEY,
		enabled: secret != null,
		retry: false,
		queryFn: async () => {
			try {
				return await api<AuditList>("/setup/audit", {
					headers: { [ADMIN_HEADER]: secret ?? "" },
				});
			} catch (error) {
				handleAdminError(error);
			}
		},
	});
}
