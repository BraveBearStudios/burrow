// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// CredentialsScreen tests (CRED-04/05 UI) over MSW: the admin-secret PROMPT shows
// when the in-memory store is empty; once a secret is set the status renders (set +
// last4 + updatedAt); a rotation submit POSTs with the X-Burrow-Admin header; the
// audit trail renders newest-first; a 401 `admin_unauthorized` clears the store and
// returns to the prompt; and the admin secret is NEVER written to localStorage.

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
import type { AuditEntry, CredentialStatus } from "../types/setup";
import { CredentialsScreen } from "./CredentialsScreen";

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

const STATUS: CredentialStatus = {
	proxmoxTokenSet: true,
	proxmoxTokenLast4: "cafe",
	gitTokenSet: false,
	gitTokenLast4: null,
	updatedAt: "2026-07-13T10:00:00Z",
};

const AUDIT_ENTRIES: AuditEntry[] = [
	{
		id: "a2",
		action: "credentials.update",
		target: "proxmoxToken",
		outcome: "success",
		sourceIp: "10.0.0.5",
		detail: "****cafe",
		createdAt: "2026-07-13T10:00:00Z",
	},
	{
		id: "a1",
		action: "admin.verify",
		target: null,
		outcome: "failure",
		sourceIp: "10.0.0.9",
		detail: null,
		createdAt: "2026-07-13T09:00:00Z",
	},
];

/** GET /setup/credentials → status. */
function statusOk() {
	return http.get("/api/v1/setup/credentials", () =>
		HttpResponse.json(envelope(STATUS)),
	);
}

/** GET /setup/audit → entries (newest-first). */
function auditOk() {
	return http.get("/api/v1/setup/audit", () =>
		HttpResponse.json(envelope({ entries: AUDIT_ENTRIES })),
	);
}

function renderScreen() {
	const client = new QueryClient({
		defaultOptions: { queries: { retry: false } },
	});
	const wrapper = ({ children }: { children: ReactNode }) => (
		<QueryClientProvider client={client}>{children}</QueryClientProvider>
	);
	return render(<CredentialsScreen onClose={() => {}} />, { wrapper });
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
	useAdminStore.getState().clear();
});

afterEach(() => {
	cleanup();
});

describe("CredentialsScreen — admin gate (CRED-04)", () => {
	it("prompts for the admin secret when the store is empty (no status shown)", () => {
		renderScreen();
		expect(screen.getByLabelText("Admin secret")).toBeInTheDocument();
		expect(screen.getByRole("button", { name: "Unlock" })).toBeInTheDocument();
		// The unlocked surface (rotation form) is NOT rendered yet.
		expect(
			screen.queryByRole("button", { name: "Save credentials" }),
		).not.toBeInTheDocument();
	});

	it("does not persist the admin secret to localStorage after unlocking", async () => {
		server.use(statusOk(), auditOk());
		renderScreen();
		fireEvent.change(screen.getByLabelText("Admin secret"), {
			target: { value: "admin-secret-1" },
		});
		fireEvent.click(screen.getByRole("button", { name: "Unlock" }));

		// The status loads (unlocked), so the secret drove an admin-gated fetch...
		expect(
			await screen.findByRole("button", { name: "Save credentials" }),
		).toBeInTheDocument();
		expect(useAdminStore.getState().secret).toBe("admin-secret-1");
		// ...but the secret was never written to web storage.
		expect(isInLocalStorage("admin-secret-1")).toBe(false);
	});
});

describe("CredentialsScreen — status + audit (CRED-04/05)", () => {
	it("renders credential status (set + last4 + updatedAt) once unlocked", async () => {
		server.use(statusOk(), auditOk());
		useAdminStore.getState().setSecret("admin-secret-1");
		renderScreen();

		// Proxmox is set with its last4; the value itself is never shown.
		expect(await screen.findByText("****cafe")).toBeInTheDocument();
		expect(
			screen.getByText("Last updated 2026-07-13T10:00:00Z"),
		).toBeInTheDocument();
	});

	it("renders the audit trail rows (action / target / outcome / source)", async () => {
		server.use(statusOk(), auditOk());
		useAdminStore.getState().setSecret("admin-secret-1");
		renderScreen();

		expect(await screen.findByText("credentials.update")).toBeInTheDocument();
		expect(screen.getByText("proxmoxToken")).toBeInTheDocument();
		expect(screen.getByText("admin.verify")).toBeInTheDocument();
		expect(screen.getByText("10.0.0.5")).toBeInTheDocument();
	});
});

describe("CredentialsScreen — rotation (CRED-04)", () => {
	it("submits a rotation POST carrying the X-Burrow-Admin header", async () => {
		type SaveBody = { proxmoxTokenValue?: string; gitToken?: string };
		let sentHeader: string | null = null;
		let sentBody: SaveBody | null = null;
		server.use(
			statusOk(),
			auditOk(),
			http.post("/api/v1/setup/credentials", async ({ request }) => {
				sentHeader = request.headers.get("X-Burrow-Admin");
				sentBody = (await request.json()) as SaveBody;
				return HttpResponse.json(envelope(STATUS));
			}),
		);
		useAdminStore.getState().setSecret("admin-secret-1");
		renderScreen();

		fireEvent.change(await screen.findByLabelText("Proxmox token value"), {
			target: { value: "new-pve-token" },
		});
		fireEvent.click(screen.getByRole("button", { name: "Save credentials" }));

		await waitFor(() => expect(sentHeader).toBe("admin-secret-1"));
		expect(sentBody).toEqual({ proxmoxTokenValue: "new-pve-token" });
	});
});

describe("CredentialsScreen — admin-auth rejection (CRED-02)", () => {
	it("clears the store and returns to the prompt on a 401 admin_unauthorized", async () => {
		server.use(
			http.get("/api/v1/setup/credentials", () =>
				errorEnvelope(
					"admin_unauthorized",
					"Admin authorization required.",
					401,
				),
			),
			http.get("/api/v1/setup/audit", () =>
				errorEnvelope(
					"admin_unauthorized",
					"Admin authorization required.",
					401,
				),
			),
		);
		useAdminStore.getState().setSecret("wrong-secret");
		renderScreen();

		// The rejected gate clears the in-memory secret...
		await waitFor(() => expect(useAdminStore.getState().secret).toBeNull());
		// ...and the prompt (with the re-enter message) is shown again.
		expect(
			await screen.findByRole("button", { name: "Unlock" }),
		).toBeInTheDocument();
		expect(
			screen.getByText(
				"Admin authorization failed. Re-enter the admin secret.",
			),
		).toBeInTheDocument();
	});
});
