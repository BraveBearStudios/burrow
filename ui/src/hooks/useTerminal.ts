// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// useTerminal owns the xterm.js + WebSocket + FitAddon + ResizeObserver lifecycle
// for one workspace terminal (TERM-05/06/07). The browser speaks ttyd's `tty`
// protocol (the backend bridge is a dumb relay): on open it sends the JSON init
// frame, sends typed input as a '0'-prefixed INPUT frame, fits/reflows on resize
// and sends a '1'-prefixed RESIZE frame, strips the leading '0' on OUTPUT before
// writing, auto-reconnects with jittered backoff behind a visible overlay, stops
// on terminal states, and disposes everything on unmount (no leaks).

import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";
import "@xterm/xterm/css/xterm.css";
import { useEffect, useRef, useState } from "react";
import { initFrame, inputFrame, ServerCommand } from "../lib/ttyd";
import type { TerminalState, WorkspaceStatus } from "../types/workspace";

/** xterm config lifted from 02-UI-SPEC Typography (tokens resolved at runtime). */
const TERM_OPTIONS = {
	fontFamily: "'JetBrains Mono', ui-monospace, monospace",
	fontSize: 12,
	lineHeight: 1.6,
	cursorBlink: true,
	theme: {
		background: cssVar("--bg-surf", "#212321"),
		foreground: cssVar("--text-sub", "#7a8e7a"),
		cursor: cssVar("--accent-line", "#5e7d5e"),
	},
} as const;

/** Read a CSS custom property off :root, falling back when unavailable (jsdom). */
function cssVar(name: string, fallback: string): string {
	if (typeof window === "undefined") {
		return fallback;
	}
	const value = getComputedStyle(document.documentElement)
		.getPropertyValue(name)
		.trim();
	return value || fallback;
}

/**
 * Send a ttyd frame over the socket. Copies the bytes into a fresh ArrayBuffer
 * so the value is `BufferSource`-typed (TS 6 widens `Uint8Array` over
 * `ArrayBufferLike`, which a raw frame's `.buffer` may be).
 */
function sendFrame(socket: WebSocket, frame: Uint8Array): void {
	const copy = new Uint8Array(frame.length);
	copy.set(frame);
	socket.send(copy.buffer);
}

/** Strip a leading OUTPUT opcode byte and decode the rest of a server frame. */
function decodeOutput(data: ArrayBuffer | string): string | null {
	if (typeof data === "string") {
		return data.charCodeAt(0) === 0x30 ? data.slice(1) : null;
	}
	const bytes = new Uint8Array(data);
	if (bytes[0] !== ServerCommand.OUTPUT.charCodeAt(0)) {
		return null; // not an OUTPUT frame (e.g. title/preferences) — ignore in v1
	}
	return new TextDecoder().decode(bytes.subarray(1));
}

/** What useTerminal exposes to the panel (02-UI-SPEC: status drives the overlay). */
export interface UseTerminalResult {
	containerRef: React.RefObject<HTMLDivElement | null>;
	status: TerminalState;
	reconnectAttempts: number;
}

/**
 * Mount xterm + the ttyd WS bridge for `workspaceId`. `status` is the workspace's
 * lifecycle status — a non-running workspace never opens a socket.
 */
export function useTerminal(
	workspaceId: string,
	status: WorkspaceStatus,
): UseTerminalResult {
	const containerRef = useRef<HTMLDivElement | null>(null);
	const [state, setState] = useState<TerminalState>("connecting");
	const [reconnectAttempts] = useState(0);

	useEffect(() => {
		const container = containerRef.current;
		// Only a running workspace has a live ttyd to bridge to; a non-running
		// workspace renders the body with no socket (the panel shows its state).
		if (!container || status !== "running") {
			return;
		}

		const term = new Terminal(TERM_OPTIONS);
		const fitAddon = new FitAddon();
		term.loadAddon(fitAddon);
		term.open(container);
		fitAddon.fit();

		const socket = new WebSocket(`/ws/workspaces/${workspaceId}/terminal`);
		socket.binaryType = "arraybuffer";

		socket.onopen = () => {
			sendFrame(socket, initFrame(term.cols, term.rows));
			setState("open");
		};

		socket.onmessage = (event: MessageEvent) => {
			const text = decodeOutput(event.data as ArrayBuffer | string);
			if (text !== null) {
				term.write(text);
			}
		};

		const dataSub = term.onData((data) => {
			if (socket.readyState === WebSocket.OPEN) {
				sendFrame(socket, inputFrame(data));
			}
		});

		// Thin teardown — Task 3 adds the ResizeObserver + reconnect timer cleanup.
		return () => {
			dataSub.dispose();
			socket.close();
			fitAddon.dispose();
			term.dispose();
		};
	}, [workspaceId, status]);

	return { containerRef, status: state, reconnectAttempts };
}
