// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// App shell test (Wave 4 assembly, UI-01/03/04). Mounts the full shell over the
// MSW seed (xterm/WS/ResizeObserver mocked — jsdom can't lay out a terminal) and
// proves: the four surfaces render (Navbar brand + sidebar rows + status counts),
// `+ New workspace` opens the modal, and a theme swatch switches the `data-theme`
// root across all four themes (criterion 1). The terminal grid empty-state is the
// default (no persisted layout).
//
// The first-run gate (SETUP-06) sits in front of the shell: App reads useSetupState
// and renders a themed-blank loading root until the gate resolves. The default MSW
// /setup/state double reports a CONFIGURED Burrow (non-null setupCompletedAt) so the
// normal shell renders; each test first awaits the shell landmark before asserting.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { installMockWebSocket } from "../tests/helpers/mockWebSocket";
import { resetXtermMocks } from "../tests/helpers/mockXterm";
import { installMockResizeObserver } from "../tests/helpers/resizeObserver";
import { server } from "../tests/msw/server";
import { App } from "./App";
import { useLayoutStore } from "./store/layoutStore";

function envelope<T>(data: T) {
	return {
		data,
		meta: { requestId: "test-request", timestamp: "2026-06-10T00:00:00Z" },
		error: null,
	};
}

vi.mock("@xterm/xterm", () => import("../tests/helpers/mockXterm"));
vi.mock("@xterm/addon-fit", () => import("../tests/helpers/mockXterm"));
vi.mock("@xterm/xterm/css/xterm.css", () => ({}));

function renderApp() {
	const client = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	const wrapper = ({ children }: { children: ReactNode }) => (
		<QueryClientProvider client={client}>{children}</QueryClientProvider>
	);
	return render(<App />, { wrapper });
}

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

describe("App shell — assembly (UI-01/03/04)", () => {
	it("renders the four surfaces: navbar brand, sidebar rows, grid empty-state, status counts", async () => {
		renderApp();
		// Navbar brand (await the gate resolving to the configured shell first).
		expect(await screen.findByText("Burrow")).toBeInTheDocument();
		// Sidebar rows (live list).
		await waitFor(() =>
			expect(screen.getByText("project-eta")).toBeInTheDocument(),
		);
		// Grid empty-state (no persisted layout).
		expect(screen.getByText("No open terminals")).toBeInTheDocument();
		// Status-bar counts.
		await waitFor(() =>
			expect(screen.getByTestId("count-running")).toHaveTextContent("1"),
		);
	});

	it("the app root carries the landmark + default dark theme", async () => {
		renderApp();
		// The gate resolves to the configured shell, then the landmark is present.
		expect(
			await screen.findByRole("main", { name: "Burrow workspace manager" }),
		).toBeInTheDocument();
		const root = screen
			.getByRole("main", { name: "Burrow workspace manager" })
			.closest("[data-theme]");
		expect(root).toHaveAttribute("data-theme", "dark");
	});
});

describe("App shell — interactions (UI-03, criterion 1)", () => {
	it("`+ New workspace` opens the modal", async () => {
		renderApp();
		// Await the configured shell, then assert no dialog before opening one.
		const newWorkspace = await screen.findByRole("button", {
			name: /New workspace/,
		});
		expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
		fireEvent.click(newWorkspace);
		const dialog = await screen.findByRole("dialog");
		// The dialog is titled "New workspace" (its aria-label/title).
		expect(dialog).toHaveAccessibleName("New workspace");
	});

	it("a theme swatch switches the data-theme root (criterion 1)", async () => {
		renderApp();
		// Await the configured shell so the landmark (and theme swatches) are present.
		const root = (
			await screen.findByRole("main", { name: "Burrow workspace manager" })
		).closest("[data-theme]") as HTMLElement;
		expect(root).toHaveAttribute("data-theme", "dark");
		fireEvent.click(screen.getByRole("button", { name: "Light theme" }));
		expect(root).toHaveAttribute("data-theme", "light");
		fireEvent.click(screen.getByRole("button", { name: "Medium theme" }));
		expect(root).toHaveAttribute("data-theme", "medium");
	});
});

describe("App first-run gate — replaces the shell (SETUP-06, WR-04)", () => {
	it("renders ONLY the SetupWizard (NOT the workspace shell) when setupCompletedAt is null", async () => {
		// Override the default (configured) /setup/state with an UNCONFIGURED Burrow.
		server.use(
			http.get("/api/v1/setup/state", () =>
				HttpResponse.json(envelope({ setupCompletedAt: null })),
			),
		);
		renderApp();

		// The hard gate is present...
		expect(
			await screen.findByRole("dialog", { name: "Set up Burrow" }),
		).toBeInTheDocument();
		// ...and the workspace shell (landmark + list + new-workspace CTA) is NOT.
		expect(
			screen.queryByRole("main", { name: "Burrow workspace manager" }),
		).not.toBeInTheDocument();
		expect(screen.queryByText("project-eta")).not.toBeInTheDocument();
		expect(
			screen.queryByRole("button", { name: /New workspace/ }),
		).not.toBeInTheDocument();
	});

	it("renders the shell (NOT the gate) when setupCompletedAt is non-null", async () => {
		// The default MSW double already reports a configured Burrow.
		renderApp();
		expect(
			await screen.findByRole("main", { name: "Burrow workspace manager" }),
		).toBeInTheDocument();
		// The setup gate is absent on the configured branch.
		expect(
			screen.queryByRole("dialog", { name: "Set up Burrow" }),
		).not.toBeInTheDocument();
	});
});
