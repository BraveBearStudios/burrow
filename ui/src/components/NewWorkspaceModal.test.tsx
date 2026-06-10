// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// NewWorkspaceModal tests (UI-03). Drives the binding 02-UI-SPEC create flow over
// MSW: required-field validation gating the Create button (verbatim `{Field} is
// required.` copy), a successful POST → the cosmetic 4-step boot-progress saga →
// layoutStore.openPanel(newId) + close, and a server envelope error (capacity
// CAP-01) surfacing the message verbatim + a Close button. The boot-progress is
// COSMETIC (synchronous create, A3/Pitfall 5) — the test asserts the steps +
// `→ 202 · polling status…` footnote render, not any real per-step API claim.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
	cleanup,
	fireEvent,
	render,
	screen,
	waitFor,
} from "@testing-library/react";
import { HttpResponse, http } from "msw";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { server } from "../../tests/msw/server";
import { useLayoutStore } from "../store/layoutStore";
import { NewWorkspaceModal } from "./NewWorkspaceModal";

function renderModal(onClose = vi.fn()) {
	const client = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	const wrapper = ({ children }: { children: ReactNode }) => (
		<QueryClientProvider client={client}>{children}</QueryClientProvider>
	);
	const { unmount } = render(<NewWorkspaceModal onClose={onClose} />, {
		wrapper,
	});
	return { onClose, unmount };
}

/** Fill the three required fields (Name, Git repo, Node) with valid values. */
function fillRequired() {
	fireEvent.change(screen.getByLabelText("Name"), {
		target: { value: "project-omega" },
	});
	fireEvent.change(screen.getByLabelText("Git repo"), {
		target: { value: "github.com/acme/omega" },
	});
	// Node select is populated from useNodes (seed: node1/node2).
	fireEvent.change(screen.getByLabelText("Node"), {
		target: { value: "node1" },
	});
}

beforeEach(() => {
	localStorage.clear();
	useLayoutStore.setState({ mosaicNode: null, activeWorkspaceId: null });
});

afterEach(() => {
	// Unmount so the modal's unmount effect flips isMountedRef (any in-flight saga
	// becomes a no-op). Assertions read the reset-per-test layoutStore state, so no
	// spy-identity leakage across tests is possible.
	cleanup();
	vi.restoreAllMocks();
});

describe("NewWorkspaceModal — validation (UI-03)", () => {
	it("disables Create until Name + Git repo + Node are filled", async () => {
		renderModal();
		// Node options must load from useNodes first.
		await waitFor(() =>
			expect(screen.getByRole("option", { name: "node1" })).toBeInTheDocument(),
		);
		const create = screen.getByRole("button", { name: /Create/ });
		expect(create).toBeDisabled();
		fillRequired();
		expect(create).toBeEnabled();
	});

	it("shows the verbatim `{Field} is required.` helper on a blurred-empty field", async () => {
		renderModal();
		await waitFor(() =>
			expect(screen.getByRole("option", { name: "node1" })).toBeInTheDocument(),
		);
		// Touch then clear Git repo to trip its required helper.
		const repo = screen.getByLabelText("Git repo");
		fireEvent.change(repo, { target: { value: "x" } });
		fireEvent.change(repo, { target: { value: "" } });
		fireEvent.blur(repo);
		expect(screen.getByText("Git repo is required.")).toBeInTheDocument();
	});
});

describe("NewWorkspaceModal — create saga (UI-03)", () => {
	// These assert against the REAL layoutStore state (reset in beforeEach) rather
	// than a spy on the singleton store method — a spy's identity is shared across
	// tests, so a stray async could be attributed to the wrong test; the store's
	// mosaicNode is reset per test, making "did the panel open?" leak-proof.
	it("submits → cosmetic boot-progress (4 steps + 202 footnote) → opens the panel + closes", async () => {
		const { onClose, unmount } = renderModal();
		await waitFor(() =>
			expect(screen.getByRole("option", { name: "node1" })).toBeInTheDocument(),
		);
		fillRequired();
		fireEvent.click(screen.getByRole("button", { name: /Create/ }));

		// The saga swaps in: title → Creating {name}, the 202 footnote + 4 steps.
		expect(
			await screen.findByText("Creating project-omega"),
		).toBeInTheDocument();
		expect(
			screen.getByText("POST /api/v1/workspaces → 202 · polling status…"),
		).toBeInTheDocument();
		expect(screen.getByText(/Waiting for Claude/)).toBeInTheDocument();

		// On the resolved running row the panel opens (newId) + the modal closes.
		await waitFor(() =>
			expect(useLayoutStore.getState().mosaicNode).toBe("ws-created"),
		);
		await waitFor(() => expect(onClose).toHaveBeenCalled());
		unmount();
	});

	it("does not double-open when Create is clicked twice (single-shot guard)", async () => {
		const { unmount } = renderModal();
		await waitFor(() =>
			expect(screen.getByRole("option", { name: "node1" })).toBeInTheDocument(),
		);
		fillRequired();
		const create = screen.getByRole("button", { name: /Create/ });
		fireEvent.click(create);
		fireEvent.click(create);
		await waitFor(() =>
			expect(useLayoutStore.getState().mosaicNode).toBe("ws-created"),
		);
		// A single leaf — the second click was latched out (no duplicate open).
		expect(useLayoutStore.getState().mosaicNode).toBe("ws-created");
		unmount();
	});

	it("surfaces a server envelope error (capacity CAP-01) verbatim + a Close button", async () => {
		server.use(
			http.post("/api/v1/workspaces", () =>
				HttpResponse.json(
					{
						data: null,
						meta: { requestId: "t", timestamp: "2026-06-10T00:00:00Z" },
						error: {
							code: "capacity_exceeded",
							message: "Node node1 is over its memory threshold.",
						},
					},
					{ status: 409 },
				),
			),
		);
		const { onClose, unmount } = renderModal();
		await waitFor(() =>
			expect(screen.getByRole("option", { name: "node1" })).toBeInTheDocument(),
		);
		fillRequired();
		fireEvent.click(screen.getByRole("button", { name: /Create/ }));

		expect(
			await screen.findByText("Node node1 is over its memory threshold."),
		).toBeInTheDocument();
		expect(screen.getByRole("button", { name: "Close" })).toBeInTheDocument();
		// The panel never opened and the modal stayed up (no auto-close on error).
		expect(useLayoutStore.getState().mosaicNode).toBeNull();
		expect(onClose).not.toHaveBeenCalled();
		unmount();
	});
});

describe("NewWorkspaceModal — dismissal (UI-03)", () => {
	it("Esc closes the form state", async () => {
		const { onClose } = renderModal();
		await waitFor(() =>
			expect(screen.getByRole("option", { name: "node1" })).toBeInTheDocument(),
		);
		fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
		expect(onClose).toHaveBeenCalled();
	});
});
