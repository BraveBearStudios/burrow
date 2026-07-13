// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// NewWorkspaceModal tests (UI-03). Drives the binding 02-UI-SPEC create flow over
// MSW: required-field validation gating the Create button (verbatim `{Field} is
// required.` copy), a successful POST → the brief 4-step boot-progress confirmation →
// layoutStore.openPanel(newId) + close, and a server envelope error (capacity
// CAP-01) surfacing the message verbatim + a Close button. ASYNC-202 (ADR-0017): the
// POST resolves on a 202 + `creating` row and the modal closes IMMEDIATELY on that
// success (not on `running`); the workspace-list poll drives the later transition. The
// test asserts the steps + `→ 202 · polling status…` footnote render, not any real
// per-step API claim.

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
import type { WorkspaceCreate } from "../types/workspace";
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
	it("submits → boot-progress (4 steps + 202 footnote) → opens the panel + closes on the 202 creating row", async () => {
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

		// On the resolved 202 creating row the panel opens (newId) + the modal closes
		// immediately (ADR-0017); the list poll drives the later running transition.
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

describe("NewWorkspaceModal — Auto (least-loaded) default (WSX-01)", () => {
	// Register a POST override that captures the parsed request body, returning the
	// standard created-row envelope with a server-derived node so the auto path round
	// trips like the backend (which fills the chosen node on the row).
	function captureCreateBody() {
		const captured: { body: WorkspaceCreate | null } = { body: null };
		server.use(
			http.post("/api/v1/workspaces", async ({ request }) => {
				const body = (await request.json()) as WorkspaceCreate;
				captured.body = body;
				return HttpResponse.json(
					{
						data: {
							id: "ws-created",
							name: body.name,
							status: "creating",
							vmid: 110,
							// Auto (null/omitted) → the server picks the least-loaded node1.
							node: body.node ?? "node1",
							lxcIp: null,
							projectRepo: body.projectRepo,
							projectBranch: body.projectBranch ?? "main",
							pluginSet: body.pluginSet ?? "default",
							createdAt: "2026-06-10T02:00:00Z",
							stoppedAt: null,
							destroyedAt: null,
							deletedAt: null,
						},
						meta: { requestId: "t", timestamp: "2026-06-10T00:00:00Z" },
						error: null,
					},
					// IN-01: the backend create route returns 202 + a creating row
					// (async-202, ADR-0017) — keep this double aligned with the backend.
					{ status: 202 },
				);
			}),
		);
		return captured;
	}

	/** Fill only the two required fields, leaving the Node select on its default. */
	function fillRequiredOnly() {
		fireEvent.change(screen.getByLabelText("Name"), {
			target: { value: "project-omega" },
		});
		fireEvent.change(screen.getByLabelText("Git repo"), {
			target: { value: "github.com/acme/omega" },
		});
	}

	it("defaults the Node select to Auto and enables Create with only Name + Git repo", async () => {
		renderModal();
		await waitFor(() =>
			expect(screen.getByRole("option", { name: "node1" })).toBeInTheDocument(),
		);
		// The Auto option exists and is the selected default (no first-node-on-mount).
		const select = screen.getByLabelText("Node") as HTMLSelectElement;
		expect(
			screen.getByRole("option", { name: "Auto (least-loaded)" }),
		).toBeInTheDocument();
		expect(select.value).toBe("");
		// Auto is a valid form state: Name + Git repo alone enable Create.
		fillRequiredOnly();
		expect(screen.getByRole("button", { name: /Create/ })).toBeEnabled();
	});

	it("submits the Auto choice with node null and opens the panel + closes", async () => {
		const captured = captureCreateBody();
		const { onClose, unmount } = renderModal();
		await waitFor(() =>
			expect(screen.getByRole("option", { name: "node1" })).toBeInTheDocument(),
		);
		fillRequiredOnly(); // leave Auto selected
		fireEvent.click(screen.getByRole("button", { name: /Create/ }));

		await waitFor(() =>
			expect(useLayoutStore.getState().mosaicNode).toBe("ws-created"),
		);
		await waitFor(() => expect(onClose).toHaveBeenCalled());
		// The Auto path sent node: null SPECIFICALLY (not "", not undefined/omitted) so
		// the backend auto-selects. toHaveProperty asserts the exact value, catching a
		// regression that started sending "" or dropped the key (IN-04).
		expect(captured.body).toHaveProperty("node", null);
		unmount();
	});

	it("still submits a manual node pick with the chosen node string", async () => {
		const captured = captureCreateBody();
		const { unmount } = renderModal();
		await waitFor(() =>
			expect(screen.getByRole("option", { name: "node1" })).toBeInTheDocument(),
		);
		fillRequiredOnly();
		// Explicitly pick node1 — the unchanged manual path.
		fireEvent.change(screen.getByLabelText("Node"), {
			target: { value: "node1" },
		});
		fireEvent.click(screen.getByRole("button", { name: /Create/ }));

		await waitFor(() =>
			expect(useLayoutStore.getState().mosaicNode).toBe("ws-created"),
		);
		expect(captured.body?.node).toBe("node1");
		unmount();
	});
});

describe("NewWorkspaceModal — persistent checkbox (WSX-02)", () => {
	// Same body-capturing POST override as WSX-01: round-trip the created row with
	// the submitted persistent flag so the assertion reads the exact request body.
	function captureCreateBody() {
		const captured: { body: WorkspaceCreate | null } = { body: null };
		server.use(
			http.post("/api/v1/workspaces", async ({ request }) => {
				const body = (await request.json()) as WorkspaceCreate;
				captured.body = body;
				return HttpResponse.json(
					{
						data: {
							id: "ws-created",
							name: body.name,
							status: "creating",
							vmid: 110,
							node: body.node ?? "node1",
							lxcIp: null,
							projectRepo: body.projectRepo,
							projectBranch: body.projectBranch ?? "main",
							pluginSet: body.pluginSet ?? "default",
							createdAt: "2026-06-10T02:00:00Z",
							stoppedAt: null,
							destroyedAt: null,
							deletedAt: null,
						},
						meta: { requestId: "t", timestamp: "2026-06-10T00:00:00Z" },
						error: null,
					},
					{ status: 202 },
				);
			}),
		);
		return captured;
	}

	/** Fill only the two required fields (Name, Git repo); leave Node on Auto. */
	function fillRequiredOnly() {
		fireEvent.change(screen.getByLabelText("Name"), {
			target: { value: "project-omega" },
		});
		fireEvent.change(screen.getByLabelText("Git repo"), {
			target: { value: "github.com/acme/omega" },
		});
	}

	it("submits persistent:true when the persistent checkbox is checked", async () => {
		const captured = captureCreateBody();
		const { unmount } = renderModal();
		await waitFor(() =>
			expect(screen.getByRole("option", { name: "node1" })).toBeInTheDocument(),
		);
		fillRequiredOnly();
		// Query the checkbox by its accessible (verbatim) label, then check it.
		fireEvent.click(
			screen.getByLabelText("Persistent (keep workspace after session ends)"),
		);
		fireEvent.click(screen.getByRole("button", { name: /Create/ }));

		await waitFor(() =>
			expect(useLayoutStore.getState().mosaicNode).toBe("ws-created"),
		);
		expect(captured.body?.persistent).toBe(true);
		unmount();
	});

	it("defaults persistent unchecked → the create body does not send persistent:true", async () => {
		const captured = captureCreateBody();
		const { unmount } = renderModal();
		await waitFor(() =>
			expect(screen.getByRole("option", { name: "node1" })).toBeInTheDocument(),
		);
		// The checkbox defaults unchecked — leave it alone.
		const persistentBox = screen.getByLabelText(
			"Persistent (keep workspace after session ends)",
		) as HTMLInputElement;
		expect(persistentBox.checked).toBe(false);
		fillRequiredOnly();
		fireEvent.click(screen.getByRole("button", { name: /Create/ }));

		await waitFor(() =>
			expect(useLayoutStore.getState().mosaicNode).toBe("ws-created"),
		);
		// Default (ephemeral): persistent is false (never true).
		expect(captured.body?.persistent).not.toBe(true);
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
