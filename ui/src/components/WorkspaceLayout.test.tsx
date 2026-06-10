// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// WorkspaceLayout tests (UI-02 + UI-05). Renders the react-mosaic grid bound to
// the layoutStore over the MSW-seeded workspace list, with xterm / WebSocket /
// ResizeObserver mocked (jsdom can't lay out a real terminal). Proves: a panel
// renders per persisted leaf, the empty state shows when the tree is null, and
// the restore-after-refresh reconcile drops a leaf whose workspace is absent from
// the live list on load (UI-05) while keeping the running ones.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { installMockWebSocket } from "../../tests/helpers/mockWebSocket";
import { resetXtermMocks } from "../../tests/helpers/mockXterm";
import { installMockResizeObserver } from "../../tests/helpers/resizeObserver";
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
