// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// CredentialsScreen is the admin-gated post-setup credential surface (CRED-04) to
// the ADR-0015 contract. Reached from the Navbar gear. If the in-memory admin
// secret is not set it renders an unlock PROMPT (password field → useAdminStore);
// once unlocked it shows credential STATUS (which credentials are set, their
// last4, and the last change time — NEVER a secret value, the backend never
// returns one) plus a ROTATION form (re-submit POST /setup/credentials) and the
// read-only AuditPanel. A rejected admin gate (401 `admin_unauthorized`) clears
// the store inside the hooks, so this screen falls back to the prompt.
//
// SECURITY (ADR-0015): the admin secret + rotated tokens live ONLY in transient
// React state + the in-memory useAdminStore. They are never persisted to web
// storage, never cached, and never logged. Every input is type="password"; green
// (--accent) is the CTA color (not browser-blue), --err the error strip.

import { useEffect, useRef, useState } from "react";
import { ApiError } from "../api/client";
import {
	ADMIN_AUTH_CODE,
	useCredentialStatus,
	useSaveCredentials,
} from "../hooks/useSetup";
import { useAdminStore } from "../store/useAdminStore";
import type { CredentialStatus, SaveCredentialsBody } from "../types/setup";
import { AuditPanel } from "./AuditPanel";

export interface CredentialsScreenProps {
	/** Close the screen (backdrop, ×, Esc). */
	onClose: () => void;
}

/** Fixed, secret-free copy mapped from ApiError.code (mirrors the backend). */
const ERROR_COPY: Record<string, string> = {
	setup_unreachable: "Could not reach the Proxmox host. Check it, then retry.",
	setup_auth_failed: "The Proxmox token was rejected. Re-check it, then retry.",
	credential_store_unconfigured:
		"The credential store is not configured (BURROW_SECRET_KEY unset).",
	admin_unauthorized: "Admin authorization failed. Re-enter the admin secret.",
};

const GENERIC_ERROR = "Something went wrong. Try again.";

function mapError(error: unknown): string {
	if (error instanceof ApiError && ERROR_COPY[error.code]) {
		return ERROR_COPY[error.code];
	}
	return GENERIC_ERROR;
}

const overlayStyle: React.CSSProperties = {
	position: "fixed",
	inset: 0,
	display: "grid",
	placeItems: "center",
	background: "rgba(8,13,8,.55)",
	zIndex: 50,
};

const modalStyle: React.CSSProperties = {
	width: "min(560px, calc(100vw - 32px))",
	maxHeight: "calc(100vh - 48px)",
	background: "var(--bg-surf)",
	border: "0.5px solid var(--border-mid)",
	borderRadius: "var(--radius-card)",
	display: "flex",
	flexDirection: "column",
	outline: "none",
	overflow: "hidden",
};

const bodyStyle: React.CSSProperties = {
	display: "flex",
	flexDirection: "column",
	gap: "16px",
	padding: "17px 19px",
	overflow: "auto",
};

const labelStyle: React.CSSProperties = {
	display: "block",
	fontFamily: "var(--font-sans)",
	fontSize: "11px",
	fontWeight: 500,
	letterSpacing: "1.3px",
	textTransform: "uppercase",
	color: "var(--text-muted)",
	marginBottom: "5px",
};

const inputStyle: React.CSSProperties = {
	width: "100%",
	height: "var(--h-input)",
	padding: "0 10px",
	background: "var(--bg-panel-alt)",
	border: "0.5px solid var(--border-mid)",
	borderRadius: "var(--radius-control)",
	color: "var(--text)",
	fontFamily: "var(--font-sans)",
	fontSize: "13px",
};

const helperStyle: React.CSSProperties = {
	display: "block",
	marginTop: "4px",
	fontSize: "11px",
	color: "var(--text-sub)",
};

const primaryCtaStyle = (enabled: boolean): React.CSSProperties => ({
	height: "32px",
	padding: "0 14px",
	background: "var(--accent)",
	color: "var(--btn-pri-text)",
	border: "none",
	borderRadius: "var(--radius-control)",
	fontFamily: "var(--font-sans)",
	fontSize: "13px",
	fontWeight: 500,
	cursor: enabled ? "pointer" : "not-allowed",
	opacity: enabled ? 1 : 0.5,
});

/** The left-bordered --err strip carrying a fixed message. */
function ErrorStrip({ message }: { message: string }) {
	return (
		<div
			style={{
				padding: "8px 11px",
				borderRadius: "var(--radius-control)",
				background: "var(--bg-panel-alt)",
				borderLeft: "2px solid var(--err)",
				fontFamily: "var(--font-sans)",
				fontSize: "12px",
				color: "var(--err)",
			}}
		>
			{message}
		</div>
	);
}

/** A single label + password input row. */
function PasswordField({
	id,
	label,
	value,
	onChange,
	placeholder,
	helper,
}: {
	id: string;
	label: string;
	value: string;
	onChange: (value: string) => void;
	placeholder?: string;
	helper?: string;
}) {
	return (
		<div>
			<label htmlFor={id} style={labelStyle}>
				{label}
			</label>
			<input
				id={id}
				type="password"
				value={value}
				placeholder={placeholder}
				onChange={(event) => onChange(event.target.value)}
				style={inputStyle}
			/>
			{helper ? <span style={helperStyle}>{helper}</span> : null}
		</div>
	);
}

/** The unlock prompt shown when no admin secret is in memory (or after a 401). */
function AdminPrompt({ onUnlock }: { onUnlock: (secret: string) => void }) {
	const status = useCredentialStatus();
	const [value, setValue] = useState("");
	const authFailed =
		status.error instanceof ApiError && status.error.code === ADMIN_AUTH_CODE;
	const canSubmit = value.trim() !== "";

	const submit = () => {
		if (!canSubmit) {
			return;
		}
		// Setting the store enables the admin-gated queries; a wrong secret 401s and
		// the hook clears the store, returning us to this prompt with authFailed set.
		onUnlock(value);
	};

	return (
		<>
			<span
				style={{
					fontFamily: "var(--font-sans)",
					fontSize: "13px",
					color: "var(--text-sub)",
				}}
			>
				Enter the admin secret to view and rotate stored credentials.
			</span>
			{authFailed ? (
				<ErrorStrip message={ERROR_COPY.admin_unauthorized} />
			) : null}
			<PasswordField
				id="cred-admin-secret"
				label="Admin secret"
				value={value}
				onChange={setValue}
				placeholder="••••••••"
			/>
			<footer style={{ display: "flex", justifyContent: "flex-end" }}>
				<button
					type="button"
					onClick={submit}
					disabled={!canSubmit}
					style={primaryCtaStyle(canSubmit)}
				>
					Unlock
				</button>
			</footer>
		</>
	);
}

/** One status row: a label, a set/not-set state, and the last4 when present. */
function StatusRow({
	label,
	isSet,
	last4,
}: {
	label: string;
	isSet: boolean;
	last4: string | null;
}) {
	return (
		<div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
			<span style={{ width: "110px", color: "var(--text-sub)" }}>{label}</span>
			<span
				aria-hidden="true"
				style={{
					width: "var(--sz-status-dot)",
					height: "var(--sz-status-dot)",
					borderRadius: "var(--radius-full)",
					background: isSet ? "var(--ok)" : "var(--text-muted)",
				}}
			/>
			<span style={{ color: "var(--text)" }}>{isSet ? "set" : "not set"}</span>
			{isSet && last4 ? (
				<span style={{ fontFamily: "var(--font-mono)", color: "var(--gold)" }}>
					****{last4}
				</span>
			) : null}
		</div>
	);
}

/** The credential status readout — never renders a secret value (last4 only). */
function StatusView({ status }: { status: CredentialStatus }) {
	return (
		<section
			aria-label="Credential status"
			style={{
				display: "flex",
				flexDirection: "column",
				gap: "10px",
				fontFamily: "var(--font-sans)",
				fontSize: "13px",
			}}
		>
			<StatusRow
				label="Proxmox token"
				isSet={status.proxmoxTokenSet}
				last4={status.proxmoxTokenLast4}
			/>
			<StatusRow
				label="GitHub PAT"
				isSet={status.gitTokenSet}
				last4={status.gitTokenLast4}
			/>
			<span style={{ fontSize: "11px", color: "var(--text-sub)" }}>
				{status.updatedAt
					? `Last updated ${status.updatedAt}`
					: "No credentials stored yet."}
			</span>
		</section>
	);
}

/** The rotation form: re-submit POST /setup/credentials with a new value. */
function RotationForm() {
	const saveCredentials = useSaveCredentials();
	const [proxmoxToken, setProxmoxToken] = useState("");
	const [gitToken, setGitToken] = useState("");
	const [error, setError] = useState<string | null>(null);
	const [saved, setSaved] = useState(false);

	// At least one field required (an empty write is a backend 422).
	const canSubmit =
		(proxmoxToken.trim() !== "" || gitToken.trim() !== "") &&
		!saveCredentials.isPending;

	const submit = () => {
		if (!canSubmit) {
			return;
		}
		setError(null);
		setSaved(false);
		const body: SaveCredentialsBody = {};
		if (proxmoxToken.trim() !== "") {
			body.proxmoxTokenValue = proxmoxToken;
		}
		if (gitToken.trim() !== "") {
			body.gitToken = gitToken;
		}
		saveCredentials.mutate(body, {
			onSuccess: () => {
				// Drop the transient values immediately once persisted (never linger).
				setProxmoxToken("");
				setGitToken("");
				setSaved(true);
			},
			onError: (err) => setError(mapError(err)),
		});
	};

	return (
		<section
			aria-label="Rotate credentials"
			style={{ display: "flex", flexDirection: "column", gap: "12px" }}
		>
			<span style={labelStyle}>Rotate credentials</span>
			<PasswordField
				id="cred-proxmox-token"
				label="Proxmox token value"
				value={proxmoxToken}
				onChange={(value) => {
					setProxmoxToken(value);
					setSaved(false);
				}}
				placeholder="••••••••"
				helper="Validated against Proxmox before it is stored."
			/>
			<PasswordField
				id="cred-git-token"
				label="GitHub PAT"
				value={gitToken}
				onChange={(value) => {
					setGitToken(value);
					setSaved(false);
				}}
				placeholder="••••••••"
				helper="Optional. Leave blank to keep the current PAT."
			/>
			{error ? <ErrorStrip message={error} /> : null}
			{saved ? (
				<span style={{ fontSize: "12px", color: "var(--ok)" }}>
					Credentials saved.
				</span>
			) : null}
			<footer style={{ display: "flex", justifyContent: "flex-end" }}>
				<button
					type="button"
					onClick={submit}
					disabled={!canSubmit}
					style={primaryCtaStyle(canSubmit)}
				>
					Save credentials
				</button>
			</footer>
		</section>
	);
}

/** The unlocked body: status + rotation + audit trail. */
function UnlockedBody() {
	const status = useCredentialStatus();
	return (
		<>
			{status.isLoading ? (
				<span style={{ fontSize: "12px", color: "var(--text-sub)" }}>
					Loading credential status…
				</span>
			) : status.data ? (
				<StatusView status={status.data} />
			) : null}
			<RotationForm />
			<AuditPanel />
		</>
	);
}

export function CredentialsScreen({ onClose }: CredentialsScreenProps) {
	const secret = useAdminStore((state) => state.secret);
	const setSecret = useAdminStore((state) => state.setSecret);
	const dialogRef = useRef<HTMLDivElement>(null);

	// Focus the dialog on mount so Esc + the focus trap engage immediately.
	useEffect(() => {
		dialogRef.current?.focus();
	}, []);

	const onKeyDown = (event: React.KeyboardEvent) => {
		if (event.key === "Escape") {
			onClose();
		}
	};

	return (
		<div style={overlayStyle}>
			{/* Keyboard-accessible scrim; the dialog (Esc-closable) sits above it. */}
			<button
				type="button"
				aria-label="Dismiss"
				onClick={onClose}
				style={{
					position: "absolute",
					inset: 0,
					width: "100%",
					height: "100%",
					border: "none",
					background: "transparent",
					cursor: "default",
				}}
			/>
			<div
				ref={dialogRef}
				role="dialog"
				aria-modal="true"
				aria-label="Credentials"
				tabIndex={-1}
				onKeyDown={onKeyDown}
				style={{ ...modalStyle, position: "relative" }}
			>
				<header
					style={{
						display: "flex",
						alignItems: "center",
						justifyContent: "space-between",
						padding: "16px 19px",
						borderBottom: "0.5px solid var(--border)",
					}}
				>
					<span
						style={{
							fontFamily: "var(--font-display)",
							fontWeight: 500,
							fontSize: "16px",
							color: "var(--text)",
						}}
					>
						Credentials
					</span>
					<button
						type="button"
						aria-label="Close dialog"
						onClick={onClose}
						style={{
							display: "grid",
							placeItems: "center",
							width: "24px",
							height: "24px",
							border: "none",
							background: "transparent",
							color: "var(--text-muted)",
							borderRadius: "var(--radius-control)",
							cursor: "pointer",
						}}
					>
						<svg
							width="15"
							height="15"
							viewBox="0 0 24 24"
							aria-hidden="true"
							fill="none"
							stroke="currentColor"
							strokeWidth={1.5}
							strokeLinecap="round"
						>
							<line x1="6" y1="6" x2="18" y2="18" />
							<line x1="18" y1="6" x2="6" y2="18" />
						</svg>
					</button>
				</header>

				<div style={bodyStyle}>
					{secret == null ? (
						<AdminPrompt onUnlock={setSecret} />
					) : (
						<UnlockedBody />
					)}
				</div>
			</div>
		</div>
	);
}
