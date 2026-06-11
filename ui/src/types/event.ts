// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// Frontend event type (UI-06). Field names are camelCase to match the backend's
// CamelModel JSON (api/models/event.py serialized via model_dump(by_alias=True)):
// the snake_case column workspace_id surfaces as workspaceId, created_at as
// createdAt. `data` is the already server-redacted (`_safe()`) payload — the UI
// renders it verbatim and never re-fetches or un-redacts any field.

/** A workspace event-log row (mirrors api/models/event.py::WorkspaceEvent). */
export interface WorkspaceEvent {
	id: string;
	workspaceId: string;
	type: string;
	data: Record<string, unknown>;
	createdAt: string;
}
