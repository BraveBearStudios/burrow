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
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
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
	render(<NewWorkspaceModal onClose={onClose} />, { wrapper });
	return { onClose };
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
	it("submits → cosmetic boot-progress (4 steps + 202 footnote) → openPanel + close", async () => {
		const openPanel = vi.spyOn(useLayoutStore.getState(), "openPanel");
		const { onClose } = renderModal();
		await waitFor(() =>
			expect(screen.getByRole("option", { name: "node1" })).toBeInTheDocument(),
		);
		fillRequired();
		fireEvent.click(screen.getByRole("button", { name: /Create/ }));

		// The saga swaps in: title → Creating {name}, the 202 footnote + 4 steps.
		expect(await screen.findByText("Creating project-omega")).toBeInTheDocument();
		expect(
			screen.getByText("POST /api/v1/workspaces → 202 · polling status…"),
		).toBeInTheDocument();
		expect(screen.getByText(/Waiting for Claude/)).toBeInTheDocument();

		// On the resolved running row the panel opens (newId) + the modal closes.
		await waitFor(() => expect(openPanel).toHaveBeenCalledWith("ws-created"));
		await waitFor(() => expect(onClose).toHaveBeenCalled());
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
		const openPanel = vi.spyOn(useLayoutStore.getState(), "openPanel");
		renderModal();
		await waitFor(() =>
			expect(screen.getByRole("option", { name: "node1" })).toBeInTheDocument(),
		);
		fillRequired();
		fireEvent.click(screen.getByRole("button", { name: /Create/ }));

		expect(
			await screen.findByText("Node node1 is over its memory threshold."),
		).toBeInTheDocument();
		expect(screen.getByRole("button", { name: "Close" })).toBeInTheDocument();
		expect(openPanel).not.toHaveBeenCalled();
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
