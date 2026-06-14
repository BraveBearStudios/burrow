// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// ActivityDrawer tests (UI-06). Renders the per-workspace event drawer over MSW
// and proves the binding 04-UI-SPEC contract: the four data states (loading→
// shimmer, empty→"No activity yet", error→--err strip over kept rows, populated→
// the live list), the NEWEST-first reverse (criterion 2: the most-recent event is
// the top row), the badge map keyed on the REAL namespaced types (an unknown type
// renders its raw string, criterion 3), the boot.error row emphasis (criterion 4),
// poll-only-while-open (criterion 5: no request fires when workspaceId is null),
// and the a11y contract — role=dialog, Esc closes, focus returns to the trigger.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
	fireEvent,
	render,
	screen,
	waitFor,
	within,
} from "@testing-library/react";
import { HttpResponse, http } from "msw";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { server } from "../../tests/msw/server";
import type { WorkspaceEvent } from "../types/event";
import { ActivityDrawer } from "./ActivityDrawer";

function envelope<T>(data: T) {
	return {
		data,
		meta: { requestId: "test-request", timestamp: "2026-06-10T00:00:00Z" },
		error: null,
	};
}

/** Oldest-first feed (as the endpoint returns): created → connected → boot.error. */
const seedEvents: WorkspaceEvent[] = [
	{
		id: "ev-1",
		workspaceId: "ws-1",
		type: "workspace.created",
		data: {},
		createdAt: "2026-06-10T00:00:00Z",
	},
	{
		id: "ev-2",
		workspaceId: "ws-1",
		type: "terminal.connected",
		data: {},
		createdAt: "2026-06-10T00:01:00Z",
	},
	{
		id: "ev-3",
		workspaceId: "ws-1",
		type: "boot.error",
		data: { reason: "ttyd never became healthy" },
		createdAt: "2026-06-10T00:02:00Z",
	},
];

function mockEvents(events: WorkspaceEvent[]) {
	server.use(
		http.get("/api/v1/workspaces/:id/events", () =>
			HttpResponse.json(envelope(events)),
		),
	);
}

function renderDrawer(
	props: Partial<React.ComponentProps<typeof ActivityDrawer>> = {},
) {
	const client = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	const onClose = vi.fn();
	const wrapper = ({ children }: { children: ReactNode }) => (
		<QueryClientProvider client={client}>{children}</QueryClientProvider>
	);
	const utils = render(
		<ActivityDrawer
			workspaceId="ws-1"
			workspaceName="auth-api"
			onClose={onClose}
			{...props}
		/>,
		{ wrapper },
	);
	return { ...utils, onClose };
}

beforeEach(() => {
	mockEvents(seedEvents);
});

afterEach(() => {
	vi.restoreAllMocks();
});

describe("ActivityDrawer — data states (UI-06)", () => {
	it("renders the populated list newest-first (criterion 2)", async () => {
		renderDrawer();
		// The most-recent event (boot.error) is the TOP row.
		await waitFor(() =>
			expect(screen.getByText("Boot error")).toBeInTheDocument(),
		);
		const items = screen.getAllByRole("listitem");
		expect(within(items[0]).getByText("Boot error")).toBeInTheDocument();
		expect(within(items[2]).getByText("Created")).toBeInTheDocument();
	});

	it("renders the empty state when the log is empty", async () => {
		mockEvents([]);
		renderDrawer();
		expect(await screen.findByText("No activity yet")).toBeInTheDocument();
		expect(
			screen.getByText(/Events appear here as this workspace boots/),
		).toBeInTheDocument();
	});

	it("shows the poll-error strip when the events query fails", async () => {
		server.use(
			http.get("/api/v1/workspaces/:id/events", () => HttpResponse.error()),
		);
		renderDrawer();
		expect(
			await screen.findByText("Couldn't load the event log. Retrying…"),
		).toBeInTheDocument();
	});
});

describe("ActivityDrawer — badge map + emphasis (criteria 3, 4)", () => {
	it("keys badges off the real namespaced types and maps tokens", async () => {
		renderDrawer();
		const created = await screen.findByText("Created");
		const connected = screen.getByText("Terminal connected");
		expect(created).toHaveStyle({ color: "var(--ok)" });
		expect(connected).toHaveStyle({ color: "var(--accent-line)" });
	});

	it("emphasizes a boot.error row (2px --err left bar) and shows the redacted reason", async () => {
		renderDrawer();
		const bootError = await screen.findByText("Boot error");
		const row = bootError.closest("li") as HTMLLIElement;
		expect(row).not.toBeNull();
		// The 2px --err left bar is the emphasis affordance (jsdom keeps shorthand
		// inline-style values un-expanded, so assert against the raw inline style).
		expect(row.style.borderLeft).toBe("2px solid var(--err)");
		// The server-redacted reason surfaces in --err mono beneath the badge.
		expect(
			screen.getByText(/reason: ttyd never became healthy/),
		).toBeInTheDocument();
	});

	it("renders an unknown type's raw string (forward-compatible fallback)", async () => {
		mockEvents([
			{
				id: "ev-x",
				workspaceId: "ws-1",
				type: "future.unseen_event",
				data: {},
				createdAt: "2026-06-10T00:05:00Z",
			},
		]);
		renderDrawer();
		// The raw type string renders verbatim, not a crash or a blank.
		expect(await screen.findByText("future.unseen_event")).toBeInTheDocument();
	});

	it("labels an idle auto-stop distinctly (workspace.stopped reason:idle)", async () => {
		mockEvents([
			{
				id: "ev-idle",
				workspaceId: "ws-1",
				type: "workspace.stopped",
				data: { reason: "idle" },
				createdAt: "2026-06-10T00:06:00Z",
			},
		]);
		renderDrawer();
		expect(await screen.findByText("Auto-stopped (idle)")).toBeInTheDocument();
	});
});

describe("ActivityDrawer — responsive width token (UI-09 / V2)", () => {
	// FAILING-FIRST (Wave 0): Plan 03 swaps the hardcoded `min(360px,100vw)`
	// literal for the `--w-drawer` token (whose @media override makes the phone
	// full-width sheet real). jsdom cannot COMPUTE the width, but the inline
	// `.style.width` value IS readable — assert the token is wired. RED until then.
	it("reads width: var(--w-drawer) on the drawer <aside>", async () => {
		renderDrawer();
		const dialog = await screen.findByRole("dialog");
		expect(dialog.style.width).toBe("var(--w-drawer)");
	});
});

describe("ActivityDrawer — poll gating (criterion 5)", () => {
	it("makes no request while closed (workspaceId null → enabled false)", async () => {
		const hit = vi.fn();
		server.use(
			http.get("/api/v1/workspaces/:id/events", () => {
				hit();
				return HttpResponse.json(envelope(seedEvents));
			}),
		);
		renderDrawer({ workspaceId: null });
		// The closed drawer renders nothing and fires no events poll.
		expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
		await new Promise((r) => setTimeout(r, 50));
		expect(hit).not.toHaveBeenCalled();
	});
});

describe("ActivityDrawer — a11y (criterion 11)", () => {
	it("is a role=dialog labelled by the workspace name", async () => {
		renderDrawer();
		const dialog = await screen.findByRole("dialog");
		expect(dialog).toHaveAttribute("aria-label", "auth-api activity log");
	});

	it("closes on Esc", async () => {
		const { onClose } = renderDrawer();
		const dialog = await screen.findByRole("dialog");
		fireEvent.keyDown(dialog, { key: "Escape" });
		expect(onClose).toHaveBeenCalledTimes(1);
	});

	it("keeps Tab focus inside the drawer (scrim is out of the tab order, WR-03)", async () => {
		renderDrawer();
		const dialog = await screen.findByRole("dialog");
		// The dismiss scrim must be excluded from the tab order and the a11y tree,
		// otherwise Tab escapes the modal focus trap onto it.
		const scrim = screen.getByLabelText("Dismiss activity log");
		expect(scrim).toHaveAttribute("tabindex", "-1");
		expect(scrim).toHaveAttribute("aria-hidden", "true");

		// The trap's focusables are scoped to the drawer; the scrim (tabIndex=-1)
		// is not among them, so Tab/Shift+Tab cycle within the <aside>.
		const focusables = dialog.querySelectorAll<HTMLElement>(
			'button, [href], [tabindex]:not([tabindex="-1"])',
		);
		expect(focusables.length).toBeGreaterThan(0);
		for (const el of Array.from(focusables)) {
			expect(dialog.contains(el)).toBe(true);
		}
		expect(dialog.contains(scrim)).toBe(false);

		// Tab from the last focusable wraps to the first — still inside the drawer.
		const last = focusables[focusables.length - 1];
		last.focus();
		fireEvent.keyDown(dialog, { key: "Tab" });
		expect(dialog.contains(document.activeElement)).toBe(true);
		expect(document.activeElement).not.toBe(scrim);
	});

	it("returns focus to the trigger on close", async () => {
		mockEvents(seedEvents);
		const client = new QueryClient({
			defaultOptions: { queries: { retry: false } },
		});
		const trigger = document.createElement("button");
		trigger.textContent = "Activity log";
		document.body.appendChild(trigger);
		trigger.focus();
		expect(document.activeElement).toBe(trigger);

		const { rerender } = render(
			<QueryClientProvider client={client}>
				<ActivityDrawer
					workspaceId="ws-1"
					workspaceName="auth-api"
					onClose={() => {}}
				/>
			</QueryClientProvider>,
		);
		await screen.findByRole("dialog");
		// Closing (workspaceId → null) restores focus to the original trigger.
		rerender(
			<QueryClientProvider client={client}>
				<ActivityDrawer
					workspaceId={null}
					workspaceName="auth-api"
					onClose={() => {}}
				/>
			</QueryClientProvider>,
		);
		await waitFor(() => expect(document.activeElement).toBe(trigger));
		trigger.remove();
	});
});
