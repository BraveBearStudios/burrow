// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// ttyd `tty` subprotocol frame builders + opcode constants. Verified against
// current ttyd source (02-RESEARCH Pattern 1/2): the xterm client owns the
// protocol and emits these frames; the backend proxy is a dumb, type-preserving
// relay that forwards them verbatim (SC-7 — never re-encode).

/** WebSocket subprotocol negotiated with ttyd. */
export const TTYD_SUBPROTOCOL = "tty";

/** Client → server command opcodes (single ASCII byte prefix). */
export const ClientCommand = {
	INPUT: "0",
	RESIZE_TERMINAL: "1",
	PAUSE: "2",
	RESUME: "3",
} as const;

/** Server → client command opcodes. */
export const ServerCommand = {
	OUTPUT: "0",
	SET_WINDOW_TITLE: "1",
	SET_PREFERENCES: "2",
} as const;

const enc = new TextEncoder();

/**
 * The first frame ttyd expects: JSON `{AuthToken, columns, rows}` sent as encoded
 * bytes (dispatched by ttyd on a leading `{`). v1 is no-auth so AuthToken is "".
 */
export function initFrame(columns: number, rows: number): Uint8Array {
	return enc.encode(JSON.stringify({ AuthToken: "", columns, rows }));
}

/** INPUT frame: `'0'` (0x30) prefix byte + the UTF-8 bytes of `data`. */
export function inputFrame(data: string): Uint8Array {
	const d = enc.encode(data);
	const frame = new Uint8Array(d.length + 1);
	frame[0] = 0x30; // '0'
	frame.set(d, 1);
	return frame;
}

/** RESIZE_TERMINAL frame: `'1'` prefix + JSON `{columns, rows}`. */
export function resizeFrame(columns: number, rows: number): Uint8Array {
	return enc.encode(
		`${ClientCommand.RESIZE_TERMINAL}${JSON.stringify({ columns, rows })}`,
	);
}
