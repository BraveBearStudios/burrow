// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// StatusBar tests (UI-04). Renders the bar over the MSW seed and proves the
// binding 02-UI-SPEC contract: running/stopped/error counts derived from the live
// workspace list (gold mono numbers), a session-uptime readout, a zero-workspaces
// state rendering 0s, and the fixed 32px height that never grows (chrome invariant
// criterion 15). MSW serves /api/v1/workspaces + /api/v1/nodes.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { server } from "../../tests/msw/server";
import { StatusBar } from "./StatusBar";

function renderBar() {
	const client = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	const wrapper = ({ children }: { children: ReactNode }) => (
		<QueryClientProvider client={client}>{children}</QueryClientProvider>
	);
	return render(<StatusBar />, { wrapper });
}

afterEach(() => {
	vi.restoreAllMocks();
});

describe("StatusBar — counts derived from the list (UI-04)", () => {
	it("shows running / stopped / error counts from the live workspace list", async () => {
		renderBar();
		// Seed: 1 running, 1 creating, 1 stopped, 1 error.
		await waitFor(() =>
			expect(screen.getByTestId("count-running")).toHaveTextContent("1"),
		);
		expect(screen.getByTestId("count-stopped")).toHaveTextContent("1");
		expect(screen.getByTestId("count-error")).toHaveTextContent("1");
	});

	it("each count number is gold mono and paired with a text label (a11y, gold discipline)", async () => {
		renderBar();
		await waitFor(() =>
			expect(screen.getByTestId("count-running")).toHaveTextContent("1"),
		);
		const running = screen.getByTestId("count-running");
		const number = within(running).getByText("1");
		expect(number).toHaveStyle({ color: "var(--gold)" });
		// Status is never color-only — a text label accompanies the count.
		expect(running).toHaveTextContent(/running/);
	});

	it("renders the session uptime readout (gold mono Xh Ym)", async () => {
		renderBar();
		const uptime = await screen.findByTestId("uptime");
		expect(uptime).toHaveTextContent(/uptime/);
		// Formatted Xh Ym (0h 0m at mount).
		expect(within(uptime).getByText(/\dh \dm/)).toBeInTheDocument();
	});
});

describe("StatusBar — zero state (UI-04)", () => {
	it("renders 0 for every count when there are no workspaces", async () => {
		server.use(
			http.get("/api/v1/workspaces", () =>
				HttpResponse.json({
					data: [],
					meta: { requestId: "t", timestamp: "2026-06-10T00:00:00Z" },
					error: null,
				}),
			),
		);
		renderBar();
		await waitFor(() =>
			expect(screen.getByTestId("count-running")).toHaveTextContent("0"),
		);
		expect(screen.getByTestId("count-stopped")).toHaveTextContent("0");
		expect(screen.getByTestId("count-error")).toHaveTextContent("0");
	});
});

describe("StatusBar — chrome invariant (criterion 15)", () => {
	it("is a fixed 32px-high bar that never grows", () => {
		renderBar();
		const bar = screen.getByRole("contentinfo");
		expect(bar).toHaveStyle({ height: "var(--h-statusbar)" });
	});
});
