// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// SetupWizard tests (SETUP-04/06). Drives the binding 13-UI-SPEC first-run gate over
// MSW: the gate renders the "Set up Burrow" dialog with the step-1 `Validate
// connection` CTA; a successful test-connection AUTO-ADVANCES to the `Verify
// template` step; a setup_auth_failed envelope surfaces the mapped token-free copy
// with the Host field still present (inline retry); a success=false result renders
// the mono missing-privilege list (NOT an --err strip); the full 1→2→3→4 walk fires
// POST /setup/complete AFTER POST /workspaces (complete-after-create ordering); and
// Escape does NOTHING (the gate is a non-dismissible hard block).

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
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { server } from "../../tests/msw/server";
import { SetupWizard } from "./SetupWizard";

function envelope<T>(data: T) {
	return {
		data,
		meta: { requestId: "test-request", timestamp: "2026-06-10T00:00:00Z" },
		error: null,
	};
}

function errorEnvelope(code: string, message: string, status: number) {
	return HttpResponse.json(
		{
			data: null,
			meta: { requestId: "test-request", timestamp: "2026-06-10T00:00:00Z" },
			error: { code, message },
		},
		{ status },
	);
}

function renderWizard() {
	const client = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	const wrapper = ({ children }: { children: ReactNode }) => (
		<QueryClientProvider client={client}>{children}</QueryClientProvider>
	);
	return render(<SetupWizard />, { wrapper });
}

/** Fill the four step-1 connection fields with valid values. */
function fillConnection() {
	fireEvent.change(screen.getByLabelText("Host"), {
		target: { value: "https://pve.lan:8006" },
	});
	fireEvent.change(screen.getByLabelText("User"), {
		target: { value: "burrow@pve" },
	});
	fireEvent.change(screen.getByLabelText("Token name"), {
		target: { value: "burrow-token" },
	});
	fireEvent.change(screen.getByLabelText("Token value"), {
		target: { value: "s3cr3t-token-value" },
	});
}

/** A handler that passes the connection step (token valid, no missing privileges). */
function connectionOk() {
	return http.post("/api/v1/setup/test-connection", () =>
		HttpResponse.json(envelope({ success: true, missingPrivileges: [] })),
	);
}

/** A handler that passes the template step (usable=true). */
function templateOk() {
	return http.post("/api/v1/setup/verify-template", () =>
		HttpResponse.json(
			envelope({ exists: true, usable: true, vmid: 9000, node: "pve" }),
		),
	);
}

/** A handler that reports both dependencies healthy so step 3 auto-advances. */
function healthOk() {
	return http.get("/api/v1/health", () =>
		HttpResponse.json(envelope({ status: "ok", db: "ok", compute: "ok" })),
	);
}

beforeEach(() => {
	localStorage.clear();
});

afterEach(() => {
	cleanup();
});

describe("SetupWizard — gate render (SETUP-06)", () => {
	it("renders the `Set up Burrow` dialog with the step-1 `Validate connection` CTA", () => {
		renderWizard();
		expect(
			screen.getByRole("dialog", { name: "Set up Burrow" }),
		).toBeInTheDocument();
		expect(
			screen.getByRole("button", { name: "Validate connection" }),
		).toBeInTheDocument();
		// Re-probe lands on step 1 for an unconfigured app: step-1 fields are present.
		expect(screen.getByLabelText("Host")).toBeInTheDocument();
	});
});

describe("SetupWizard — step-1 connection (SETUP-04)", () => {
	it("auto-advances to step 2 on a successful test-connection", async () => {
		server.use(connectionOk());
		renderWizard();
		fillConnection();
		fireEvent.click(
			screen.getByRole("button", { name: "Validate connection" }),
		);

		// Auto-advance: the step-2 `Verify template` CTA appears.
		expect(
			await screen.findByRole("button", { name: "Verify template" }),
		).toBeInTheDocument();
	});

	it("shows the mapped setup_auth_failed copy and keeps the inputs for inline retry", async () => {
		server.use(
			http.post("/api/v1/setup/test-connection", () =>
				errorEnvelope(
					"setup_auth_failed",
					"The Proxmox token was rejected.",
					400,
				),
			),
		);
		renderWizard();
		fillConnection();
		fireEvent.click(
			screen.getByRole("button", { name: "Validate connection" }),
		);

		expect(
			await screen.findByText("The Proxmox token was rejected."),
		).toBeInTheDocument();
		// Inline retry: the Host field (and the step-1 CTA) remain present.
		expect(screen.getByLabelText("Host")).toBeInTheDocument();
		expect(
			screen.getByRole("button", { name: "Validate connection" }),
		).toBeInTheDocument();
	});

	it("renders the missing-privilege list (NOT an error strip) on success=false", async () => {
		server.use(
			http.post("/api/v1/setup/test-connection", () =>
				HttpResponse.json(
					envelope({
						success: false,
						missingPrivileges: ["VM.Allocate", "VM.Clone"],
					}),
				),
			),
		);
		renderWizard();
		fillConnection();
		fireEvent.click(
			screen.getByRole("button", { name: "Validate connection" }),
		);

		expect(
			await screen.findByText("Token is valid but missing privileges:"),
		).toBeInTheDocument();
		expect(screen.getByText("VM.Allocate")).toBeInTheDocument();
		expect(screen.getByText("VM.Clone")).toBeInTheDocument();
		// Still on step 1 (no auto-advance): the step-1 CTA stays.
		expect(
			screen.getByRole("button", { name: "Validate connection" }),
		).toBeInTheDocument();
	});
});

describe("SetupWizard — complete-after-create ordering (SETUP-06)", () => {
	it("POSTs /setup/complete AFTER /workspaces on the step-4 create success", async () => {
		const callOrder: string[] = [];
		server.use(
			connectionOk(),
			templateOk(),
			healthOk(),
			http.post("/api/v1/workspaces", async ({ request }) => {
				callOrder.push("workspaces");
				const body = (await request.json()) as { name: string };
				return HttpResponse.json(
					envelope({
						id: "ws-created",
						name: body.name,
						status: "running",
						vmid: 110,
						node: "node1",
						lxcIp: "10.99.0.110",
						projectRepo: "github.com/acme/omega",
						projectBranch: "main",
						pluginSet: "default",
						createdAt: "2026-06-10T02:00:00Z",
						stoppedAt: null,
						destroyedAt: null,
						deletedAt: null,
					}),
				);
			}),
			http.post("/api/v1/setup/complete", () => {
				callOrder.push("complete");
				return HttpResponse.json(
					envelope({ setupCompletedAt: "2026-06-10T03:00:00Z" }),
				);
			}),
		);
		renderWizard();

		// Step 1 → 2.
		fillConnection();
		fireEvent.click(
			screen.getByRole("button", { name: "Validate connection" }),
		);
		await screen.findByRole("button", { name: "Verify template" });

		// Step 2 → 3.
		fireEvent.change(screen.getByLabelText("Template VMID"), {
			target: { value: "9000" },
		});
		fireEvent.change(screen.getByLabelText("Node"), {
			target: { value: "pve" },
		});
		fireEvent.click(screen.getByRole("button", { name: "Verify template" }));

		// Step 3 auto-probes on mount and (both ok) auto-advances to step 4.
		await screen.findByRole("button", { name: "Create workspace" });

		// Step 4 → create → complete.
		fireEvent.change(screen.getByLabelText("Name"), {
			target: { value: "project-omega" },
		});
		fireEvent.change(screen.getByLabelText("Git repo"), {
			target: { value: "github.com/acme/omega" },
		});
		fireEvent.click(screen.getByRole("button", { name: "Create workspace" }));

		await waitFor(() => expect(callOrder).toEqual(["workspaces", "complete"]));
	});
});

describe("SetupWizard — hard gate (SETUP-06)", () => {
	it("does NOT close on Escape (the gate is non-dismissible)", () => {
		renderWizard();
		const dialog = screen.getByRole("dialog", { name: "Set up Burrow" });
		fireEvent.keyDown(dialog, { key: "Escape" });
		// The gate is still present — Escape is inert.
		expect(
			screen.getByRole("dialog", { name: "Set up Burrow" }),
		).toBeInTheDocument();
	});
});
