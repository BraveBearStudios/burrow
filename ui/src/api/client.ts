// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// Typed fetch wrapper for the control plane. Every /api/v1 response uses the
// standard {data, meta, error} envelope (api/lib/envelope.py); this unwraps it,
// throwing a typed ApiError when `error` is non-null so callers branch on
// error.code (e.g. capacity_exceeded, illegal_transition) without re-parsing.

import type { ApiEnvelope } from "../types/workspace";

/** Thrown when the envelope carries a non-null `error`. Carries the stable code. */
export class ApiError extends Error {
	readonly code: string;

	constructor(code: string, message: string) {
		super(message);
		this.name = "ApiError";
		this.code = code;
	}
}

/**
 * Fetch `/api/v1{path}`, unwrap the standard envelope, and return `data`.
 * Throws {@link ApiError} when the envelope reports an error.
 */
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
	const res = await fetch(`/api/v1${path}`, {
		...init,
		headers: { "content-type": "application/json", ...init?.headers },
	});
	const body = (await res.json()) as ApiEnvelope<T>;
	if (body.error) {
		throw new ApiError(body.error.code, body.error.message);
	}
	return body.data as T;
}
