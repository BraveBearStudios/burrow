// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// NewWorkspaceModal is the create flow (UI-03) to the binding 02-UI-SPEC contract:
// a centered 400px modal collecting Name / Git repo / Branch (default `main`) /
// Node (from useNodes), with required-field validation gating a green `Create`.
//
// COSMETIC boot-progress (A3 / Pitfall 5): POST /api/v1/workspaces is SYNCHRONOUS
// in v1 — it blocks to `running` and returns the final row (no 202+poll). So the
// 4-step checklist (✓/✓/⟳/○ with a gold-topped spinner on the active step + the
// `→ 202 · polling status…` footnote) is a time-driven cosmetic animation that runs
// WHILE the in-flight mutation resolves; it makes NO real per-step API claim. On the
// resolved `running` row all steps mark ✓, then layoutStore.openPanel(id) + close.
// A server envelope error (e.g. capacity CAP-01) surfaces the message verbatim as a
// red ✕ step + an --err strip + a `Close` button (the server already compensated).
//
// DEFERRED (note in SUMMARY): migrating create to an async 202 + real status poll so
// the saga reflects true per-step worker progress is a v1.x improvement, out of scope.
//
// Tokens-only (no hex); green reserved for Create; gold reserved for the spinner
// top-arc; weight ≤500; focus-trapped with Esc-closes / Enter-submits and an
// aria-live saga region (02-UI-SPEC Accessibility).

import { useEffect, useRef, useState } from "react";
import { ApiError } from "../api/client";
import { useNodes } from "../hooks/useNodes";
import { useCreateWorkspace } from "../hooks/useWorkspaces";
import { useLayoutStore } from "../store/layoutStore";

export interface NewWorkspaceModalProps {
	/** Close the modal (backdrop click, ×, Esc, Cancel, or post-success). */
	onClose: () => void;
}

/** The cosmetic boot-progress steps (02-UI-SPEC saga; {placeholders} elided). */
const SAGA_STEPS = [
	"Reserving VMID · writing row",
	"Cloning template",
	"Starting LXC · waiting for IP",
	"Waiting for Claude (ttyd health)",
] as const;

/** 02-UI-SPEC Copywriting: the saga footnote (cosmetic — create is synchronous). */
const SAGA_FOOTNOTE = "POST /api/v1/workspaces → 202 · polling status…";

/** Cosmetic step cadence so the checklist visibly advances during the request. */
const STEP_INTERVAL_MS = 450;

type Phase = "form" | "saga" | "error";

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
	color: "var(--err)",
};

/** Inline `+` for the Create button (no icon font — 02-UI-SPEC Registry Safety). */
function PlusIcon() {
	return (
		<svg
			width="14"
			height="14"
			viewBox="0 0 24 24"
			aria-hidden="true"
			fill="none"
			stroke="currentColor"
			strokeWidth={1.5}
			strokeLinecap="round"
		>
			<line x1="12" y1="5" x2="12" y2="19" />
			<line x1="5" y1="12" x2="19" y2="12" />
		</svg>
	);
}

/** The 13px gold-topped spinner that marks the active saga step. */
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

/** A single field with a label + input + an optional required helper. */
function Field({
	id,
	label,
	value,
	onChange,
	onBlur,
	error,
	placeholder,
}: {
	id: string;
	label: string;
	value: string;
	onChange: (v: string) => void;
	onBlur: () => void;
	error?: string;
	placeholder?: string;
}) {
	return (
		<div>
			<label htmlFor={id} style={labelStyle}>
				{label}
			</label>
			<input
				id={id}
				value={value}
				placeholder={placeholder}
				onChange={(e) => onChange(e.target.value)}
				onBlur={onBlur}
				style={{
					...inputStyle,
					borderColor: error ? "var(--err)" : "var(--border-mid)",
				}}
			/>
			{error ? <span style={helperStyle}>{error}</span> : null}
		</div>
	);
}

export function NewWorkspaceModal({ onClose }: NewWorkspaceModalProps) {
	const { data: nodes } = useNodes();
	const createWorkspace = useCreateWorkspace();
	const openPanel = useLayoutStore((s) => s.openPanel);

	const [name, setName] = useState("");
	const [projectRepo, setProjectRepo] = useState("");
	const [projectBranch, setProjectBranch] = useState("main");
	// "" is the Auto (least-loaded) sentinel: the default selection, sent to the
	// backend as node: null so the service auto-selects. A non-empty value is an
	// explicit manual node pick (the unchanged path).
	const [node, setNode] = useState("");
	const [touched, setTouched] = useState<Record<string, boolean>>({});

	const [phase, setPhase] = useState<Phase>("form");
	const [activeStep, setActiveStep] = useState(0);
	const [serverError, setServerError] = useState<string | null>(null);

	const dialogRef = useRef<HTMLDivElement>(null);
	// Track the cosmetic step-advance interval so unmount cancels it.
	const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
	// Single-shot guard: a resolve-after-unmount must never re-open.
	const isMountedRef = useRef(true);
	const completedRef = useRef(false);
	// Synchronous submit latch — React `phase`/`isPending` update async, so a second
	// click in the same tick would otherwise start a second saga.
	const submittingRef = useRef(false);

	useEffect(() => {
		isMountedRef.current = true;
		return () => {
			isMountedRef.current = false;
			if (intervalRef.current) {
				clearInterval(intervalRef.current);
			}
		};
	}, []);

	// Focus the dialog on mount so Esc/Enter + the focus trap engage immediately.
	useEffect(() => {
		dialogRef.current?.focus();
	}, []);

	const requiredError = (field: string, val: string): string | undefined => {
		if (touched[field] && val.trim() === "") {
			return `${field} is required.`;
		}
		return undefined;
	};

	// Node is no longer required: the default Auto (least-loaded) choice ("" sentinel)
	// is a valid form state, so only Name + Git repo gate the Create button.
	const isValid = name.trim() !== "" && projectRepo.trim() !== "";

	const runSaga = async () => {
		setServerError(null);
		setPhase("saga");
		setActiveStep(0);
		// Cosmetic step advance while the (synchronous) request is in flight.
		intervalRef.current = setInterval(() => {
			setActiveStep((s) => Math.min(s + 1, SAGA_STEPS.length - 1));
		}, STEP_INTERVAL_MS);
		try {
			const created = await createWorkspace.mutateAsync({
				name,
				projectRepo,
				projectBranch: projectBranch.trim() || "main",
				// Auto sentinel ("") → node: null so the backend auto-selects the
				// least-loaded node; a manual pick sends the chosen node string.
				node: node || null,
			});
			if (intervalRef.current) {
				clearInterval(intervalRef.current);
				intervalRef.current = null;
			}
			// Single-shot + still-mounted guard: never open after unmount or twice.
			if (!isMountedRef.current || completedRef.current) {
				return;
			}
			completedRef.current = true;
			setActiveStep(SAGA_STEPS.length); // all steps ✓
			// Open the panel + close (the completed checklist is the visual confirm).
			openPanel(created.id);
			onClose();
		} catch (err) {
			if (intervalRef.current) {
				clearInterval(intervalRef.current);
				intervalRef.current = null;
			}
			const message =
				err instanceof ApiError ? err.message : "Create failed. Try again.";
			setServerError(message);
			setPhase("error");
		}
	};

	const onSubmit = () => {
		setTouched({ Name: true, "Git repo": true });
		// Synchronous latch: block a double-submit (Enter + click, or two clicks in
		// one tick) from starting a second saga / a second openPanel timer.
		if (!isValid || phase !== "form" || submittingRef.current) {
			return;
		}
		submittingRef.current = true;
		void runSaga();
	};

	const onKeyDown = (e: React.KeyboardEvent) => {
		if (e.key === "Escape") {
			onClose();
			return;
		}
		if (e.key === "Enter" && phase === "form" && isValid) {
			onSubmit();
		}
	};

	const title = phase === "form" ? "New workspace" : `Creating ${name}`;

	return (
		<div style={overlayStyle}>
			{/* The scrim is a real <button> so click-to-dismiss is keyboard-accessible
			    and lint-clean; the dialog (Esc-closable) sits above it. */}
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
				aria-label={title}
				// Focused on mount so Esc/Enter + the focus trap work (02-UI-SPEC a11y).
				tabIndex={-1}
				onKeyDown={onKeyDown}
				style={{ ...modalStyle, position: "relative", outline: "none" }}
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
						{title}
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

				{phase === "form" ? (
					<div
						style={{
							display: "flex",
							flexDirection: "column",
							gap: "14px",
							padding: "17px 19px",
						}}
					>
						<Field
							id="ws-name"
							label="Name"
							value={name}
							onChange={setName}
							onBlur={() => setTouched((t) => ({ ...t, Name: true }))}
							error={requiredError("Name", name)}
							placeholder="project-omega"
						/>
						<Field
							id="ws-repo"
							label="Git repo"
							value={projectRepo}
							onChange={setProjectRepo}
							onBlur={() => setTouched((t) => ({ ...t, "Git repo": true }))}
							error={requiredError("Git repo", projectRepo)}
							placeholder="github.com/acme/omega"
						/>
						<div style={{ display: "flex", gap: "12px" }}>
							<div style={{ flex: 1 }}>
								<label htmlFor="ws-branch" style={labelStyle}>
									Branch
								</label>
								<input
									id="ws-branch"
									value={projectBranch}
									onChange={(e) => setProjectBranch(e.target.value)}
									style={inputStyle}
								/>
							</div>
							<div style={{ width: "128px" }}>
								<label htmlFor="ws-node" style={labelStyle}>
									Node
								</label>
								<select
									id="ws-node"
									value={node}
									onChange={(e) => setNode(e.target.value)}
									onBlur={() => setTouched((t) => ({ ...t, Node: true }))}
									style={{ ...inputStyle, padding: "0 6px" }}
								>
									{/* Auto (least-loaded) is the default: value "" → node null →
									    the backend auto-selects. Manual picks follow below. */}
									<option value="">Auto (least-loaded)</option>
									{(nodes ?? []).map((n) => (
										<option key={n.node} value={n.node}>
											{n.node}
										</option>
									))}
								</select>
							</div>
						</div>

						<footer
							style={{
								display: "flex",
								justifyContent: "flex-end",
								gap: "8px",
								marginTop: "3px",
							}}
						>
							<button
								type="button"
								onClick={onClose}
								style={{
									height: "32px",
									padding: "0 14px",
									background: "var(--bg-panel-alt)",
									color: "var(--text)",
									border: "0.5px solid var(--border-mid)",
									borderRadius: "var(--radius-control)",
									fontFamily: "var(--font-sans)",
									fontSize: "13px",
									fontWeight: 500,
									cursor: "pointer",
								}}
							>
								Cancel
							</button>
							<button
								type="button"
								onClick={onSubmit}
								disabled={!isValid}
								style={{
									display: "inline-flex",
									alignItems: "center",
									gap: "6px",
									height: "32px",
									padding: "0 14px",
									background: "var(--accent)",
									color: "var(--btn-pri-text)",
									border: "none",
									borderRadius: "var(--radius-control)",
									fontFamily: "var(--font-sans)",
									fontSize: "13px",
									fontWeight: 500,
									cursor: isValid ? "pointer" : "not-allowed",
									opacity: isValid ? 1 : 0.5,
								}}
							>
								<PlusIcon />
								Create
							</button>
						</footer>
					</div>
				) : (
					<div
						role="status"
						aria-live="polite"
						style={{
							display: "flex",
							flexDirection: "column",
							gap: "11px",
							padding: "19px",
							fontFamily: "var(--font-mono)",
							fontSize: "12.5px",
						}}
					>
						{SAGA_STEPS.map((step, i) => {
							const isActive = phase === "saga" && i === activeStep;
							const isErrorStep = phase === "error" && i === activeStep;
							return (
								<div
									key={step}
									style={{
										display: "flex",
										alignItems: "center",
										gap: "9px",
										color:
											i < activeStep
												? "var(--text)"
												: isErrorStep
													? "var(--err)"
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
										{isErrorStep ? (
											"✕"
										) : isActive ? (
											<StepSpinner />
										) : i < activeStep ? (
											"✓"
										) : (
											"○"
										)}
									</span>
									<span>{step}</span>
								</div>
							);
						})}

						{phase === "error" && serverError ? (
							<div
								style={{
									marginTop: "4px",
									padding: "8px 11px",
									borderRadius: "var(--radius-control)",
									background: "var(--bg-panel-alt)",
									borderLeft: "2px solid var(--err)",
									color: "var(--err)",
									fontFamily: "var(--font-sans)",
									fontSize: "12px",
								}}
							>
								{serverError}
							</div>
						) : (
							<span style={{ color: "var(--text-muted)", fontSize: "11.5px" }}>
								{SAGA_FOOTNOTE}
							</span>
						)}

						{phase === "error" ? (
							<footer style={{ display: "flex", justifyContent: "flex-end" }}>
								<button
									type="button"
									onClick={onClose}
									style={{
										height: "32px",
										padding: "0 14px",
										background: "var(--bg-panel-alt)",
										color: "var(--text)",
										border: "0.5px solid var(--border-mid)",
										borderRadius: "var(--radius-control)",
										fontFamily: "var(--font-sans)",
										fontSize: "13px",
										fontWeight: 500,
										cursor: "pointer",
									}}
								>
									Close
								</button>
							</footer>
						) : null}
					</div>
				)}
			</div>
		</div>
	);
}
