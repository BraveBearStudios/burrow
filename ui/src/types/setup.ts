// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// Setup-wizard domain types. Field names are camelCase to match the backend's
// CamelModel JSON (api/routers/setup.py serialized via model_dump(by_alias=True)).
// The Proxmox token in TestConnectionBody is a TRANSIENT argument only — it is
// validated in memory and never persisted/logged client-side (T-13-04/T-13-05).

/** GET /setup/state — the first-run gate's only persisted signal (a timestamp). */
export interface SetupState {
	setupCompletedAt: string | null;
}

/** POST /setup/test-connection result. success=false (200) is the under-privileged
 *  SUCCESS path: the token is valid but missing privileges, NOT an error. */
export interface ConnectionResult {
	success: boolean;
	missingPrivileges: string[];
}

/** POST /setup/verify-template result. exists=true/usable=false (200) is the
 *  "VMID exists but is not a template" path, NOT an error. */
export interface TemplateResult {
	exists: boolean;
	usable: boolean;
	vmid: number;
	node: string;
}

/** POST /setup/test-connection body. `tokenValue` is the transient Proxmox token —
 *  never written to Zustand/localStorage/query cache (T-13-04). */
export interface TestConnectionBody {
	host: string;
	user: string;
	tokenName: string;
	tokenValue: string;
}

/** POST /setup/verify-template body. */
export interface VerifyTemplateBody {
	templateVmid: number;
	node: string;
}
