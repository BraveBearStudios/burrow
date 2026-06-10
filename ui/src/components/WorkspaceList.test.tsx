// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// WorkspaceList tests (UI-01). Renders the live-polled sidebar over the MSW seed
// (one row per status) and proves the binding 02-UI-SPEC sidebar contract: a row
// per non-destroyed workspace, status→color dot mapping (criterion 7), a pulsing
// `creating` dot, a status overline on non-running rows, click → openPanel +
// setActive (sidebar↔panel sync, criterion 8), and the empty + poll-error states.
// MSW serves /api/v1/workspaces; the layoutStore spies catch the click wiring.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
	fireEvent,
	render,
	screen,
	waitFor,
	within,
} from "@testing-library/react";
import { HttpResponse, http } from "msw";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { server } from "../../tests/msw/server";
import { useLayoutStore } from "../store/layoutStore";
import { WorkspaceList } from "./WorkspaceList";

function renderList() {
	// Disable retry so a forced poll error surfaces isError immediately in the
	// test (the production hook keeps TanStack Query's default backoff retries).
	const client = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	const wrapper = ({ children }: { children: ReactNode }) => (
		<QueryClientProvider client={client}>{children}</QueryClientProvider>
	);
	return render(<WorkspaceList />, { wrapper });
}

beforeEach(() => {
	localStorage.clear();
	useLayoutStore.setState({ mosaicNode: null, activeWorkspaceId: null });
});

afterEach(() => {
	vi.restoreAllMocks();
});

describe("WorkspaceList — rows + status mapping (UI-01)", () => {
	it("renders one row per non-destroyed workspace with its name", async () => {
		renderList();
		await waitFor(() => {
			expect(screen.getByText("project-eta")).toBeInTheDocument();
		});
		// The four seeded statuses each surface a row.
		expect(screen.getByText("project-theta")).toBeInTheDocument();
		expect(screen.getByText("project-iota")).toBeInTheDocument();
		expect(screen.getByText("project-kappa")).toBeInTheDocument();
	});

	it("shows `repo · branch` in mono under each row", async () => {
		renderList();
		await waitFor(() =>
			expect(screen.getByText("project-eta")).toBeInTheDocument(),
		);
		// projectRepo · projectBranch (02-UI-SPEC sidebar row second line).
		expect(screen.getByText("github.com/acme/eta · main")).toBeInTheDocument();
	});

	it("maps status → dot color token (criterion 7) and only non-running rows carry an overline", async () => {
		renderList();
		const runningRow = await screen.findByRole("listitem", {
			name: /project-eta/i,
		});
		const creatingRow = await screen.findByRole("listitem", {
			name: /project-theta/i,
		});

		// Status dots carry a data-status so the color token is assertable.
		const runningDot = within(runningRow).getByTestId("status-dot");
		const creatingDot = within(creatingRow).getByTestId("status-dot");
		expect(runningDot).toHaveStyle({ background: "var(--ok)" });
		expect(creatingDot).toHaveStyle({ background: "var(--warn)" });

		// running shows no overline; creating shows the `creating` overline.
		expect(within(runningRow).queryByText("creating")).not.toBeInTheDocument();
		expect(within(creatingRow).getByText("creating")).toBeInTheDocument();
		// error + stopped rows carry their own overlines.
		const errorRow = await screen.findByRole("listitem", {
			name: /project-kappa/i,
		});
		expect(within(errorRow).getByText("error")).toBeInTheDocument();
		const stoppedRow = await screen.findByRole("listitem", {
			name: /project-iota/i,
		});
		expect(within(stoppedRow).getByText("stopped")).toBeInTheDocument();
	});

	it("pulses the `creating` dot (live indication) and not the running dot", async () => {
		renderList();
		const creatingRow = await screen.findByRole("listitem", {
			name: /project-theta/i,
		});
		const runningRow = await screen.findByRole("listitem", {
			name: /project-eta/i,
		});
		const creatingDot = within(creatingRow).getByTestId("status-dot");
		const runningDot = within(runningRow).getByTestId("status-dot");
		expect(creatingDot.style.animationName).toBe("pulse");
		expect(runningDot.style.animationName).toBe("");
	});

	it("filters out destroyed rows", async () => {
		server.use(
			http.get("/api/v1/workspaces", () =>
				HttpResponse.json({
					data: [
						{
							id: "ws-gone",
							name: "project-gone",
							status: "destroyed",
							vmid: null,
							node: "node1",
							lxcIp: null,
							projectRepo: "github.com/acme/gone",
							projectBranch: "main",
							pluginSet: "default",
							createdAt: "2026-06-10T00:00:00Z",
							stoppedAt: null,
							destroyedAt: "2026-06-10T01:00:00Z",
							deletedAt: null,
						},
					],
					meta: { requestId: "t", timestamp: "2026-06-10T00:00:00Z" },
					error: null,
				}),
			),
		);
		renderList();
		await waitFor(() =>
			expect(screen.getByText("No workspaces yet")).toBeInTheDocument(),
		);
		expect(screen.queryByText("project-gone")).not.toBeInTheDocument();
	});
});

describe("WorkspaceList — click sync (criterion 8, UI-01)", () => {
	it("clicking a row opens its panel + marks it active (openPanel + setActive)", async () => {
		const openPanel = vi.spyOn(useLayoutStore.getState(), "openPanel");
		const setActive = vi.spyOn(useLayoutStore.getState(), "setActive");
		renderList();
		const row = await screen.findByRole("listitem", { name: /project-eta/i });
		fireEvent.click(within(row).getByRole("button"));
		expect(openPanel).toHaveBeenCalledWith("ws-running");
		expect(setActive).toHaveBeenCalledWith("ws-running");
	});

	it("marks the active row aria-current bound to layoutStore.activeWorkspaceId", async () => {
		useLayoutStore.setState({ activeWorkspaceId: "ws-running" });
		renderList();
		const row = await screen.findByRole("listitem", { name: /project-eta/i });
		expect(within(row).getByRole("button")).toHaveAttribute(
			"aria-current",
			"true",
		);
	});
});

describe("WorkspaceList — empty + error states (UI-01)", () => {
	it("renders the `No workspaces yet` empty state when the list is empty", async () => {
		server.use(
			http.get("/api/v1/workspaces", () =>
				HttpResponse.json({
					data: [],
					meta: { requestId: "t", timestamp: "2026-06-10T00:00:00Z" },
					error: null,
				}),
			),
		);
		renderList();
		expect(await screen.findByText("No workspaces yet")).toBeInTheDocument();
		expect(
			screen.getByText(/Spin one up with \+ New workspace/),
		).toBeInTheDocument();
	});

	it("shows the poll-error strip when the list query fails", async () => {
		server.use(http.get("/api/v1/workspaces", () => HttpResponse.error()));
		renderList();
		expect(
			await screen.findByText("Couldn't reach the control plane. Retrying…"),
		).toBeInTheDocument();
	});
});
