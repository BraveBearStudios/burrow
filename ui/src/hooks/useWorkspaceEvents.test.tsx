// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// useWorkspaceEvents tests (UI-06). The drawer's ~3s events poll is gated on
// `enabled` (open-only, criterion 5) AND backs off once the query errors (WR-04):
// a destroyed/404'd workspace must not be polled indefinitely while the drawer
// stays open. These tests assert the refetchInterval function returns the live
// 3s tempo while healthy and `false` once the query is in an error state.

import type { Query } from "@tanstack/react-query";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { server } from "../../tests/msw/server";
import type { WorkspaceEvent } from "../types/event";
import { useWorkspaceEvents, WORKSPACE_EVENTS_KEY } from "./useWorkspaceEvents";

function envelope<T>(data: T) {
	return {
		data,
		meta: { requestId: "test-request", timestamp: "2026-06-10T00:00:00Z" },
		error: null,
	};
}

function wrapper(client: QueryClient) {
	return ({ children }: { children: ReactNode }) => (
		<QueryClientProvider client={client}>{children}</QueryClientProvider>
	);
}

/** The resolved refetchInterval option on the live query's first observer. */
function refetchIntervalOption(client: QueryClient) {
	const observers = client
		.getQueryCache()
		.find({ queryKey: [WORKSPACE_EVENTS_KEY, "ws-1"] })?.observers;
	return observers?.[0]?.options.refetchInterval;
}

const seedEvents: WorkspaceEvent[] = [
	{
		id: "ev-1",
		workspaceId: "ws-1",
		type: "workspace.created",
		data: {},
		createdAt: "2026-06-10T00:00:00Z",
	},
];

afterEach(() => {
	vi.restoreAllMocks();
});

describe("useWorkspaceEvents (UI-06)", () => {
	it("polls at the 3s tempo while the query is healthy", async () => {
		server.use(
			http.get("/api/v1/workspaces/:id/events", () =>
				HttpResponse.json(envelope(seedEvents)),
			),
		);
		const client = new QueryClient();
		const { result } = renderHook(() => useWorkspaceEvents("ws-1", true), {
			wrapper: wrapper(client),
		});
		await waitFor(() => expect(result.current.isSuccess).toBe(true));

		const interval = refetchIntervalOption(client);
		expect(typeof interval).toBe("function");
		// A healthy (non-error) query keeps the live 3s tempo.
		const healthy = { state: { status: "success" } } as unknown as Query;
		expect((interval as (q: Query) => number | false)(healthy)).toBe(3000);
	});

	it("stops polling (refetchInterval false) once the query errors (WR-04)", async () => {
		// The workspace 404'd / is destroyed: the events endpoint errors.
		server.use(
			http.get("/api/v1/workspaces/:id/events", () => HttpResponse.error()),
		);
		const client = new QueryClient({
			defaultOptions: { queries: { retry: false } },
		});
		const { result } = renderHook(() => useWorkspaceEvents("ws-1", true), {
			wrapper: wrapper(client),
		});
		await waitFor(() => expect(result.current.isError).toBe(true));

		const interval = refetchIntervalOption(client);
		expect(typeof interval).toBe("function");
		// The function form backs off: an errored query polls no more.
		const errored = { state: { status: "error" } } as unknown as Query;
		expect((interval as (q: Query) => number | false)(errored)).toBe(false);
	});

	it("does not run while closed (enabled false → no poll)", async () => {
		const hit = vi.fn();
		server.use(
			http.get("/api/v1/workspaces/:id/events", () => {
				hit();
				return HttpResponse.json(envelope(seedEvents));
			}),
		);
		const client = new QueryClient();
		renderHook(() => useWorkspaceEvents("ws-1", false), {
			wrapper: wrapper(client),
		});
		await new Promise((r) => setTimeout(r, 30));
		expect(hit).not.toHaveBeenCalled();
	});
});
