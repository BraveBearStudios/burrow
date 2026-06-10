// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

import { afterEach, describe, expect, it, vi } from "vitest";
import { initFrame, inputFrame, resizeFrame } from "../lib/ttyd";
import type { ApiEnvelope, Workspace } from "../types/workspace";
import { ApiError, api } from "./client";

function mockFetchOnce(body: ApiEnvelope<unknown>): void {
	vi.stubGlobal(
		"fetch",
		vi.fn(async () => new Response(JSON.stringify(body), { status: 200 })),
	);
}

describe("api client (envelope unwrap)", () => {
	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it("test_unwraps_data: returns body.data when error is null", async () => {
		const ws: Workspace = {
			id: "w1",
			name: "demo",
			status: "running",
			vmid: 101,
			node: "node1",
			lxcIp: "10.99.0.101",
			projectRepo: "github.com/acme/app",
			projectBranch: "main",
			pluginSet: "default",
			createdAt: "2026-06-10T00:00:00Z",
			stoppedAt: null,
			destroyedAt: null,
			deletedAt: null,
		};
		mockFetchOnce({
			data: [ws],
			meta: { requestId: "r1", timestamp: "2026-06-10T00:00:00Z" },
			error: null,
		});

		const result = await api<Workspace[]>("/workspaces");
		expect(result).toEqual([ws]);
		expect(fetch).toHaveBeenCalledWith(
			"/api/v1/workspaces",
			expect.objectContaining({}),
		);
	});

	it("test_throws_apierror: throws ApiError carrying code + message when error != null", async () => {
		mockFetchOnce({
			data: null,
			meta: { requestId: "r2", timestamp: "2026-06-10T00:00:00Z" },
			error: {
				code: "capacity_exceeded",
				message: "Node node1 is over its memory threshold.",
			},
		});

		await expect(api("/workspaces", { method: "POST" })).rejects.toMatchObject({
			code: "capacity_exceeded",
			message: "Node node1 is over its memory threshold.",
		});
		await expect(api("/workspaces", { method: "POST" })).rejects.toBeInstanceOf(
			ApiError,
		);
	});
});

describe("ttyd frame builders (verified opcodes)", () => {
	const dec = new TextDecoder();

	it("test_input_frame: inputFrame('a') is [0x30, 0x61] ('0' prefix + data byte)", () => {
		const f = inputFrame("a");
		expect(f).toBeInstanceOf(Uint8Array);
		expect(Array.from(f)).toEqual([0x30, 0x61]);
	});

	it("test_resize_frame: resizeFrame(80,24) is '1' + JSON {columns,rows}", () => {
		const f = resizeFrame(80, 24);
		const text = dec.decode(f);
		expect(text[0]).toBe("1");
		expect(JSON.parse(text.slice(1))).toEqual({ columns: 80, rows: 24 });
	});

	it("test_init_frame: initFrame(80,24) decodes to JSON with AuthToken, columns, rows", () => {
		const f = initFrame(80, 24);
		const payload = JSON.parse(dec.decode(f));
		expect(payload).toMatchObject({ AuthToken: "", columns: 80, rows: 24 });
	});
});
