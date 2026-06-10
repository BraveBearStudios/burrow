// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// useTerminal lifecycle tests (TERM-05/06/07) over a mocked WebSocket + xterm.
// Task 1 authors the happy-path (RED until the hook exists); Task 3 adds the
// fit/reconnect/dispose hardening tests under this same file.

import { render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	installMockWebSocket,
	lastSocket,
	type MockWebSocket,
} from "../../tests/helpers/mockWebSocket";
import { lastTerminal, resetXtermMocks } from "../../tests/helpers/mockXterm";
import { installMockResizeObserver } from "../../tests/helpers/resizeObserver";
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
		const { rerender } = render(<StatusHarness />);
		expect(status).toBe("connecting");
		lastSocket().emitOpen();
		rerender(<StatusHarness />);
		expect(status).toBe("open");
	});
});
