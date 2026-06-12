// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// MSW (v2) request handlers for the /api/v1 surface used by Tier-2 UI tests.
// Every response is wrapped in the standard {data, meta, error} envelope with
// camelCase fields, matching the backend CamelModel JSON the client unwraps.

import { HttpResponse, http } from "msw";
import type {
	NodeCapacity,
	Workspace,
	WorkspaceCreate,
	WorkspaceStatus,
} from "../../src/types/workspace";

function envelope<T>(data: T): {
	data: T;
	meta: { requestId: string; timestamp: string };
	error: null;
} {
	return {
		data,
		meta: { requestId: "test-request", timestamp: "2026-06-10T00:00:00Z" },
		error: null,
	};
}

/** A small seed list spanning every status the sidebar must render. */
export const seedWorkspaces: Workspace[] = [
	{
		id: "ws-running",
		name: "project-eta",
		status: "running",
		vmid: 101,
		node: "node1",
		lxcIp: "10.99.0.101",
		projectRepo: "github.com/acme/eta",
		projectBranch: "main",
		pluginSet: "default",
		createdAt: "2026-06-10T00:00:00Z",
		stoppedAt: null,
		destroyedAt: null,
		deletedAt: null,
	},
	{
		id: "ws-creating",
		name: "project-theta",
		status: "creating",
		vmid: 102,
		node: "node1",
		lxcIp: null,
		projectRepo: "github.com/acme/theta",
		projectBranch: "feat/setup",
		pluginSet: "default",
		createdAt: "2026-06-10T00:01:00Z",
		stoppedAt: null,
		destroyedAt: null,
		deletedAt: null,
	},
	{
		id: "ws-stopped",
		name: "project-iota",
		status: "stopped",
		vmid: 103,
		node: "node2",
		lxcIp: "10.99.0.103",
		projectRepo: "github.com/acme/iota",
		projectBranch: "main",
		pluginSet: "default",
		createdAt: "2026-06-10T00:02:00Z",
		stoppedAt: "2026-06-10T01:00:00Z",
		destroyedAt: null,
		deletedAt: null,
	},
	{
		id: "ws-error",
		name: "project-kappa",
		status: "error",
		vmid: null,
		node: "node2",
		lxcIp: null,
		projectRepo: "github.com/acme/kappa",
		projectBranch: "main",
		pluginSet: "default",
		createdAt: "2026-06-10T00:03:00Z",
		stoppedAt: null,
		destroyedAt: null,
		deletedAt: null,
	},
];

export const seedNodes: NodeCapacity[] = [
	{
		node: "node1",
		memoryUsedFraction: 0.42,
		capacityThreshold: 0.8,
		overThreshold: false,
	},
	{
		node: "node2",
		memoryUsedFraction: 0.71,
		capacityThreshold: 0.8,
		overThreshold: false,
	},
];

export const handlers = [
	// GET /api/v1/workspaces — list, optionally filtered by ?status=
	http.get("/api/v1/workspaces", ({ request }) => {
		const status = new URL(request.url).searchParams.get(
			"status",
		) as WorkspaceStatus | null;
		const list = status
			? seedWorkspaces.filter((w) => w.status === status)
			: seedWorkspaces;
		return HttpResponse.json(envelope(list));
	}),

	// GET /api/v1/workspaces/:id — single workspace
	http.get("/api/v1/workspaces/:id", ({ params }) => {
		const found = seedWorkspaces.find((w) => w.id === params.id);
		if (!found) {
			return HttpResponse.json(
				{
					data: null,
					meta: {
						requestId: "test-request",
						timestamp: "2026-06-10T00:00:00Z",
					},
					error: { code: "not_found", message: "Not found." },
				},
				{ status: 404 },
			);
		}
		return HttpResponse.json(envelope(found));
	}),

	// POST /api/v1/workspaces — synchronous create returns a running workspace (v1 saga)
	http.post("/api/v1/workspaces", async ({ request }) => {
		const body = (await request.json()) as WorkspaceCreate;
		const created: Workspace = {
			id: "ws-created",
			name: body.name,
			status: "running",
			vmid: 110,
			node: body.node,
			lxcIp: "10.99.0.110",
			projectRepo: body.projectRepo,
			projectBranch: body.projectBranch ?? "main",
			pluginSet: body.pluginSet ?? "default",
			createdAt: "2026-06-10T02:00:00Z",
			stoppedAt: null,
			destroyedAt: null,
			deletedAt: null,
		};
		return HttpResponse.json(envelope(created), { status: 201 });
	}),

	// DELETE /api/v1/workspaces/:id — destroy (stop+destroy CT, soft-delete row).
	// Mirrors the backend: the destroyed workspace returns with status `destroyed`,
	// dropping out of the live list the sidebar/grid render (WS-08 / UI-05).
	http.delete("/api/v1/workspaces/:id", ({ params }) => {
		const found = seedWorkspaces.find((w) => w.id === params.id);
		if (!found) {
			return HttpResponse.json(
				{
					data: null,
					meta: {
						requestId: "test-request",
						timestamp: "2026-06-10T00:00:00Z",
					},
					error: { code: "not_found", message: "Not found." },
				},
				{ status: 404 },
			);
		}
		return HttpResponse.json(
			envelope({
				...found,
				status: "destroyed" as WorkspaceStatus,
				destroyedAt: "2026-06-10T03:00:00Z",
			}),
		);
	}),

	// GET /api/v1/nodes — per-node capacity (Plan 02-01 backend; UI-04)
	http.get("/api/v1/nodes", () => HttpResponse.json(envelope(seedNodes))),
];
