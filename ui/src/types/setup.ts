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

// ── Credential store (ADR-0015 / CRED-02..05) ──────────────────────────────
// camelCase to match the backend CamelModel JSON (api/routers/setup.py). The
// secret values in these bodies are TRANSIENT — held in React form state / the
// in-memory useAdminStore only, never persisted or logged client-side.

/** POST /setup/admin-secret body. `currentSecret` is required only to CHANGE an
 *  already-set secret; first-run (wizard) omits it. */
export interface AdminSecretBody {
	secret: string;
	currentSecret?: string;
}

/** POST /setup/credentials body. At least one field must be present (the backend
 *  422s an empty write); a Proxmox token is validated read-only before persist. */
export interface SaveCredentialsBody {
	proxmoxTokenValue?: string;
	gitToken?: string;
}

/** GET/POST /setup/credentials status — mirrors the backend getCredentialStatus
 *  keys EXACTLY (api/db/sqliteProvider.py). Write-only store: a secret VALUE is
 *  never returned, only whether it is set + its last 4 chars + the change time. */
export interface CredentialStatus {
	proxmoxTokenSet: boolean;
	proxmoxTokenLast4: string | null;
	gitTokenSet: boolean;
	gitTokenLast4: string | null;
	updatedAt: string | null;
}

/** One row of the credential audit trail (audit_log columns, CRED-05). `target`,
 *  `sourceIp`, and `detail` are nullable per the schema. */
export interface AuditEntry {
	id: string;
	action: string;
	target: string | null;
	outcome: string;
	sourceIp: string | null;
	detail: string | null;
	createdAt: string;
}

/** GET /setup/audit result — recent audit rows, newest-first (bounded). */
export interface AuditList {
	entries: AuditEntry[];
}
