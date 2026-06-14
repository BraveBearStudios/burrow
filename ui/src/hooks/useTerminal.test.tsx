// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// useTerminal lifecycle tests (TERM-05/06/07) over a mocked WebSocket + xterm.
// Task 1 authors the happy-path (RED until the hook exists); Task 3 adds the
// fit/reconnect/dispose hardening tests under this same file.

import { act, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	frameText,
	installMockWebSocket,
	lastSocket,
	type MockWebSocket,
} from "../../tests/helpers/mockWebSocket";
import {
	lastTerminal,
	liveTerminalCount,
	resetXtermMocks,
} from "../../tests/helpers/mockXterm";
import {
	installMockResizeObserver,
	liveObserverCount,
	MockResizeObserver,
} from "../../tests/helpers/resizeObserver";
import type { WorkspaceStatus } from "../types/workspace";
import { useTerminal } from "./useTerminal";

vi.mock("@xterm/xterm", () => import("../../tests/helpers/mockXterm"));
vi.mock("@xterm/addon-fit", () => import("../../tests/helpers/mockXterm"));
vi.mock("@xterm/xterm/css/xterm.css", () => ({}));

// Drives the hook from a component so React runs its effects/cleanup.
function Harness({ id }: { id: string }) {
	const { containerRef } = useTerminal(id, "running");
	return <div data-testid="term" ref={containerRef} />;
}

describe("useTerminal — happy path (TERM-05)", () => {
	let WS: typeof MockWebSocket;

	beforeEach(() => {
		WS = installMockWebSocket();
		installMockResizeObserver();
		resetXtermMocks();
	});

	afterEach(() => {
		vi.restoreAllMocks();
	});

	it("opens a WS to /ws/workspaces/{id}/terminal and sends init on open", () => {
		render(<Harness id="w1" />);
		const socket = lastSocket();
		expect(socket.url).toContain("/ws/workspaces/w1/terminal");
		expect(socket.binaryType).toBe("arraybuffer");
		expect(WS.instances).toHaveLength(1);

		socket.emitOpen();
		const first = socket.sent[0];
		const text =
			typeof first === "string" ? first : new TextDecoder().decode(first);
		// Init reflects the fitted grid (the hook fits before connecting), so
		// assert the shape — AuthToken "" + numeric columns/rows — not stuck 80x24.
		const init = JSON.parse(text);
		expect(init).toMatchObject({ AuthToken: "" });
		expect(typeof init.columns).toBe("number");
		expect(typeof init.rows).toBe("number");
	});

	it("writes stripped OUTPUT text to the terminal", () => {
		render(<Harness id="w1" />);
		const socket = lastSocket();
		socket.emitOpen();
		socket.emitOutput("hi");
		expect(lastTerminal().written.join("")).toContain("hi");
	});

	it("sends an inputFrame on typed data ('0' + data)", () => {
		render(<Harness id="w1" />);
		const socket = lastSocket();
		socket.emitOpen();
		lastTerminal().emitData("x");
		const sent = socket.sent.map((f) =>
			typeof f === "string" ? f : Array.from(f),
		);
		expect(sent).toContainEqual([0x30, 0x78]); // '0' + 'x'
	});

	it("starts connecting and flips to open on the first onopen", () => {
		let status = "";
		function StatusHarness() {
			const t = useTerminal("w1", "running");
			status = t.status;
			return <div ref={t.containerRef} />;
		}
		render(<StatusHarness />);
		expect(status).toBe("connecting");
		act(() => {
			lastSocket().emitOpen();
		});
		expect(status).toBe("open");
	});
});

// A status-reading harness shared by the Task-3 hardening blocks.
let observed: {
	status: string;
	reconnectAttempts: number;
	reattach: () => void;
};
function ObservedHarness({ id = "w1" }: { id?: string }) {
	const t = useTerminal(id, "running");
	observed = {
		status: t.status,
		reconnectAttempts: t.reconnectAttempts,
		reattach: t.reattach,
	};
	return <div ref={t.containerRef} />;
}

describe("useTerminal — fit on resize (TERM-05)", () => {
	beforeEach(() => {
		installMockWebSocket();
		installMockResizeObserver();
		resetXtermMocks();
		// jsdom reports 0 for layout; give the panel body a visible non-zero size
		// so the hook's "only fit when visible & non-zero" guard lets fit() run.
		vi.spyOn(HTMLElement.prototype, "offsetWidth", "get").mockReturnValue(800);
		vi.spyOn(HTMLElement.prototype, "offsetHeight", "get").mockReturnValue(600);
	});
	afterEach(() => {
		vi.restoreAllMocks();
	});

	it("fits and sends a resize frame on a ResizeObserver callback (not stuck 80x24)", () => {
		render(<ObservedHarness />);
		const socket = lastSocket();
		act(() => {
			socket.emitOpen();
		});
		const term = lastTerminal();
		// The mock fit() reflows off the 80x24 default.
		expect(term.cols).not.toBe(80);

		const before = socket.sent.length;
		act(() => {
			MockResizeObserver.instances.at(-1)?.trigger();
		});
		// A resize frame ('1' + JSON {columns,rows}) was sent.
		const resizeFrames = socket.sent
			.slice(before)
			.map(frameText)
			.filter((t) => t.startsWith("1") && t.includes("columns"));
		expect(resizeFrames.length).toBeGreaterThanOrEqual(1);
	});
});

describe("useTerminal — reconnect with jittered backoff (TERM-06)", () => {
	beforeEach(() => {
		vi.useFakeTimers();
		installMockWebSocket();
		installMockResizeObserver();
		resetXtermMocks();
	});
	afterEach(() => {
		vi.useRealTimers();
		vi.restoreAllMocks();
	});

	it("reconnects on an unexpected close, incrementing the attempt counter", () => {
		render(<ObservedHarness />);
		act(() => {
			lastSocket().emitOpen();
		});
		expect(observed.status).toBe("open");

		const firstSocket = lastSocket();
		act(() => {
			firstSocket.emitClose(1006); // abnormal drop
		});
		expect(observed.status).toBe("reconnecting");
		expect(observed.reconnectAttempts).toBe(1);

		// The backoff timer fires and a NEW socket is opened.
		act(() => {
			vi.runOnlyPendingTimers();
		});
		expect(lastSocket()).not.toBe(firstSocket);

		// A successful reopen resets the attempt counter to 0.
		act(() => {
			lastSocket().emitOpen();
		});
		expect(observed.status).toBe("open");
		expect(observed.reconnectAttempts).toBe(0);
	});

	it("stops retrying after 5 attempts and shows the error state", () => {
		render(<ObservedHarness />);
		act(() => {
			lastSocket().emitOpen();
		});
		// Drop + let the timer fire, six times: attempts 1..5 then exhaustion.
		for (let i = 0; i < 6; i += 1) {
			act(() => {
				lastSocket().emitClose(1006);
			});
			act(() => {
				vi.runOnlyPendingTimers();
			});
		}
		expect(observed.status).toBe("error");
	});

	it("does NOT retry on close code 1008 (policy violation) — error state", () => {
		render(<ObservedHarness />);
		act(() => {
			lastSocket().emitOpen();
		});
		const sockets = MockWebSocketInstances();
		act(() => {
			lastSocket().emitClose(1008);
		});
		expect(observed.status).toBe("error");
		act(() => {
			vi.runOnlyPendingTimers();
		});
		// No new socket was constructed after the 1008 close.
		expect(MockWebSocketInstances()).toBe(sockets);
	});

	it("goes to error (no retry) on an LXC_NOT_READY error frame", () => {
		render(<ObservedHarness />);
		const socket = lastSocket();
		act(() => {
			socket.emitOpen();
		});
		act(() => {
			socket.emitMessage(
				JSON.stringify({ type: "error", code: "LXC_NOT_READY" }),
			);
		});
		expect(observed.status).toBe("error");
	});
});

describe("useTerminal — clean dispose (TERM-07)", () => {
	beforeEach(() => {
		installMockWebSocket();
		installMockResizeObserver();
		resetXtermMocks();
	});
	afterEach(() => {
		vi.restoreAllMocks();
	});

	it("closes the WS, disposes the terminal, and disconnects the observer on unmount", () => {
		const { unmount } = render(<ObservedHarness />);
		const socket = lastSocket();
		expect(liveTerminalCount()).toBe(1);
		expect(liveObserverCount()).toBe(1);

		unmount();
		expect(socket.closed).toBe(true);
		expect(liveTerminalCount()).toBe(0);
		expect(liveObserverCount()).toBe(0);
	});

	it("leaves a flat terminal/observer count over many mount/unmount cycles", () => {
		for (let i = 0; i < 50; i += 1) {
			const { unmount } = render(<ObservedHarness />);
			unmount();
		}
		expect(liveTerminalCount()).toBe(0);
		expect(liveObserverCount()).toBe(0);
	});
});

// A status-parameterized harness for the stopped-gate block: it drives the hook
// with a live `status` so a rerender flips the [workspaceId, status] effect dep.
function StatusHarness({
	id = "w1",
	status,
}: {
	id?: string;
	status: WorkspaceStatus;
}) {
	const t = useTerminal(id, status);
	return <div data-testid="term" ref={t.containerRef} />;
}

describe("useTerminal — stopped gate (UI-07/UI-08)", () => {
	let WS: typeof MockWebSocket;

	beforeEach(() => {
		WS = installMockWebSocket();
		installMockResizeObserver();
		resetXtermMocks();
	});
	afterEach(() => {
		vi.restoreAllMocks();
	});

	it("opens NO socket while status is stopped (the line-178 gate holds)", () => {
		render(<StatusHarness status="stopped" />);
		// A stopped workspace has no live ttyd — the effect early-returns, so the
		// hook constructs zero sockets and runs no reconnect/backoff loop.
		expect(WS.instances).toHaveLength(0);
	});

	it("tears the socket down on running→stopped and opens none after", () => {
		const { rerender } = render(<StatusHarness status="running" />);
		// A running workspace opened a socket; drive it open.
		expect(WS.instances).toHaveLength(1);
		const opened = WS.instances.at(-1);
		if (!opened) {
			throw new Error("expected a socket while running");
		}
		act(() => {
			opened.emitOpen();
		});

		// Flip to stopped: the [workspaceId, status] dep change runs the cleanup
		// (closes the socket, clears the timer), then the re-run early-returns.
		rerender(<StatusHarness status="stopped" />);
		expect(opened.closed).toBe(true);
		// No new OPEN socket exists after the flip (no phantom reconnect).
		expect(WS.instances.filter((s) => !s.closed)).toHaveLength(0);
	});

	it("reconnects with a fresh socket on stopped→running", () => {
		const { rerender } = render(<StatusHarness status="stopped" />);
		expect(WS.instances).toHaveLength(0);

		// Start: the effect re-runs and constructs a fresh socket (reconnect).
		rerender(<StatusHarness status="running" />);
		expect(WS.instances).toHaveLength(1);
		const reconnected = WS.instances.at(-1);
		if (!reconnected) {
			throw new Error("expected a fresh socket after stopped→running");
		}
		expect(reconnected.closed).toBe(false);
	});
});

/** Snapshot the MockWebSocket instances array identity for no-retry assertions. */
function MockWebSocketInstances() {
	return lastSocketCount();
}
function lastSocketCount(): number {
	// biome-ignore lint/suspicious/noExplicitAny: read the mock's static list
	return ((globalThis as any).WebSocket?.instances ?? []).length;
}
