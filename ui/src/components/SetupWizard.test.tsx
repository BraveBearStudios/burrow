// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// SetupWizard tests (SETUP-04/06 + CRED-03). Drives the binding 13-UI-SPEC first-run
// gate over MSW: the gate renders the "Set up Burrow" dialog with the step-1 `Validate
// connection` CTA; a successful test-connection AUTO-ADVANCES to the `Verify template`
// step; a setup_auth_failed envelope surfaces the mapped token-free copy with the Host
// field still present (inline retry); a success=false result renders the mono
// missing-privilege list (NOT an --err strip); the credential steps set the in-memory
// admin secret (never localStorage) and save credentials with the X-Burrow-Admin
// header; the full 1..6 walk fires POST /setup/complete AFTER POST /workspaces
// (complete-after-create ordering); and Escape does NOTHING (non-dismissible gate).

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
import { useAdminStore } from "../store/useAdminStore";
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

/** A handler that accepts the first-run admin-secret set (step 4). */
function adminSecretOk() {
	return http.post("/api/v1/setup/admin-secret", () =>
		HttpResponse.json(envelope({ adminSecretSet: true })),
	);
}

/** A handler that accepts the credential save + returns status (step 5). */
function credentialsOk() {
	return http.post("/api/v1/setup/credentials", () =>
		HttpResponse.json(
			envelope({
				proxmoxTokenSet: true,
				proxmoxTokenLast4: "alue",
				gitTokenSet: false,
				gitTokenLast4: null,
				updatedAt: "2026-06-10T02:30:00Z",
			}),
		),
	);
}

/** Fill + submit the step-4 admin-secret fields, then wait for the step-5 CTA. */
async function passAdminSecret() {
	fireEvent.change(screen.getByLabelText("Admin secret"), {
		target: { value: "admin-secret-1" },
	});
	fireEvent.change(screen.getByLabelText("Confirm admin secret"), {
		target: { value: "admin-secret-1" },
	});
	fireEvent.click(screen.getByRole("button", { name: "Set admin secret" }));
	await screen.findByRole("button", { name: "Save credentials" });
}

/** Fill + submit the step-5 credentials fields, then wait for the step-6 CTA. */
async function passCredentials() {
	fireEvent.change(screen.getByLabelText("Proxmox token value"), {
		target: { value: "pve-token-value" },
	});
	fireEvent.click(screen.getByRole("button", { name: "Save credentials" }));
	await screen.findByRole("button", { name: "Create workspace" });
}

/** True when `value` appears in ANY localStorage cell (leak assertion). */
function isInLocalStorage(value: string): boolean {
	for (let i = 0; i < localStorage.length; i++) {
		const key = localStorage.key(i);
		if (key && (localStorage.getItem(key) ?? "").includes(value)) {
			return true;
		}
	}
	return false;
}

beforeEach(() => {
	localStorage.clear();
	// The admin store is a module singleton — reset it so a secret set in one test
	// never bleeds into the next.
	useAdminStore.getState().clear();
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

describe("SetupWizard — credential steps (CRED-03)", () => {
	/** Walk steps 1..3 so the wizard sits on step 4 (admin secret). */
	async function walkToAdminSecret() {
		server.use(connectionOk(), templateOk(), healthOk());
		renderWizard();
		fillConnection();
		fireEvent.click(
			screen.getByRole("button", { name: "Validate connection" }),
		);
		await screen.findByRole("button", { name: "Verify template" });
		fireEvent.change(screen.getByLabelText("Template VMID"), {
			target: { value: "9000" },
		});
		fireEvent.change(screen.getByLabelText("Node"), {
			target: { value: "pve" },
		});
		fireEvent.click(screen.getByRole("button", { name: "Verify template" }));
		await screen.findByRole("button", { name: "Set admin secret" });
	}

	it("sets the admin secret in memory only (NOT localStorage) and advances to credentials", async () => {
		server.use(adminSecretOk(), credentialsOk());
		await walkToAdminSecret();
		await passAdminSecret();

		// Advanced to step 5 (credentials).
		expect(
			screen.getByRole("button", { name: "Save credentials" }),
		).toBeInTheDocument();
		// The secret is held in the in-memory store...
		expect(useAdminStore.getState().secret).toBe("admin-secret-1");
		// ...and NEVER written to any web storage.
		expect(isInLocalStorage("admin-secret-1")).toBe(false);
	});

	it("saves the Proxmox token with the X-Burrow-Admin header, then advances to create", async () => {
		type SaveBody = { proxmoxTokenValue?: string; gitToken?: string };
		let sentHeader: string | null = null;
		let sentBody: SaveBody | null = null;
		server.use(
			adminSecretOk(),
			http.post("/api/v1/setup/credentials", async ({ request }) => {
				sentHeader = request.headers.get("X-Burrow-Admin");
				sentBody = (await request.json()) as SaveBody;
				return HttpResponse.json(
					envelope({
						proxmoxTokenSet: true,
						proxmoxTokenLast4: "alue",
						gitTokenSet: false,
						gitTokenLast4: null,
						updatedAt: "2026-06-10T02:30:00Z",
					}),
				);
			}),
		);
		await walkToAdminSecret();
		await passAdminSecret();
		await passCredentials();

		// Advanced to step 6 (create) once credentials saved.
		expect(
			screen.getByRole("button", { name: "Create workspace" }),
		).toBeInTheDocument();
		expect(sentHeader).toBe("admin-secret-1");
		expect(sentBody).toEqual({ proxmoxTokenValue: "pve-token-value" });
	});
});

describe("SetupWizard — complete-after-create ordering (SETUP-06)", () => {
	it("POSTs /setup/complete AFTER /workspaces on the step-6 create success", async () => {
		const callOrder: string[] = [];
		server.use(
			connectionOk(),
			templateOk(),
			healthOk(),
			adminSecretOk(),
			credentialsOk(),
			http.post("/api/v1/workspaces", async ({ request }) => {
				callOrder.push("workspaces");
				const body = (await request.json()) as { name: string };
				return HttpResponse.json(
					envelope({
						id: "ws-created",
						name: body.name,
						// ADR-0017: create resolves on a 202 + `creating` row.
						status: "creating",
						vmid: 110,
						node: "node1",
						lxcIp: null,
						projectRepo: "github.com/acme/omega",
						projectBranch: "main",
						pluginSet: "default",
						createdAt: "2026-06-10T02:00:00Z",
						stoppedAt: null,
						destroyedAt: null,
						deletedAt: null,
					}),
					{ status: 202 },
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

		// Step 1 -> 2.
		fillConnection();
		fireEvent.click(
			screen.getByRole("button", { name: "Validate connection" }),
		);
		await screen.findByRole("button", { name: "Verify template" });

		// Step 2 -> 3.
		fireEvent.change(screen.getByLabelText("Template VMID"), {
			target: { value: "9000" },
		});
		fireEvent.change(screen.getByLabelText("Node"), {
			target: { value: "pve" },
		});
		fireEvent.click(screen.getByRole("button", { name: "Verify template" }));

		// Step 3 auto-probes on mount and (both ok) auto-advances to step 4.
		await screen.findByRole("button", { name: "Set admin secret" });

		// Steps 4 -> 5 -> 6 (admin secret, then credentials).
		await passAdminSecret();
		await passCredentials();

		// Step 6 create -> complete.
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

describe("SetupWizard — complete-after-create failure (SETUP-06, WR-01)", () => {
	it("a failed /setup/complete latches the create and retries ONLY complete (no duplicate workspace)", async () => {
		const workspaceCalls: string[] = [];
		let completeAttempts = 0;
		server.use(
			connectionOk(),
			templateOk(),
			healthOk(),
			adminSecretOk(),
			credentialsOk(),
			http.post("/api/v1/workspaces", async ({ request }) => {
				workspaceCalls.push("workspaces");
				const body = (await request.json()) as { name: string };
				return HttpResponse.json(
					envelope({
						id: "ws-created",
						name: body.name,
						// ADR-0017: create resolves on a 202 + `creating` row.
						status: "creating",
						vmid: 110,
						node: "node1",
						lxcIp: null,
						projectRepo: "github.com/acme/omega",
						projectBranch: "main",
						pluginSet: "default",
						createdAt: "2026-06-10T02:00:00Z",
						stoppedAt: null,
						destroyedAt: null,
						deletedAt: null,
					}),
					{ status: 202 },
				);
			}),
			// The first /setup/complete fails; the second (retry) succeeds.
			http.post("/api/v1/setup/complete", () => {
				completeAttempts += 1;
				if (completeAttempts === 1) {
					return errorEnvelope("internal_error", "Boom.", 500);
				}
				return HttpResponse.json(
					envelope({ setupCompletedAt: "2026-06-10T03:00:00Z" }),
				);
			}),
		);
		renderWizard();

		// Walk 1 -> 2 -> 3 -> 4.
		fillConnection();
		fireEvent.click(
			screen.getByRole("button", { name: "Validate connection" }),
		);
		await screen.findByRole("button", { name: "Verify template" });
		fireEvent.change(screen.getByLabelText("Template VMID"), {
			target: { value: "9000" },
		});
		fireEvent.change(screen.getByLabelText("Node"), {
			target: { value: "pve" },
		});
		fireEvent.click(screen.getByRole("button", { name: "Verify template" }));
		await screen.findByRole("button", { name: "Set admin secret" });

		// Steps 4 -> 5 -> 6 (admin secret, then credentials).
		await passAdminSecret();
		await passCredentials();

		// Step 6 — create succeeds but /setup/complete fails.
		fireEvent.change(screen.getByLabelText("Name"), {
			target: { value: "project-omega" },
		});
		fireEvent.change(screen.getByLabelText("Git repo"), {
			target: { value: "github.com/acme/omega" },
		});
		fireEvent.click(screen.getByRole("button", { name: "Create workspace" }));

		// The failure is surfaced and the CTA latches to a complete-only retry.
		const retry = await screen.findByRole("button", { name: "Complete setup" });
		expect(
			screen.getByText("Workspace created, but finishing setup failed. Retry."),
		).toBeInTheDocument();

		// Retry: this must call /setup/complete again, NOT re-create the workspace.
		fireEvent.click(retry);
		await waitFor(() => expect(completeAttempts).toBe(2));
		// The workspace was created EXACTLY once across the whole flow (no duplicate).
		expect(workspaceCalls).toEqual(["workspaces"]);
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
