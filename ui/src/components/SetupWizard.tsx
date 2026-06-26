// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// SetupWizard is the full-page first-run GATE (SETUP-04/06) to the binding
// 13-UI-SPEC contract. An unconfigured Burrow renders ONLY this wizard; it blocks
// the app until the operator validates the Proxmox connection, verifies the worker
// template, confirms control-plane health, and creates a first workspace — at which
// point setup is marked complete (POST /setup/complete) and the gate flips away.
//
// Four ordered steps AUTO-ADVANCE on success: (1) token validation → (2) template
// verify → (3) health → (4) create first workspace. There is NO persisted checkpoint
// machine: position is derived from live state only (an unconfigured Burrow opens on
// step 1). Errors map by ApiError.code to the FIXED token-free backend messages
// (_SAFE_ERROR_MESSAGES) + static UI guidance; inputs stay populated for inline retry.
//
// Hard-gate a11y: role="dialog", aria-modal, aria-label="Set up Burrow", focus on
// mount, focus trapped (the only interactive surface), Enter submits the active step,
// and ESCAPE DOES NOTHING (override the dismissible-modal idiom). Each step status is
// an aria-live="polite" region. Tokens-only (no hex); green (--accent) is reserved
// for the forward CTA + the ✓ rows + the focus ring; gold (--gold) is reserved to the
// StepSpinner top-arc ONLY; --err for the ✕ + the left-bordered error strip.
//
// SECURITY (T-13-07): the Proxmox token lives ONLY in step-1 form state and is passed
// to useTestConnection.mutate. It is NEVER written to the query cache / Zustand /
// localStorage and NEVER logged. The token field is type="password".

import { createContext, useContext, useEffect, useRef, useState } from "react";
import { ApiError, api } from "../api/client";
import {
	useCompleteSetup,
	useTestConnection,
	useVerifyTemplate,
} from "../hooks/useSetup";
import { useCreateWorkspace } from "../hooks/useWorkspaces";

/** The four gate steps (1-indexed to match the checklist labels). */
const STEP_LABELS = [
	"1 Connection",
	"2 Template",
	"3 Health",
	"4 First workspace",
] as const;

/** The fixed, token-free error copy mapped from ApiError.code (UI-SPEC Copywriting). */
const ERROR_COPY: Record<string, { message: string; guidance: string }> = {
	setup_unreachable: {
		message: "Could not reach the Proxmox host.",
		guidance:
			"Check the host URL and that the API port (8006) is reachable, then retry.",
	},
	setup_auth_failed: {
		message: "The Proxmox token was rejected.",
		guidance: "Re-check the user, token name, and token value, then retry.",
	},
	setup_template_not_found: {
		message: "The worker template was not found on the target node.",
		guidance: "Confirm the template VMID and node, then re-verify.",
	},
};

/** Generic fallback when an un-coded error escapes (UI-SPEC cross-cutting copy). */
const GENERIC_ERROR = "Something went wrong. Try again.";

/**
 * Holds the active step's submit handler so the dialog-level Enter key handler can
 * invoke it without threading props through every step. Each step registers its
 * current (enabled) submit via useActiveSubmit; null means "not submittable".
 */
const ActiveSubmitContext = createContext<{
	current: (() => void) | null;
}>({ current: null });

/** Register this step's submit handler with the dialog while it is active + enabled. */
function useActiveSubmit(fn: () => void, enabled: boolean) {
	const ref = useContext(ActiveSubmitContext);
	useEffect(() => {
		ref.current = enabled ? fn : null;
		return () => {
			ref.current = null;
		};
	});
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
	width: "var(--w-modal)",
	maxWidth: "calc(100vw - 32px)",
	background: "var(--bg-surf)",
	border: "0.5px solid var(--border-mid)",
	borderRadius: "var(--radius-card)",
	display: "flex",
	flexDirection: "column",
	outline: "none",
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

const footerStyle: React.CSSProperties = {
	display: "flex",
	justifyContent: "flex-end",
	marginTop: "3px",
};

const bodyStyle: React.CSSProperties = {
	display: "flex",
	flexDirection: "column",
	gap: "14px",
	padding: "17px 19px",
};

/** The 13px gold-topped spinner that marks the active step (gold's ONE sanctioned use). */
function StepSpinner() {
	return (
		<span
			aria-hidden="true"
			style={{
				width: "13px",
				height: "13px",
				borderRadius: "var(--radius-full)",
				border: "2px solid var(--border-mid)",
				borderTopColor: "var(--gold)",
				animation: "spin 0.8s linear infinite",
			}}
		/>
	);
}

/** A single label + input field (verbatim NewWorkspaceModal idiom). */
function Field({
	id,
	label,
	value,
	onChange,
	type = "text",
	placeholder,
	invalid,
}: {
	id: string;
	label: string;
	value: string;
	onChange: (v: string) => void;
	type?: string;
	placeholder?: string;
	invalid?: boolean;
}) {
	return (
		<div>
			<label htmlFor={id} style={labelStyle}>
				{label}
			</label>
			<input
				id={id}
				type={type}
				value={value}
				placeholder={placeholder}
				onChange={(e) => onChange(e.target.value)}
				style={{
					...inputStyle,
					borderColor: invalid ? "var(--err)" : "var(--border-mid)",
				}}
			/>
		</div>
	);
}

/** The left-bordered --err strip carrying a fixed message + inline guidance. */
function ErrorStrip({
	message,
	guidance,
}: {
	message: string;
	guidance?: string;
}) {
	return (
		<div
			style={{
				padding: "8px 11px",
				borderRadius: "var(--radius-control)",
				background: "var(--bg-panel-alt)",
				borderLeft: "2px solid var(--err)",
				fontFamily: "var(--font-sans)",
				fontSize: "12px",
			}}
		>
			<span style={{ color: "var(--err)" }}>{message}</span>
			{guidance ? (
				<span
					style={{
						display: "block",
						marginTop: "4px",
						color: "var(--text-sub)",
					}}
				>
					{guidance}
				</span>
			) : null}
		</div>
	);
}

/** Map an unknown error to the fixed copy (coded → mapped, else generic fallback). */
function mapError(err: unknown): { message: string; guidance?: string } {
	if (err instanceof ApiError && ERROR_COPY[err.code]) {
		return ERROR_COPY[err.code];
	}
	return { message: GENERIC_ERROR };
}

/** The vertical 4-row status checklist (mono 12.5px), glyph contract per UI-SPEC. */
function Checklist({ step }: { step: number }) {
	return (
		<div
			role="status"
			aria-live="polite"
			style={{
				display: "flex",
				flexDirection: "column",
				gap: "11px",
				fontFamily: "var(--font-mono)",
				fontSize: "12.5px",
			}}
		>
			{STEP_LABELS.map((label, i) => {
				const index = i + 1;
				const isActive = index === step;
				const isPassed = index < step;
				return (
					<div
						key={label}
						style={{
							display: "flex",
							alignItems: "center",
							gap: "9px",
							color: isPassed
								? "var(--text)"
								: isActive
									? "var(--text)"
									: "var(--text-muted)",
						}}
					>
						<span
							aria-hidden="true"
							style={{
								display: "grid",
								placeItems: "center",
								width: "13px",
								height: "13px",
							}}
						>
							{isActive ? <StepSpinner /> : isPassed ? "✓" : "○"}
						</span>
						<span>{label}</span>
					</div>
				);
			})}
		</div>
	);
}

/** Step 1 — validate the operator-typed Proxmox token (transient, never stored). */
function StepConnection({ onAdvance }: { onAdvance: () => void }) {
	const testConnection = useTestConnection();
	const [host, setHost] = useState("");
	const [user, setUser] = useState("");
	const [tokenName, setTokenName] = useState("");
	const [tokenValue, setTokenValue] = useState("");
	const [missingPrivileges, setMissingPrivileges] = useState<string[] | null>(
		null,
	);
	const [error, setError] = useState<{
		message: string;
		guidance?: string;
	} | null>(null);

	const isValid =
		host.trim() !== "" &&
		user.trim() !== "" &&
		tokenName.trim() !== "" &&
		tokenValue.trim() !== "";
	const isLoading = testConnection.isPending;
	const canSubmit = isValid && !isLoading;

	const submit = () => {
		if (!canSubmit) {
			return;
		}
		setError(null);
		setMissingPrivileges(null);
		// The token is a transient mutation arg ONLY (T-13-07): not stored, not logged.
		testConnection.mutate(
			{ host, user, tokenName, tokenValue },
			{
				onSuccess: (result) => {
					if (result.success) {
						onAdvance();
					} else {
						// success=false (200) is the under-privileged SUCCESS path — render
						// the privilege list, NOT an error strip.
						setMissingPrivileges(result.missingPrivileges);
					}
				},
				onError: (err) => setError(mapError(err)),
			},
		);
	};

	return (
		<>
			<StepHeading title="Validate Proxmox connection" />
			<Field
				id="setup-host"
				label="Host"
				value={host}
				onChange={setHost}
				placeholder="https://pve.lan:8006"
			/>
			<Field
				id="setup-user"
				label="User"
				value={user}
				onChange={setUser}
				placeholder="burrow@pve"
			/>
			<Field
				id="setup-token-name"
				label="Token name"
				value={tokenName}
				onChange={setTokenName}
				placeholder="burrow-token"
			/>
			<Field
				id="setup-token-value"
				label="Token value"
				value={tokenValue}
				onChange={setTokenValue}
				type="password"
				placeholder="••••••••"
			/>
			<span style={helperStyle}>
				Validated in memory only — never stored. Keep the real token in your
				.env.
			</span>

			{missingPrivileges ? (
				<div
					style={{
						padding: "10px 12px",
						background: "var(--bg-panel-alt)",
						border: "0.5px solid var(--border)",
						borderRadius: "var(--radius-control)",
						fontFamily: "var(--font-sans)",
						fontSize: "12px",
						color: "var(--text)",
					}}
				>
					<span style={{ display: "block", marginBottom: "6px" }}>
						Token is valid but missing privileges:
					</span>
					<ul
						style={{
							margin: 0,
							paddingLeft: "18px",
							fontFamily: "var(--font-mono)",
							fontSize: "12.5px",
						}}
					>
						{missingPrivileges.map((priv) => (
							<li key={priv}>{priv}</li>
						))}
					</ul>
					<span
						style={{
							display: "block",
							marginTop: "6px",
							color: "var(--text-sub)",
						}}
					>
						Grant these on the Burrow privsep token, then re-validate.
					</span>
				</div>
			) : null}

			{error ? (
				<ErrorStrip message={error.message} guidance={error.guidance} />
			) : null}

			<StepFooter
				label="Validate connection"
				onSubmit={submit}
				enabled={canSubmit}
			/>
		</>
	);
}

/** Step 2 — verify the worker template exists + is usable on the target node. */
function StepTemplate({ onAdvance }: { onAdvance: () => void }) {
	const verifyTemplate = useVerifyTemplate();
	const [templateVmid, setTemplateVmid] = useState("");
	const [node, setNode] = useState("");
	const [notUsable, setNotUsable] = useState<{
		vmid: number;
		node: string;
	} | null>(null);
	const [error, setError] = useState<{
		message: string;
		guidance?: string;
	} | null>(null);

	const isValid = templateVmid.trim() !== "" && node.trim() !== "";
	const isLoading = verifyTemplate.isPending;
	const canSubmit = isValid && !isLoading;

	const submit = () => {
		if (!canSubmit) {
			return;
		}
		setError(null);
		setNotUsable(null);
		verifyTemplate.mutate(
			{ templateVmid: Number(templateVmid), node },
			{
				onSuccess: (result) => {
					if (result.usable) {
						onAdvance();
					} else {
						// exists=true, usable=false (200) → "not a template" guidance.
						setNotUsable({ vmid: result.vmid, node: result.node });
					}
				},
				onError: (err) => setError(mapError(err)),
			},
		);
	};

	return (
		<>
			<StepHeading title="Verify worker template" />
			<Field
				id="setup-template-vmid"
				label="Template VMID"
				value={templateVmid}
				onChange={setTemplateVmid}
				type="number"
				placeholder="9000"
			/>
			<Field
				id="setup-template-node"
				label="Node"
				value={node}
				onChange={setNode}
				placeholder="pve"
			/>

			{notUsable ? (
				<ErrorStrip
					message={`VMID ${notUsable.vmid} exists on ${notUsable.node} but is not a template.`}
					guidance="Convert it to a template (or check the VMID), then re-verify."
				/>
			) : null}

			{error ? (
				<ErrorStrip message={error.message} guidance={error.guidance} />
			) : null}

			<StepFooter
				label="Verify template"
				onSubmit={submit}
				enabled={canSubmit}
			/>
		</>
	);
}

/** The control-plane health readout (degrade-not-500: db + compute must read "ok"). */
interface HealthResult {
	status: string;
	db: string;
	compute: string;
}

/** Step 3 — probe GET /api/v1/health; both db + compute "ok" advances. */
function StepHealth({ onAdvance }: { onAdvance: () => void }) {
	const [result, setResult] = useState<HealthResult | null>(null);
	const [isLoading, setIsLoading] = useState(false);
	const advancedRef = useRef(false);

	const probe = () => {
		setIsLoading(true);
		api<HealthResult>("/health")
			.then((data) => {
				setResult(data);
				setIsLoading(false);
				if (data.db === "ok" && data.compute === "ok" && !advancedRef.current) {
					advancedRef.current = true;
					onAdvance();
				}
			})
			.catch(() => {
				setResult({ status: "degraded", db: "error", compute: "error" });
				setIsLoading(false);
			});
	};

	// Probe once on mount so the health step self-checks without a manual click.
	// biome-ignore lint/correctness/useExhaustiveDependencies: probe-on-mount only.
	useEffect(() => {
		probe();
	}, []);

	const degraded =
		result !== null && (result.db !== "ok" || result.compute !== "ok");

	return (
		<>
			<StepHeading title="Check control-plane health" />
			<div
				style={{
					display: "flex",
					flexDirection: "column",
					gap: "8px",
					fontFamily: "var(--font-sans)",
					fontSize: "13px",
				}}
			>
				<HealthRow label="Database" ok={result?.db === "ok"} />
				<HealthRow label="Compute" ok={result?.compute === "ok"} />
			</div>

			{degraded ? (
				<ErrorStrip
					message="Burrow can start, but cannot reach Proxmox yet."
					guidance="Fix the connection above, then Re-check."
				/>
			) : null}

			<StepFooter label="Re-check" onSubmit={probe} enabled={!isLoading} />
		</>
	);
}

/** One health row: a status dot + the literal ok/unreachable text (never color-only). */
function HealthRow({ label, ok }: { label: string; ok: boolean }) {
	return (
		<div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
			<span style={{ width: "70px", color: "var(--text-sub)" }}>{label}</span>
			<span
				aria-hidden="true"
				style={{
					width: "var(--sz-status-dot)",
					height: "var(--sz-status-dot)",
					borderRadius: "var(--radius-full)",
					background: ok ? "var(--ok)" : "var(--err)",
				}}
			/>
			<span style={{ color: ok ? "var(--ok)" : "var(--err)" }}>
				{ok ? "ok" : "unreachable"}
			</span>
		</div>
	);
}

/** Step 4 — create the first workspace, then mark setup complete (complete-AFTER-create). */
function StepCreate() {
	const createWorkspace = useCreateWorkspace();
	const completeSetup = useCompleteSetup();
	const [name, setName] = useState("");
	const [projectRepo, setProjectRepo] = useState("");
	const [projectBranch, setProjectBranch] = useState("main");
	const [node, setNode] = useState("");
	const [persistent, setPersistent] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const isValid = name.trim() !== "" && projectRepo.trim() !== "";
	const isLoading = createWorkspace.isPending || completeSetup.isPending;
	const canSubmit = isValid && !isLoading;

	const submit = () => {
		if (!canSubmit) {
			return;
		}
		setError(null);
		createWorkspace.mutate(
			{
				name,
				projectRepo,
				projectBranch: projectBranch.trim() || "main",
				node: node || null,
				persistent,
			},
			{
				// complete-AFTER-create: only mark setup complete once the create lands.
				onSuccess: () => completeSetup.mutate(),
				onError: (err) =>
					setError(err instanceof ApiError ? err.message : GENERIC_ERROR),
			},
		);
	};

	return (
		<>
			<StepHeading title="Create your first workspace" />
			<Field
				id="setup-ws-name"
				label="Name"
				value={name}
				onChange={setName}
				placeholder="project-omega"
			/>
			<Field
				id="setup-ws-repo"
				label="Git repo"
				value={projectRepo}
				onChange={setProjectRepo}
				placeholder="github.com/acme/omega"
			/>
			<div style={{ display: "flex", gap: "12px" }}>
				<div style={{ flex: 1 }}>
					<label htmlFor="setup-ws-branch" style={labelStyle}>
						Branch
					</label>
					<input
						id="setup-ws-branch"
						value={projectBranch}
						onChange={(e) => setProjectBranch(e.target.value)}
						style={inputStyle}
					/>
				</div>
				<div style={{ width: "128px" }}>
					<label htmlFor="setup-ws-node" style={labelStyle}>
						Node
					</label>
					<input
						id="setup-ws-node"
						value={node}
						onChange={(e) => setNode(e.target.value)}
						placeholder="Auto (least-loaded)"
						style={{ ...inputStyle, padding: "0 6px" }}
					/>
				</div>
			</div>

			<div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
				<input
					id="setup-ws-persistent"
					type="checkbox"
					checked={persistent}
					onChange={(e) => setPersistent(e.target.checked)}
					style={{ accentColor: "var(--accent)" }}
				/>
				<label
					htmlFor="setup-ws-persistent"
					style={{
						fontFamily: "var(--font-sans)",
						fontSize: "13px",
						fontWeight: 400,
						color: "var(--text)",
					}}
				>
					Persistent (keep workspace after session ends)
				</label>
			</div>

			{error ? <ErrorStrip message={error} /> : null}

			<StepFooter
				label="Create workspace"
				onSubmit={submit}
				enabled={canSubmit}
			/>
		</>
	);
}

/** A step section heading (16px display, 02-UI-SPEC). */
function StepHeading({ title }: { title: string }) {
	return (
		<span
			style={{
				fontFamily: "var(--font-display)",
				fontWeight: 500,
				fontSize: "14px",
				color: "var(--text)",
			}}
		>
			{title}
		</span>
	);
}

/** The single right-aligned primary CTA footer for a step. */
function StepFooter({
	label,
	onSubmit,
	enabled,
}: {
	label: string;
	onSubmit: () => void;
	enabled: boolean;
}) {
	// Register this step's submit with the dialog so Enter can invoke it.
	useActiveSubmit(onSubmit, enabled);
	return (
		<footer style={footerStyle}>
			<button
				type="button"
				onClick={onSubmit}
				disabled={!enabled}
				style={primaryCtaStyle(enabled)}
			>
				{label}
			</button>
		</footer>
	);
}

export function SetupWizard() {
	// The active step (1..4) is derived from live state only — NO persisted checkpoint.
	// An unconfigured Burrow opens on step 1; each success advances via setStep.
	const [step, setStep] = useState(1);
	const dialogRef = useRef<HTMLDivElement>(null);
	// The active step's submit handler (null when the step is not submittable).
	const submitRef = useRef<(() => void) | null>(null);

	// Focus the card on mount so the focus trap + Enter/Escape handling engage.
	useEffect(() => {
		dialogRef.current?.focus();
	}, []);

	const advance = () => setStep((s) => Math.min(s + 1, STEP_LABELS.length));

	const onKeyDown = (e: React.KeyboardEvent) => {
		// ESCAPE DOES NOTHING — the gate is non-dismissible (override the modal idiom).
		if (e.key === "Escape") {
			e.preventDefault();
			return;
		}
		// Enter submits the active step's CTA when its required fields are valid.
		if (e.key === "Enter") {
			submitRef.current?.();
		}
	};

	return (
		<ActiveSubmitContext.Provider value={submitRef}>
			<div style={overlayStyle}>
				<div
					ref={dialogRef}
					role="dialog"
					aria-modal="true"
					aria-label="Set up Burrow"
					tabIndex={-1}
					onKeyDown={onKeyDown}
					style={modalStyle}
				>
					<header
						style={{
							display: "flex",
							flexDirection: "column",
							gap: "4px",
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
							Set up Burrow
						</span>
						<span
							style={{
								fontFamily: "var(--font-sans)",
								fontSize: "12px",
								color: "var(--text-sub)",
							}}
						>
							Connect your Proxmox host and create your first workspace.
						</span>
					</header>

					<div style={bodyStyle}>
						<Checklist step={step} />
						{step === 1 ? <StepConnection onAdvance={advance} /> : null}
						{step === 2 ? <StepTemplate onAdvance={advance} /> : null}
						{step === 3 ? <StepHealth onAdvance={advance} /> : null}
						{step === 4 ? <StepCreate /> : null}
					</div>
				</div>
			</div>
		</ActiveSubmitContext.Provider>
	);
}
