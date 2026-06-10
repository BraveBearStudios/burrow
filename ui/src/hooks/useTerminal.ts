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
import { useCallback, useEffect, useRef, useState } from "react";
import { initFrame, inputFrame, resizeFrame, ServerCommand } from "../lib/ttyd";
import type { TerminalState, WorkspaceStatus } from "../types/workspace";

/** Reconnect policy (02-RESEARCH Pattern 2): jittered exponential, capped at 5. */
const MAX_RECONNECT_ATTEMPTS = 5;
const BASE_BACKOFF_MS = 500;
const MAX_BACKOFF_MS = 30_000;
const JITTER_MS = 250;
/** WS close code the backend uses for a policy violation — never retry on it. */
const POLICY_VIOLATION = 1008;

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

/** Jittered exponential backoff for reconnect attempt `n` (0-based). */
function backoffDelay(attempt: number): number {
	return (
		Math.min(MAX_BACKOFF_MS, BASE_BACKOFF_MS * 2 ** attempt) +
		Math.random() * JITTER_MS
	);
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

/** Decode a server frame to its text. Returns the parsed JSON for a JSON frame. */
function frameToString(data: ArrayBuffer | string): string {
	return typeof data === "string" ? data : new TextDecoder().decode(data);
}

/** True when the frame is the typed `{type:"error", code:"LXC_NOT_READY"}`. */
function isLxcNotReady(text: string): boolean {
	if (text[0] !== "{") {
		return false;
	}
	try {
		const parsed = JSON.parse(text);
		return parsed?.type === "error" && parsed?.code === "LXC_NOT_READY";
	} catch {
		return false;
	}
}

/** Strip a leading OUTPUT opcode byte; return null for a non-OUTPUT frame. */
function decodeOutput(text: string): string | null {
	return text.charCodeAt(0) === ServerCommand.OUTPUT.charCodeAt(0)
		? text.slice(1)
		: null;
}

/** What useTerminal exposes to the panel (02-UI-SPEC: status drives the overlay). */
export interface UseTerminalResult {
	containerRef: React.RefObject<HTMLDivElement | null>;
	status: TerminalState;
	reconnectAttempts: number;
	/** Force an immediate (re)connect — backs the Reattach / Retry overlay buttons. */
	reattach: () => void;
}

export interface UseTerminalOptions {
	/** Fired when the terminal enters a terminal state (Pitfall 4 reconciliation). */
	onTerminalEvent?: (event: "error" | "closed") => void;
}

/**
 * Mount xterm + the ttyd WS bridge for `workspaceId`. `status` is the workspace's
 * lifecycle status — a non-running / error / destroyed workspace never retries.
 */
export function useTerminal(
	workspaceId: string,
	status: WorkspaceStatus,
	options: UseTerminalOptions = {},
): UseTerminalResult {
	const containerRef = useRef<HTMLDivElement | null>(null);
	const [state, setState] = useState<TerminalState>("connecting");
	const [reconnectAttempts, setReconnectAttempts] = useState(0);

	// Live resources + counters held in refs so the single effect can tear them
	// all down idempotently (StrictMode double-mount safe) and the backoff loop
	// can recreate the socket without re-running the effect.
	const termRef = useRef<Terminal | null>(null);
	const fitRef = useRef<FitAddon | null>(null);
	const socketRef = useRef<WebSocket | null>(null);
	const observerRef = useRef<ResizeObserver | null>(null);
	const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
	const attemptRef = useRef(0);
	const disposedRef = useRef(false);
	const onEventRef = useRef(options.onTerminalEvent);
	onEventRef.current = options.onTerminalEvent;

	// `reattach` resets the backoff and forces an immediate connect. It is bound
	// once via a ref so the returned identity is stable for the overlay buttons.
	const connectRef = useRef<() => void>(() => {});
	const reattach = useCallback(() => {
		if (disposedRef.current) {
			return;
		}
		if (timerRef.current) {
			clearTimeout(timerRef.current);
			timerRef.current = null;
		}
		attemptRef.current = 0;
		setReconnectAttempts(0);
		setState("connecting");
		connectRef.current();
	}, []);

	useEffect(() => {
		const container = containerRef.current;
		// Only a running workspace has a live ttyd to bridge to.
		if (!container || status !== "running") {
			return;
		}
		disposedRef.current = false;

		const term = new Terminal(TERM_OPTIONS);
		const fitAddon = new FitAddon();
		term.loadAddon(fitAddon);
		term.open(container);
		termRef.current = term;
		fitRef.current = fitAddon;

		const safeFit = () => {
			// Fit only when visible & non-zero (Pitfall 3: fit-on-hidden → 1 col).
			if (container.offsetWidth === 0 && container.clientWidth === 0) {
				return;
			}
			fitAddon.fit();
			const socket = socketRef.current;
			if (socket && socket.readyState === WebSocket.OPEN) {
				sendFrame(socket, resizeFrame(term.cols, term.rows));
			}
		};
		safeFit();

		term.onData((data) => {
			const socket = socketRef.current;
			if (socket && socket.readyState === WebSocket.OPEN) {
				sendFrame(socket, inputFrame(data));
			}
		});

		const connect = () => {
			if (disposedRef.current) {
				return;
			}
			const socket = new WebSocket(`/ws/workspaces/${workspaceId}/terminal`);
			socket.binaryType = "arraybuffer";
			socketRef.current = socket;

			socket.onopen = () => {
				attemptRef.current = 0;
				setReconnectAttempts(0);
				setState("open");
				sendFrame(socket, initFrame(term.cols, term.rows));
			};

			socket.onmessage = (event: MessageEvent) => {
				const text = frameToString(event.data as ArrayBuffer | string);
				if (isLxcNotReady(text)) {
					stop("error");
					return;
				}
				const output = decodeOutput(text);
				if (output !== null) {
					term.write(output);
				}
			};

			socket.onclose = (event: CloseEvent) => {
				if (disposedRef.current) {
					return;
				}
				// Stop on a policy violation or a terminal workspace state.
				if (event.code === POLICY_VIOLATION) {
					stop("error");
					return;
				}
				scheduleReconnect();
			};

			socket.onerror = () => {
				// onerror is followed by onclose in the browser; let onclose decide.
			};
		};
		connectRef.current = connect;

		const scheduleReconnect = () => {
			if (disposedRef.current) {
				return;
			}
			if (attemptRef.current >= MAX_RECONNECT_ATTEMPTS) {
				stop("error");
				return;
			}
			const delay = backoffDelay(attemptRef.current);
			attemptRef.current += 1;
			setReconnectAttempts(attemptRef.current);
			setState("reconnecting");
			onEventRef.current?.("closed");
			timerRef.current = setTimeout(connect, delay);
		};

		const stop = (next: "error" | "closed") => {
			if (timerRef.current) {
				clearTimeout(timerRef.current);
				timerRef.current = null;
			}
			setState(next);
			onEventRef.current?.(next);
		};

		const observer = new ResizeObserver(() => {
			safeFit();
		});
		observer.observe(container);
		observerRef.current = observer;

		connect();

		return () => {
			disposedRef.current = true;
			if (timerRef.current) {
				clearTimeout(timerRef.current);
				timerRef.current = null;
			}
			observer.disconnect();
			observerRef.current = null;
			socketRef.current?.close();
			socketRef.current = null;
			fitAddon.dispose();
			fitRef.current = null;
			term.dispose();
			termRef.current = null;
		};
	}, [workspaceId, status]);

	return { containerRef, status: state, reconnectAttempts, reattach };
}
