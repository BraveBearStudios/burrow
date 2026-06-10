// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// Shared test double for the browser WebSocket the useTerminal hook owns. It
// captures every frame the hook sends, exposes emit* helpers to drive the
// onopen/onmessage/onclose/onerror lifecycle deterministically, and honors the
// `binaryType = "arraybuffer"` the hook sets (so OUTPUT frames arrive as
// ArrayBuffer, matching the real browser). Reused by Task-1 happy-path,
// Task-3 reconnect/dispose, and any later WS test.

export type WsListener = (event: unknown) => void;

const enc = new TextEncoder();

/** A controllable WebSocket stand-in. Construction is recorded on `instances`. */
export class MockWebSocket {
	static readonly CONNECTING = 0 as const;
	static readonly OPEN = 1 as const;
	static readonly CLOSING = 2 as const;
	static readonly CLOSED = 3 as const;

	/** Every MockWebSocket built since the last reset (newest last). */
	static instances: MockWebSocket[] = [];

	readonly CONNECTING = 0;
	readonly OPEN = 1;
	readonly CLOSING = 2;
	readonly CLOSED = 3;

	readonly url: string;
	binaryType: "arraybuffer" | "blob" = "blob";
	readyState = 0;

	/** Frames passed to send(), newest last (Uint8Array / string as the hook sent). */
	readonly sent: Array<Uint8Array | string> = [];
	/** Set true when the hook calls close(). */
	closed = false;
	closeCode: number | undefined;

	onopen: WsListener | null = null;
	onmessage: WsListener | null = null;
	onclose: WsListener | null = null;
	onerror: WsListener | null = null;

	constructor(url: string) {
		this.url = url;
		MockWebSocket.instances.push(this);
	}

	send(frame: Uint8Array | string): void {
		this.sent.push(frame);
	}

	close(code?: number): void {
		this.closed = true;
		this.closeCode = code;
		this.readyState = this.CLOSED;
	}

	// ── test drivers ─────────────────────────────────────────────────────────

	/** Fire onopen (sets readyState OPEN first, like the browser). */
	emitOpen(): void {
		this.readyState = this.OPEN;
		this.onopen?.(new Event("open"));
	}

	/**
	 * Fire onmessage with `data`. Strings pass through; a Uint8Array is delivered
	 * as an ArrayBuffer when binaryType is "arraybuffer" (matching the browser),
	 * otherwise as the raw bytes.
	 */
	emitMessage(data: Uint8Array | string): void {
		let payload: ArrayBuffer | string;
		if (typeof data === "string") {
			payload = data;
		} else if (this.binaryType === "arraybuffer") {
			payload = data.buffer.slice(
				data.byteOffset,
				data.byteOffset + data.byteLength,
			) as ArrayBuffer;
		} else {
			payload = data as unknown as ArrayBuffer;
		}
		this.onmessage?.({ data: payload } as MessageEvent);
	}

	/** Convenience: emit a ttyd OUTPUT frame ('0' + text) as the server would. */
	emitOutput(text: string): void {
		const body = enc.encode(text);
		const frame = new Uint8Array(body.length + 1);
		frame[0] = 0x30; // '0'
		frame.set(body, 1);
		this.emitMessage(frame);
	}

	/** Fire onclose with a close code (1006 = abnormal/dropped by default). */
	emitClose(code = 1006): void {
		this.readyState = this.CLOSED;
		this.onclose?.({ code } as CloseEvent);
	}

	/** Fire onerror. */
	emitError(): void {
		this.onerror?.(new Event("error"));
	}
}

/** Install MockWebSocket as the global WebSocket and reset its instance list. */
export function installMockWebSocket(): typeof MockWebSocket {
	MockWebSocket.instances = [];
	// biome-ignore lint/suspicious/noExplicitAny: test-only global swap
	(globalThis as any).WebSocket = MockWebSocket;
	return MockWebSocket;
}

/** The most recently constructed MockWebSocket (the hook's current socket). */
export function lastSocket(): MockWebSocket {
	const socket = MockWebSocket.instances.at(-1);
	if (!socket) {
		throw new Error("No MockWebSocket has been constructed yet");
	}
	return socket;
}

/** Decode a captured frame (Uint8Array or string) to a string for assertions. */
export function frameText(frame: Uint8Array | string): string {
	return typeof frame === "string" ? frame : new TextDecoder().decode(frame);
}
