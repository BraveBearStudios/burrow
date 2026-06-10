// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// UI-05 restore-after-refresh integration test (vitest + MSW + the mock WebSocket).
//
// Simulates a hard refresh: localStorage already holds a persisted Mosaic tree from a
// prior session (one leaf for a workspace that is STILL running, one for a workspace
// that is GONE from the live list). On a fresh App mount the test proves the two
// load-bearing UI-05 behaviors that are easy to regress:
//
//   1. RECONCILE (UI-02/UI-05): once the live useWorkspaces list arrives, the leaf
//      whose id is absent from the server list is dropped from the persisted tree, the
//      tree rebalances to the survivor, and the active id retargets off the gone id.
//   2. LIVE RECONNECT (UI-05): the still-running workspace's panel re-mounts and opens
//      a FRESH WebSocket to /ws/workspaces/{id}/terminal — it reconnects to the live PTY
//      rather than replaying a saved transcript. There is NO scrollback restore in v1
//      (Pitfall 1/7): the terminal writes nothing until a live OUTPUT frame arrives, and
//      the persisted state carries no replay buffer (only the tree + active id).
//
// xterm / WebSocket / ResizeObserver are mocked (jsdom can't lay out a real terminal);
// MSW seeds /api/v1 (ws-running is `running`; the persisted ghost id is not in the seed).

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../../src/App";
import {
	LAYOUT_STORAGE_KEY,
	useLayoutStore,
} from "../../src/store/layoutStore";
import {
	installMockWebSocket,
	type MockWebSocket,
} from "../helpers/mockWebSocket";
import { resetXtermMocks, Terminal } from "../helpers/mockXterm";
import { installMockResizeObserver } from "../helpers/resizeObserver";

vi.mock("@xterm/xterm", () => import("../helpers/mockXterm"));
vi.mock("@xterm/addon-fit", () => import("../helpers/mockXterm"));
vi.mock("@xterm/xterm/css/xterm.css", () => ({}));

// A still-running workspace from the MSW seed + a ghost id absent from the live list.
const RUNNING_ID = "ws-running";
const GHOST_ID = "ws-ghost";

/**
 * Seed localStorage with a persisted layout exactly as zustand `persist` would have
 * written it before a refresh, then rehydrate the store from it. This is the honest
 * "after refresh" entry point: the store starts from disk, not from a setState.
 */
function seedPersistedLayout(): void {
	localStorage.setItem(
		LAYOUT_STORAGE_KEY,
		JSON.stringify({
			state: {
				mosaicNode: { direction: "row", first: RUNNING_ID, second: GHOST_ID },
				activeWorkspaceId: GHOST_ID,
			},
			version: 0,
		}),
	);
	// Pull the persisted state off disk into the live store (what a page load does).
	useLayoutStore.persist.rehydrate();
}

function renderApp() {
	const client = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	const wrapper = ({ children }: { children: ReactNode }) => (
		<QueryClientProvider client={client}>{children}</QueryClientProvider>
	);
	return render(<App />, { wrapper });
}

let WS: typeof MockWebSocket;

beforeEach(() => {
	localStorage.clear();
	useLayoutStore.setState({ mosaicNode: null, activeWorkspaceId: null });
	WS = installMockWebSocket();
	installMockResizeObserver();
	resetXtermMocks();
});

afterEach(() => {
	vi.restoreAllMocks();
});

describe("restore-after-refresh (UI-05)", () => {
	it("drops the gone leaf and reconnects the still-running panel to a fresh live WS", async () => {
		seedPersistedLayout();
		// Sanity: the persisted tree started with BOTH ids (pre-reconcile).
		expect(useLayoutStore.getState().mosaicNode).toEqual({
			direction: "row",
			first: RUNNING_ID,
			second: GHOST_ID,
		});

		renderApp();

		// 1) Reconcile: after the first live list lands, the ghost leaf is dropped and
		//    the tree collapses to the lone running survivor; the active id retargets.
		await waitFor(() => {
			expect(useLayoutStore.getState().mosaicNode).toBe(RUNNING_ID);
		});
		expect(useLayoutStore.getState().activeWorkspaceId).toBe(RUNNING_ID);

		// The running panel re-mounted: its terminal body (uniquely keyed by id) is in
		// the grid, and its header shows the name resolved from the live list. The name
		// appears twice (sidebar row + panel header), which itself confirms the remount.
		expect(await screen.findByTestId(`term-${RUNNING_ID}`)).toBeInTheDocument();
		expect(screen.getAllByText("project-eta").length).toBeGreaterThanOrEqual(2);

		// 2) Live reconnect: a fresh WS to the running workspace's terminal is OPEN.
		//    (The ghost panel may briefly mount + dial before the first list lands;
		//    after reconcile its panel unmounts and that socket is closed. The running
		//    socket is the one that survives — that is the live-session reconnect.)
		const runningSocket = await waitFor(() => {
			const open = WS.instances.find(
				(s) =>
					s.url.includes(`/ws/workspaces/${RUNNING_ID}/terminal`) && !s.closed,
			);
			expect(open).toBeDefined();
			return open as MockWebSocket;
		});
		expect(runningSocket.url).toContain(
			`/ws/workspaces/${RUNNING_ID}/terminal`,
		);

		// Every ghost-id socket (if any was dialed pre-reconcile) is closed — the gone
		// workspace holds no live terminal after the persisted tree reconciles.
		for (const socket of WS.instances) {
			if (socket.url.includes(GHOST_ID)) {
				expect(socket.closed).toBe(true);
			}
		}
	});

	it("restores no scrollback — the terminal stays blank until a live OUTPUT frame (Pitfall 7)", async () => {
		seedPersistedLayout();
		renderApp();

		await waitFor(() => {
			expect(useLayoutStore.getState().mosaicNode).toBe(RUNNING_ID);
		});

		// The live reconnect socket for the running workspace (open, post-reconcile).
		const socket = await waitFor(() => {
			const open = WS.instances.find(
				(s) =>
					s.url.includes(`/ws/workspaces/${RUNNING_ID}/terminal`) && !s.closed,
			);
			expect(open).toBeDefined();
			return open as MockWebSocket;
		});

		// On reconnect, BEFORE any live frame, NO terminal has any writes: no replay
		// buffer is restored from the persisted state (v1 has no scrollback — honest
		// blank-then-live across every panel).
		const totalWrittenBefore = Terminal.instances.reduce(
			(n, t) => n + t.written.length,
			0,
		);
		expect(totalWrittenBefore).toBe(0);

		// The session is live: only a real OUTPUT frame from the PTY paints a terminal.
		socket.emitOpen();
		socket.emitOutput("live-after-reconnect");
		const liveText = Terminal.instances.map((t) => t.written.join("")).join("");
		expect(liveText).toContain("live-after-reconnect");

		// The persisted layout carries ONLY view state (tree + active id) — never a
		// terminal transcript / replay buffer (Pitfall 11 + Pitfall 7).
		const persisted = JSON.parse(
			localStorage.getItem(LAYOUT_STORAGE_KEY) ?? "{}",
		);
		expect(Object.keys(persisted.state)).toEqual([
			"mosaicNode",
			"activeWorkspaceId",
		]);
	});
});
