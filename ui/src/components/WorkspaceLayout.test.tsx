// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// WorkspaceLayout tests (UI-02 + UI-05). Renders the react-mosaic grid bound to
// the layoutStore over the MSW-seeded workspace list, with xterm / WebSocket /
// ResizeObserver mocked (jsdom can't lay out a real terminal). Proves: a panel
// renders per persisted leaf, the empty state shows when the tree is null, and
// the restore-after-refresh reconcile drops a leaf whose workspace is absent from
// the live list on load (UI-05) while keeping the running ones.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { installMockWebSocket } from "../../tests/helpers/mockWebSocket";
import { resetXtermMocks } from "../../tests/helpers/mockXterm";
import { installMockResizeObserver } from "../../tests/helpers/resizeObserver";
import { server } from "../../tests/msw/server";
import { useLayoutStore } from "../store/layoutStore";
import { WorkspaceLayout } from "./WorkspaceLayout";

// The terminal stack needs real layout; mock it so the panels mount cleanly.
vi.mock("@xterm/xterm", () => import("../../tests/helpers/mockXterm"));
vi.mock("@xterm/addon-fit", () => import("../../tests/helpers/mockXterm"));
vi.mock("@xterm/xterm/css/xterm.css", () => ({}));

function renderLayout() {
	const client = new QueryClient();
	const wrapper = ({ children }: { children: ReactNode }) => (
		<QueryClientProvider client={client}>{children}</QueryClientProvider>
	);
	return render(<WorkspaceLayout />, { wrapper });
}

/** Reset the persisted layout + terminal/WS mocks before each case. */
beforeEach(() => {
	localStorage.clear();
	useLayoutStore.setState({ mosaicNode: null, activeWorkspaceId: null });
	installMockWebSocket();
	installMockResizeObserver();
	resetXtermMocks();
});

afterEach(() => {
	vi.restoreAllMocks();
});

describe("WorkspaceLayout — empty state (UI-02)", () => {
	it("renders the `No open terminals` empty state when the tree is null", () => {
		renderLayout();
		expect(screen.getByText("No open terminals")).toBeInTheDocument();
		expect(
			screen.getByText(/Pick a workspace from the sidebar/),
		).toBeInTheDocument();
	});
});

describe("WorkspaceLayout — renders a panel per leaf (UI-02)", () => {
	it("mounts a TerminalPanel for each live leaf in the persisted tree", async () => {
		// Two distinct live workspaces from the MSW seed split side-by-side
		// (Mosaic forbids duplicate leaf ids).
		useLayoutStore.setState({
			mosaicNode: {
				direction: "row",
				first: "ws-running",
				second: "ws-stopped",
			},
			activeWorkspaceId: "ws-running",
		});
		renderLayout();
		// Each leaf resolves its workspace name into the panel header.
		await waitFor(() => {
			expect(screen.getByText("project-eta")).toBeInTheDocument();
			expect(screen.getByText("project-iota")).toBeInTheDocument();
		});
	});
});

describe("WorkspaceLayout — terminate destroys the workspace (WS-08 / UI-05)", () => {
	it("Destroy issues DELETE /api/v1/workspaces/{id} and prunes the panel", async () => {
		// A single open panel for a live, running workspace from the MSW seed.
		useLayoutStore.setState({
			mosaicNode: "ws-running",
			activeWorkspaceId: "ws-running",
		});

		// Spy the DELETE: record the destroyed id so we can assert the backend call
		// actually fired (the regression was a client-only closePanel that NEVER hit
		// the API). This test bites if onTerminate is reverted to closePanel-only.
		let destroyedId: string | null = null;
		server.use(
			http.delete("/api/v1/workspaces/:id", ({ params }) => {
				destroyedId = params.id as string;
				return HttpResponse.json({
					data: {
						id: params.id,
						name: "project-eta",
						status: "destroyed",
						vmid: 101,
						node: "node1",
						lxcIp: null,
						projectRepo: "github.com/acme/eta",
						projectBranch: "main",
						pluginSet: "default",
						createdAt: "2026-06-10T00:00:00Z",
						stoppedAt: null,
						destroyedAt: "2026-06-10T03:00:00Z",
						deletedAt: null,
					},
					meta: {
						requestId: "test-request",
						timestamp: "2026-06-10T03:00:00Z",
					},
					error: null,
				});
			}),
		);

		renderLayout();
		// The panel mounts for the live leaf.
		await waitFor(() => {
			expect(screen.getByText("project-eta")).toBeInTheDocument();
		});

		// Confirm-gated terminate: × opens the confirm, Destroy fires onTerminate.
		fireEvent.click(screen.getByRole("button", { name: "Terminate" }));
		fireEvent.click(screen.getByRole("button", { name: "Destroy" }));

		// The DELETE actually reached the backend (NOT a client-only panel close).
		await waitFor(() => {
			expect(destroyedId).toBe("ws-running");
		});

		// The mosaic leaf is pruned optimistically (last leaf → empty grid).
		await waitFor(() => {
			expect(useLayoutStore.getState().mosaicNode).toBeNull();
		});
	});
});

describe("WorkspaceLayout — stop/start mutation wiring (UI-07 / UI-08)", () => {
	// FAILING-FIRST (Wave 0): these reference the `Stop workspace` / `Start
	// workspace` controls Plan 02 adds to TerminalPanel. They are RED until then —
	// the expected Wave 0 state. The MSW stop/start handlers (Wave 0, this plan)
	// resolve the mutation so the test fails on the missing button, NOT on an
	// onUnhandledRequest error.
	it("Stop issues POST /api/v1/workspaces/{id}/stop and keeps the panel mounted", async () => {
		// A single open panel for a live, running workspace from the MSW seed.
		useLayoutStore.setState({
			mosaicNode: "ws-running",
			activeWorkspaceId: "ws-running",
		});

		// Spy the POST /stop: record the id so we can assert the mutation actually
		// reached the backend (mirrors the `Destroy issues DELETE` spy). Unlike
		// terminate, stop must NOT prune the panel — the poll reconciles the status.
		let stoppedId: string | null = null;
		server.use(
			http.post("/api/v1/workspaces/:id/stop", ({ params }) => {
				stoppedId = params.id as string;
				return HttpResponse.json({
					data: {
						id: params.id,
						name: "project-eta",
						status: "stopped",
						vmid: 101,
						node: "node1",
						lxcIp: "10.99.0.101",
						projectRepo: "github.com/acme/eta",
						projectBranch: "main",
						pluginSet: "default",
						createdAt: "2026-06-10T00:00:00Z",
						stoppedAt: "2026-06-10T04:00:00Z",
						destroyedAt: null,
						deletedAt: null,
					},
					meta: {
						requestId: "test-request",
						timestamp: "2026-06-10T04:00:00Z",
					},
					error: null,
				});
			}),
		);

		renderLayout();
		await waitFor(() => {
			expect(screen.getByText("project-eta")).toBeInTheDocument();
		});

		// Stop fires immediately (no confirm) — distinct from terminate.
		fireEvent.click(screen.getByRole("button", { name: "Stop workspace" }));

		// The POST actually reached the backend with the right id.
		await waitFor(() => {
			expect(stoppedId).toBe("ws-running");
		});

		// The panel stays mounted (NOT pruned like terminate); the poll drives the
		// header Stop↔Start swap and the placeholder body.
		expect(screen.getByText("project-eta")).toBeInTheDocument();
		expect(useLayoutStore.getState().mosaicNode).toBe("ws-running");
	});

	it("Start issues POST /api/v1/workspaces/{id}/start and keeps the panel mounted", async () => {
		// A single open panel for a live, stopped workspace from the MSW seed.
		useLayoutStore.setState({
			mosaicNode: "ws-stopped",
			activeWorkspaceId: "ws-stopped",
		});

		let startedId: string | null = null;
		server.use(
			http.post("/api/v1/workspaces/:id/start", ({ params }) => {
				startedId = params.id as string;
				return HttpResponse.json({
					data: {
						id: params.id,
						name: "project-iota",
						status: "running",
						vmid: 103,
						node: "node2",
						lxcIp: "10.99.0.103",
						projectRepo: "github.com/acme/iota",
						projectBranch: "main",
						pluginSet: "default",
						createdAt: "2026-06-10T00:02:00Z",
						stoppedAt: null,
						destroyedAt: null,
						deletedAt: null,
					},
					meta: {
						requestId: "test-request",
						timestamp: "2026-06-10T05:00:00Z",
					},
					error: null,
				});
			}),
		);

		renderLayout();
		await waitFor(() => {
			expect(screen.getByText("project-iota")).toBeInTheDocument();
		});

		// A stopped panel renders two Start affordances (header button + placeholder
		// CTA, both "Start workspace"); click the first — getByRole throws on 2.
		fireEvent.click(
			screen.getAllByRole("button", { name: "Start workspace" })[0],
		);

		await waitFor(() => {
			expect(startedId).toBe("ws-stopped");
		});

		expect(screen.getByText("project-iota")).toBeInTheDocument();
		expect(useLayoutStore.getState().mosaicNode).toBe("ws-stopped");
	});
});

describe("WorkspaceLayout — restore-after-refresh reconcile (UI-05)", () => {
	it("drops a persisted leaf whose workspace is absent from the live list", async () => {
		// A persisted tree referencing a running ws + a ghost id not in the seed.
		useLayoutStore.setState({
			mosaicNode: {
				direction: "row",
				first: "ws-running",
				second: "ws-ghost",
			},
			activeWorkspaceId: "ws-ghost",
		});
		renderLayout();

		// After the first useWorkspaces success, reconcile drops the ghost leaf;
		// only the live running leaf remains.
		await waitFor(() => {
			const { mosaicNode } = useLayoutStore.getState();
			expect(mosaicNode).toBe("ws-running");
		});
		// The active id retargets off the gone workspace to the survivor.
		expect(useLayoutStore.getState().activeWorkspaceId).toBe("ws-running");
	});

	it("clears the tree to the empty state when no persisted leaf is live", async () => {
		useLayoutStore.setState({
			mosaicNode: { direction: "row", first: "ghost-1", second: "ghost-2" },
			activeWorkspaceId: "ghost-1",
		});
		renderLayout();

		await waitFor(() =>
			expect(useLayoutStore.getState().mosaicNode).toBeNull(),
		);
		expect(await screen.findByText("No open terminals")).toBeInTheDocument();
	});
});
