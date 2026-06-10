// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// App shell test (Wave 4 assembly, UI-01/03/04). Mounts the full shell over the
// MSW seed (xterm/WS/ResizeObserver mocked — jsdom can't lay out a terminal) and
// proves: the four surfaces render (Navbar brand + sidebar rows + status counts),
// `+ New workspace` opens the modal, and a theme swatch switches the `data-theme`
// root across all four themes (criterion 1). The terminal grid empty-state is the
// default (no persisted layout).

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { installMockWebSocket } from "../tests/helpers/mockWebSocket";
import { resetXtermMocks } from "../tests/helpers/mockXterm";
import { installMockResizeObserver } from "../tests/helpers/resizeObserver";
import { App } from "./App";
import { useLayoutStore } from "./store/layoutStore";

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
		// Navbar brand.
		expect(screen.getByText("Burrow")).toBeInTheDocument();
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

	it("the app root carries the landmark + default dark theme", () => {
		renderApp();
		expect(
			screen.getByRole("main", { name: "Burrow workspace manager" }),
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
		expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
		fireEvent.click(screen.getByRole("button", { name: /New workspace/ }));
		const dialog = await screen.findByRole("dialog");
		// The dialog is titled "New workspace" (its aria-label/title).
		expect(dialog).toHaveAccessibleName("New workspace");
	});

	it("a theme swatch switches the data-theme root (criterion 1)", () => {
		renderApp();
		const root = screen
			.getByRole("main", { name: "Burrow workspace manager" })
			.closest("[data-theme]") as HTMLElement;
		expect(root).toHaveAttribute("data-theme", "dark");
		fireEvent.click(screen.getByRole("button", { name: "Light theme" }));
		expect(root).toHaveAttribute("data-theme", "light");
		fireEvent.click(screen.getByRole("button", { name: "Medium theme" }));
		expect(root).toHaveAttribute("data-theme", "medium");
	});
});
