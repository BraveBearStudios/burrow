// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// TerminalPanel happy-path + overlay tests. Task 1 authors the happy path
// (mount → connect → init → echo → type), RED until TerminalPanel/useTerminal
// exist; Task 3 adds the reconnecting/error overlay assertions.

import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	installMockWebSocket,
	lastSocket,
	type MockWebSocket,
} from "../../tests/helpers/mockWebSocket";
import { lastTerminal, resetXtermMocks } from "../../tests/helpers/mockXterm";
import { installMockResizeObserver } from "../../tests/helpers/resizeObserver";
import { TerminalPanel } from "./TerminalPanel";

vi.mock("@xterm/xterm", () => import("../../tests/helpers/mockXterm"));
vi.mock("@xterm/addon-fit", () => import("../../tests/helpers/mockXterm"));
vi.mock("@xterm/xterm/css/xterm.css", () => ({}));

describe("TerminalPanel — happy path (the MVP slice)", () => {
	let WS: typeof MockWebSocket;

	beforeEach(() => {
		WS = installMockWebSocket();
		installMockResizeObserver();
		resetXtermMocks();
	});

	afterEach(() => {
		vi.restoreAllMocks();
	});

	it("mounting opens a WS to the workspace terminal and sends init on open", () => {
		render(<TerminalPanel id="w1" name="project-eta" status="running" />);
		const socket = lastSocket();
		expect(socket.url).toContain("/ws/workspaces/w1/terminal");
		expect(WS.instances).toHaveLength(1);

		socket.emitOpen();
		const first = socket.sent[0];
		const text =
			typeof first === "string" ? first : new TextDecoder().decode(first);
		expect(JSON.parse(text)).toMatchObject({ AuthToken: "" });
	});

	it("writes OUTPUT ('0'+\"hi\") through to the terminal (echo visible)", () => {
		render(<TerminalPanel id="w1" name="project-eta" status="running" />);
		const socket = lastSocket();
		socket.emitOpen();
		socket.emitOutput("hi");
		expect(lastTerminal().written.join("")).toContain("hi");
	});

	it("sends an inputFrame when the terminal emits typed data", () => {
		render(<TerminalPanel id="w1" name="project-eta" status="running" />);
		const socket = lastSocket();
		socket.emitOpen();
		lastTerminal().emitData("x");
		const sent = socket.sent.map((f) =>
			typeof f === "string" ? f : Array.from(f),
		);
		expect(sent).toContainEqual([0x30, 0x78]);
	});

	it("renders the workspace name in the panel header", () => {
		render(<TerminalPanel id="w1" name="project-eta" status="running" />);
		expect(screen.getByText("project-eta")).toBeInTheDocument();
	});

	it("shows the connecting overlay before the first byte", () => {
		render(<TerminalPanel id="w1" name="project-eta" status="running" />);
		expect(screen.getByText("Connecting…")).toBeInTheDocument();
	});
});

describe("TerminalPanel — overlays (TERM-06)", () => {
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

	it("shows the reconnecting overlay with the verbatim attempt copy + Reattach", () => {
		render(<TerminalPanel id="w1" name="project-eta" status="running" />);
		act(() => {
			lastSocket().emitOpen();
		});
		act(() => {
			lastSocket().emitClose(1006);
		});
		// 02-UI-SPEC copy: `reconnecting… attempt {n} / 5`
		expect(screen.getByText("reconnecting… attempt 1 / 5")).toBeInTheDocument();
		expect(
			screen.getByRole("button", { name: "Reattach" }),
		).toBeInTheDocument();
		// aria-live region announces the attempt counter.
		expect(screen.getByRole("status")).toBeInTheDocument();
	});

	it("shows the error overlay (no spinner) + Retry on a 1008 close", () => {
		render(<TerminalPanel id="w1" name="project-eta" status="running" />);
		act(() => {
			lastSocket().emitOpen();
		});
		act(() => {
			lastSocket().emitClose(1008);
		});
		expect(
			screen.getByText("Session unavailable. the worker isn't ready."),
		).toBeInTheDocument();
		expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
		expect(screen.getByRole("alert")).toBeInTheDocument();
	});
});

describe("TerminalPanel — terminate confirm + detach (UI-SPEC criterion 12)", () => {
	beforeEach(() => {
		installMockWebSocket();
		installMockResizeObserver();
		resetXtermMocks();
	});
	afterEach(() => {
		vi.restoreAllMocks();
	});

	it("terminate (×) asks the confirm copy and does NOT terminate until Destroy", () => {
		const onTerminate = vi.fn();
		render(
			<TerminalPanel
				id="w1"
				name="project-eta"
				status="running"
				onTerminate={onTerminate}
			/>,
		);

		// × opens the confirm gate — terminate is not fired yet.
		fireEvent.click(screen.getByRole("button", { name: "Terminate" }));
		expect(
			screen.getByText(
				"Destroy project-eta? The container and its session are gone for good.",
			),
		).toBeInTheDocument();
		expect(onTerminate).not.toHaveBeenCalled();

		// Cancel dismisses without terminating.
		fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
		expect(onTerminate).not.toHaveBeenCalled();

		// Re-open and confirm: Destroy fires onTerminate exactly once with the id.
		fireEvent.click(screen.getByRole("button", { name: "Terminate" }));
		fireEvent.click(screen.getByRole("button", { name: "Destroy" }));
		expect(onTerminate).toHaveBeenCalledTimes(1);
		expect(onTerminate).toHaveBeenCalledWith("w1");
	});

	it("detach (plug) closes the live socket non-destructively → reconnecting overlay", () => {
		const onDetach = vi.fn();
		const onTerminate = vi.fn();
		render(
			<TerminalPanel
				id="w1"
				name="project-eta"
				status="running"
				onDetach={onDetach}
				onTerminate={onTerminate}
			/>,
		);
		act(() => {
			lastSocket().emitOpen();
		});

		// Detach closes the socket (non-destructive) and notifies the parent. It NEVER
		// terminates the workspace (no confirm, no onTerminate).
		fireEvent.click(
			screen.getByRole("button", {
				name: "Detach (keeps the session running)",
			}),
		);
		expect(lastSocket().closed).toBe(true);
		expect(onDetach).toHaveBeenCalledWith("w1");
		expect(onTerminate).not.toHaveBeenCalled();

		// The dropped socket surfaces the reconnecting overlay (session survives).
		act(() => {
			lastSocket().emitClose(1000);
		});
		expect(screen.getByText("reconnecting… attempt 1 / 5")).toBeInTheDocument();
	});
});
