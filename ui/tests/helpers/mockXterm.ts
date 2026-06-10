// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// xterm.js needs real layout (cell metrics, canvas/DOM) that jsdom can't provide,
// so the useTerminal tests mock @xterm/xterm + @xterm/addon-fit with these fakes.
// They record the surface the hook drives — open/write/onData/dispose, fit(),
// cols/rows — and expose live counts so the dispose/leak test (TERM-07) can assert
// teardown. Wire them with `vi.mock` at the top of a test file:
//
//   vi.mock("@xterm/xterm", () => import("../../tests/helpers/mockXterm"));
//   vi.mock("@xterm/addon-fit", () => import("../../tests/helpers/mockXterm"));
//   vi.mock("@xterm/xterm/css/xterm.css", () => ({}));

export type DataHandler = (data: string) => void;

/** A fake xterm Terminal recording the calls useTerminal makes against it. */
export class Terminal {
	static live = new Set<Terminal>();
	static instances: Terminal[] = [];

	/** Mutable so a fit() can change them (TERM-05: not stuck 80x24). */
	cols = 80;
	rows = 24;

	readonly options: Record<string, unknown>;
	readonly addons: unknown[] = [];
	/** Everything passed to write(), newest last. */
	readonly written: string[] = [];
	readonly dataHandlers: DataHandler[] = [];
	opened: HTMLElement | null = null;
	disposed = false;

	constructor(options: Record<string, unknown> = {}) {
		this.options = options;
		Terminal.live.add(this);
		Terminal.instances.push(this);
	}

	loadAddon(addon: { activate?: (t: Terminal) => void }): void {
		this.addons.push(addon);
		addon.activate?.(this);
	}

	open(el: HTMLElement): void {
		this.opened = el;
	}

	onData(handler: DataHandler): { dispose: () => void } {
		this.dataHandlers.push(handler);
		return { dispose: () => {} };
	}

	write(data: string | Uint8Array): void {
		this.written.push(
			typeof data === "string" ? data : new TextDecoder().decode(data),
		);
	}

	focus(): void {}

	dispose(): void {
		this.disposed = true;
		Terminal.live.delete(this);
	}

	/** Test driver: simulate a user keystroke (fires every onData handler). */
	emitData(data: string): void {
		for (const handler of this.dataHandlers) {
			handler(data);
		}
	}
}

/** A fake FitAddon whose fit() bumps the bound terminal's cols/rows once. */
export class FitAddon {
	static live = new Set<FitAddon>();

	private term: Terminal | null = null;
	fitCalls = 0;
	disposed = false;

	constructor() {
		FitAddon.live.add(this);
	}

	activate(term: Terminal): void {
		this.term = term;
	}

	fit(): void {
		this.fitCalls += 1;
		// Simulate a real fit reflowing the grid off the default 80x24 so the
		// fit-on-resize test can prove cols/rows changed (TERM-05).
		if (this.term) {
			this.term.cols = 120;
			this.term.rows = 40;
		}
	}

	dispose(): void {
		this.disposed = true;
		FitAddon.live.delete(this);
	}
}

/** Reset all xterm-mock counters between tests. */
export function resetXtermMocks(): void {
	Terminal.live = new Set();
	Terminal.instances = [];
	FitAddon.live = new Set();
}

/** The most recently constructed fake Terminal. */
export function lastTerminal(): Terminal {
	const term = Terminal.instances.at(-1);
	if (!term) {
		throw new Error("No mock Terminal has been constructed yet");
	}
	return term;
}

/** Live (undisposed) terminal count — for the leak assertion (TERM-07). */
export function liveTerminalCount(): number {
	return Terminal.live.size;
}
