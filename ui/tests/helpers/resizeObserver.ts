// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// jsdom has no ResizeObserver. This stub records observe/disconnect so a test can
// (a) drive a resize callback manually (fit-on-resize, TERM-05) and (b) assert the
// live-observer count returns to zero after unmount (no leak, TERM-07).

export type ResizeCallback = (entries: unknown[]) => void;

export class MockResizeObserver {
	/** Observers that have been constructed and not yet disconnected. */
	static live = new Set<MockResizeObserver>();
	/** Every observer ever constructed (newest last). */
	static instances: MockResizeObserver[] = [];

	readonly callback: ResizeCallback;
	readonly observed: Element[] = [];
	disconnected = false;

	constructor(callback: ResizeCallback) {
		this.callback = callback;
		MockResizeObserver.live.add(this);
		MockResizeObserver.instances.push(this);
	}

	observe(target: Element): void {
		this.observed.push(target);
	}

	unobserve(target: Element): void {
		const i = this.observed.indexOf(target);
		if (i >= 0) {
			this.observed.splice(i, 1);
		}
	}

	disconnect(): void {
		this.disconnected = true;
		MockResizeObserver.live.delete(this);
	}

	/** Drive a resize: fire the callback as the browser would on a size change. */
	trigger(): void {
		this.callback([{ target: this.observed[0] }]);
	}
}

/** Install MockResizeObserver globally and reset its counters. */
export function installMockResizeObserver(): typeof MockResizeObserver {
	MockResizeObserver.live = new Set();
	MockResizeObserver.instances = [];
	// biome-ignore lint/suspicious/noExplicitAny: test-only global swap
	(globalThis as any).ResizeObserver = MockResizeObserver;
	return MockResizeObserver;
}

/** Number of observers still live (constructed, not disconnected). */
export function liveObserverCount(): number {
	return MockResizeObserver.live.size;
}
