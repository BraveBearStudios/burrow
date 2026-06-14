// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// TerminalPanel happy-path + overlay tests. Task 1 authors the happy path
// (mount → connect → init → echo → type), RED until TerminalPanel/useTerminal
// exist; Task 3 adds the reconnecting/error overlay assertions.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
	act,
	fireEvent,
	type RenderResult,
	render,
	screen,
} from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
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

// The panel renders the (closed) ActivityDrawer, whose useWorkspaceEvents hook
// needs a QueryClient in context even when the poll is disabled. Wrap every render
// via the `wrapper` option (NOT inline children) so a later `rerender(...)` keeps
// the provider — an inline-children wrap is dropped on rerender, surfacing a
// "No QueryClient set" error in the gating test that flips status via rerender.
function renderPanel(ui: ReactElement): RenderResult {
	const client = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	return render(ui, {
		wrapper: ({ children }: { children: ReactNode }) => (
			<QueryClientProvider client={client}>{children}</QueryClientProvider>
		),
	});
}

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
		renderPanel(<TerminalPanel id="w1" name="project-eta" status="running" />);
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
		renderPanel(<TerminalPanel id="w1" name="project-eta" status="running" />);
		const socket = lastSocket();
		socket.emitOpen();
		socket.emitOutput("hi");
		expect(lastTerminal().written.join("")).toContain("hi");
	});

	it("sends an inputFrame when the terminal emits typed data", () => {
		renderPanel(<TerminalPanel id="w1" name="project-eta" status="running" />);
		const socket = lastSocket();
		socket.emitOpen();
		lastTerminal().emitData("x");
		const sent = socket.sent.map((f) =>
			typeof f === "string" ? f : Array.from(f),
		);
		expect(sent).toContainEqual([0x30, 0x78]);
	});

	it("renders the workspace name in the panel header", () => {
		renderPanel(<TerminalPanel id="w1" name="project-eta" status="running" />);
		expect(screen.getByText("project-eta")).toBeInTheDocument();
	});

	it("shows the connecting overlay before the first byte", () => {
		renderPanel(<TerminalPanel id="w1" name="project-eta" status="running" />);
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
		renderPanel(<TerminalPanel id="w1" name="project-eta" status="running" />);
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
		renderPanel(<TerminalPanel id="w1" name="project-eta" status="running" />);
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
		renderPanel(
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
		renderPanel(
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

describe("TerminalPanel — Stop/Start controls + stopped placeholder (UI-07/UI-08)", () => {
	// FAILING-FIRST (Wave 0): these reference the gated Stop/Start header buttons,
	// the pending feedback, and the `Workspace stopped` placeholder body that
	// Plan 02 adds. They are RED until then — the expected Wave 0 state. No test
	// asserts an immediate status swap on click (optimistic-flip trap, Pitfall 1)
	// and none uses getComputedStyle for a pseudo-class (jsdom boundary).
	beforeEach(() => {
		installMockWebSocket();
		installMockResizeObserver();
		resetXtermMocks();
	});
	afterEach(() => {
		vi.restoreAllMocks();
	});

	it("gates: Stop only when running, Start only when stopped, neither otherwise", () => {
		const { rerender } = renderPanel(
			<TerminalPanel id="w1" name="project-eta" status="running" />,
		);
		expect(
			screen.getByRole("button", { name: "Stop workspace" }),
		).toBeInTheDocument();
		expect(
			screen.queryByRole("button", { name: "Start workspace" }),
		).toBeNull();

		rerender(<TerminalPanel id="w1" name="project-eta" status="stopped" />);
		// stopped renders TWO Start affordances (the header button + the placeholder
		// CTA, both aria-label "Start workspace" per UI-SPEC §1+§2), so assert the
		// affordance is present via getAllByRole — getByRole throws on the 2 matches.
		expect(
			screen.getAllByRole("button", { name: "Start workspace" }).length,
		).toBeGreaterThanOrEqual(1);
		expect(screen.queryByRole("button", { name: "Stop workspace" })).toBeNull();

		for (const status of ["creating", "error", "destroyed"] as const) {
			rerender(<TerminalPanel id="w1" name="project-eta" status={status} />);
			expect(
				screen.queryByRole("button", { name: "Stop workspace" }),
			).toBeNull();
			expect(
				screen.queryByRole("button", { name: "Start workspace" }),
			).toBeNull();
		}
	});

	it("Stop fires onStop once immediately, with NO confirm overlay (contrast terminate)", () => {
		const onStop = vi.fn();
		renderPanel(
			<TerminalPanel
				id="w1"
				name="project-eta"
				status="running"
				onStop={onStop}
			/>,
		);

		fireEvent.click(screen.getByRole("button", { name: "Stop workspace" }));

		// Stop is reversible → fires immediately, no `Destroy …?` confirm copy.
		expect(onStop).toHaveBeenCalledTimes(1);
		expect(onStop).toHaveBeenCalledWith("w1");
		expect(
			screen.queryByText(/The container and its session are gone for good/),
		).toBeNull();
	});

	it("disables + aria-busy while stop is pending and does not double-fire", () => {
		const onStop = vi.fn();
		renderPanel(
			<TerminalPanel
				id="w1"
				name="project-eta"
				status="running"
				onStop={onStop}
				stopPending
			/>,
		);

		const btn = screen.getByRole("button", { name: "Stop workspace" });
		expect(btn).toBeDisabled();
		expect(btn).toHaveAttribute("aria-busy", "true");

		// A click while pending must not fire a second mutation (disabled guard).
		fireEvent.click(btn);
		expect(onStop).not.toHaveBeenCalled();
	});

	it("renders the `Workspace stopped` placeholder (heading + copy + CTA, role=status) instead of overlays", () => {
		renderPanel(<TerminalPanel id="w1" name="project-iota" status="stopped" />);

		// The resting-state placeholder: heading + the locked body copy + a Start CTA.
		expect(screen.getByText("Workspace stopped")).toBeInTheDocument();
		expect(
			screen.getByText(
				"This workspace is stopped. Start it to reconnect the terminal and pick up where you left off.",
			),
		).toBeInTheDocument();
		// The placeholder Start CTA (plus the header Start button) — both labeled
		// "Start workspace"; assert at least the placeholder CTA exists via plural.
		expect(
			screen.getAllByRole("button", { name: "Start workspace" }).length,
		).toBeGreaterThanOrEqual(1);

		// It is a calm role=status region (announced politely), NOT role=alert, and
		// NONE of the connecting/reconnecting/error overlays render under it.
		expect(screen.getByRole("status")).toBeInTheDocument();
		expect(screen.queryByRole("alert")).toBeNull();
		expect(screen.queryByText("Connecting…")).toBeNull();
		expect(screen.queryByText(/reconnecting…/)).toBeNull();
		expect(screen.queryByText(/Session unavailable/)).toBeNull();
	});

	it("disables both Start affordances (header + placeholder CTA) while start is pending", () => {
		const onStart = vi.fn();
		renderPanel(
			<TerminalPanel
				id="w1"
				name="project-iota"
				status="stopped"
				onStart={onStart}
				startPending
			/>,
		);

		// Both the header Start button and the placeholder Start CTA carry the same
		// pending state so a stopped panel cannot double-fire start (Pitfall 7).
		const starts = screen.getAllByRole("button", { name: "Start workspace" });
		expect(starts.length).toBeGreaterThanOrEqual(2);
		for (const btn of starts) {
			expect(btn).toBeDisabled();
		}
		fireEvent.click(starts[0]);
		expect(onStart).not.toHaveBeenCalled();
	});
});
