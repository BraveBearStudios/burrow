// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// useWorkspaces tests (UI-01): the list poll returns the seeded MSW workspaces,
// and a terminal error/close invalidates the list (Pitfall 4 reconciliation).

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { seedWorkspaces } from "../../tests/msw/handlers";
import { useInvalidateWorkspaces, useWorkspaces } from "./useWorkspaces";

function wrapper(client: QueryClient) {
	return ({ children }: { children: ReactNode }) => (
		<QueryClientProvider client={client}>{children}</QueryClientProvider>
	);
}

describe("useWorkspaces (UI-01)", () => {
	it("polls the list and returns the seeded workspaces", async () => {
		const client = new QueryClient();
		const { result } = renderHook(() => useWorkspaces(), {
			wrapper: wrapper(client),
		});

		await waitFor(() => expect(result.current.isSuccess).toBe(true));
		expect(result.current.data?.map((w) => w.id)).toEqual(
			seedWorkspaces.map((w) => w.id),
		);
	});

	it("uses a ~3s refetchInterval so the sidebar reflects status changes", async () => {
		const client = new QueryClient();
		const { result } = renderHook(() => useWorkspaces(), {
			wrapper: wrapper(client),
		});
		await waitFor(() => expect(result.current.isSuccess).toBe(true));
		// The query is configured to poll (refetchInterval set on the observer).
		const observers = client
			.getQueryCache()
			.find({ queryKey: ["workspaces"] })?.observers;
		expect(observers?.[0]?.options.refetchInterval).toBe(3000);
	});

	it("invalidateWorkspaces refetches the list (terminal error/close → fresh poll)", async () => {
		const client = new QueryClient();
		const invalidateSpy = vi.spyOn(client, "invalidateQueries");

		const { result } = renderHook(
			() => ({
				list: useWorkspaces(),
				invalidate: useInvalidateWorkspaces(),
			}),
			{ wrapper: wrapper(client) },
		);

		await waitFor(() => expect(result.current.list.isSuccess).toBe(true));
		result.current.invalidate();
		expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["workspaces"] });
	});
});
