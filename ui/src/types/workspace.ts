// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// Frontend domain types. Field names are camelCase to match the backend's
// CamelModel JSON (api/models/workspace.py serialized via model_dump(by_alias=True)):
// snake_case columns (lxc_ip, project_repo, …) surface as lxcIp, projectRepo, ….

/** The workspace lifecycle status, 1:1 with the backend `WorkspaceStatus` enum. */
export type WorkspaceStatus =
	| "creating"
	| "running"
	| "stopped"
	| "error"
	| "destroyed";

/** A worker workspace row (mirrors api/models/workspace.py::Workspace). */
export interface Workspace {
	id: string;
	name: string;
	status: WorkspaceStatus;
	vmid: number | null;
	node: string;
	lxcIp: string | null;
	projectRepo: string;
	projectBranch: string;
	pluginSet: string;
	createdAt: string;
	stoppedAt: string | null;
	destroyedAt: string | null;
	deletedAt: string | null;
}

/** Request body for POST /api/v1/workspaces (mirrors WorkspaceCreate). */
export interface WorkspaceCreate {
	name: string;
	projectRepo: string;
	projectBranch?: string;
	pluginSet?: string;
	// Optional, mirroring the backend `node: str | None = None`: null/omitted means
	// "auto-select the least-loaded node"; a node string is an explicit manual pick.
	node?: string | null;
}

/** Per-node capacity from GET /api/v1/nodes (Plan 02-01 backend). */
export interface NodeCapacity {
	node: string;
	memoryUsedFraction: number | null;
	capacityThreshold: number;
	overThreshold: boolean;
}

/** The standard response envelope (mirrors api/lib/envelope.py). */
export interface ApiEnvelope<T> {
	data: T | null;
	meta: { requestId: string; timestamp: string };
	error: { code: string; message: string } | null;
}

/** Terminal connection state surfaced by useTerminal (TERM-06 overlay states). */
export type TerminalState =
	| "connecting"
	| "open"
	| "reconnecting"
	| "error"
	| "closed";
