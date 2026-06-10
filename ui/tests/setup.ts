// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// Vitest global setup: install the jest-dom matchers and run the MSW server for
// every test so Tier-2 component tests get /api/v1 mocking for free. Unhandled
// requests error so a missing handler surfaces instead of silently hanging.
import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./msw/server";

// Node 25 auto-exposes a non-functional built-in `localStorage` that shadows
// jsdom's Web Storage (no getItem/setItem/clear), so zustand `persist` and the
// layoutStore tests can't round-trip. Install a spec-compliant in-memory Storage
// when the active one is broken, on both globalThis and window (same ref).
if (typeof globalThis.localStorage?.getItem !== "function") {
	class MemoryStorage implements Storage {
		private map = new Map<string, string>();
		get length(): number {
			return this.map.size;
		}
		clear(): void {
			this.map.clear();
		}
		getItem(key: string): string | null {
			return this.map.has(key) ? (this.map.get(key) as string) : null;
		}
		key(index: number): string | null {
			return [...this.map.keys()][index] ?? null;
		}
		removeItem(key: string): void {
			this.map.delete(key);
		}
		setItem(key: string, value: string): void {
			this.map.set(key, String(value));
		}
	}
	const storage = new MemoryStorage();
	Object.defineProperty(globalThis, "localStorage", {
		configurable: true,
		value: storage,
	});
	if (typeof window !== "undefined") {
		Object.defineProperty(window, "localStorage", {
			configurable: true,
			value: storage,
		});
	}
}

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
