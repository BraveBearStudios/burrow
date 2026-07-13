// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// AuditPanel is the read-only credential audit trail on the Credentials screen
// (CRED-05 UI). It renders the admin-gated GET /setup/audit rows newest-first
// (the backend already orders createdAt DESC — this trusts that order rather than
// re-sorting) in a mono table: action / target / outcome / when / source. It is
// display-only — no controls mutate anything, and no secret value is ever shown
// (audit `detail` carries only a ****last4 marker the backend wrote). Tokens-only
// colors; the outcome cell tints --ok for success and --err for failure.

import { useAudit } from "../hooks/useSetup";
import type { AuditEntry } from "../types/setup";

const wrapStyle: React.CSSProperties = {
	display: "flex",
	flexDirection: "column",
	gap: "8px",
};

const headingStyle: React.CSSProperties = {
	fontFamily: "var(--font-sans)",
	fontSize: "11px",
	fontWeight: 500,
	letterSpacing: "1.3px",
	textTransform: "uppercase",
	color: "var(--text-muted)",
};

const scrollStyle: React.CSSProperties = {
	maxHeight: "220px",
	overflow: "auto",
	border: "0.5px solid var(--border)",
	borderRadius: "var(--radius-control)",
	background: "var(--bg-panel-alt)",
};

const tableStyle: React.CSSProperties = {
	width: "100%",
	borderCollapse: "collapse",
	fontFamily: "var(--font-mono)",
	fontSize: "12px",
};

const thStyle: React.CSSProperties = {
	position: "sticky",
	top: 0,
	textAlign: "left",
	padding: "7px 10px",
	background: "var(--bg-panel)",
	borderBottom: "0.5px solid var(--border)",
	color: "var(--text-sub)",
	fontWeight: 500,
};

const tdStyle: React.CSSProperties = {
	padding: "6px 10px",
	borderBottom: "0.5px solid var(--border)",
	color: "var(--text)",
	whiteSpace: "nowrap",
};

const mutedNote: React.CSSProperties = {
	padding: "12px",
	fontFamily: "var(--font-sans)",
	fontSize: "12px",
	color: "var(--text-sub)",
};

/** Render a nullable cell value, showing an em-free dash placeholder for null. */
function cell(value: string | null): string {
	return value == null || value === "" ? "·" : value;
}

/** One audit row; the outcome is color-coded (never color-only — the word shows). */
function AuditRow({ entry }: { entry: AuditEntry }) {
	const outcomeColor =
		entry.outcome === "success"
			? "var(--ok)"
			: entry.outcome === "failure"
				? "var(--err)"
				: "var(--text)";
	return (
		<tr>
			<td style={tdStyle}>{entry.action}</td>
			<td style={tdStyle}>{cell(entry.target)}</td>
			<td style={{ ...tdStyle, color: outcomeColor }}>{entry.outcome}</td>
			<td style={tdStyle}>{entry.createdAt}</td>
			<td style={tdStyle}>{cell(entry.sourceIp)}</td>
		</tr>
	);
}

/** The read-only audit trail (CRED-05 UI), fed by the admin-gated useAudit query. */
export function AuditPanel() {
	const audit = useAudit();
	const entries = audit.data?.entries ?? [];

	return (
		<section aria-label="Audit trail" style={wrapStyle}>
			<span style={headingStyle}>Audit trail</span>
			<div style={scrollStyle}>
				{audit.isLoading ? (
					<div style={mutedNote}>Loading audit trail…</div>
				) : audit.isError ? (
					<div style={mutedNote}>Could not load the audit trail.</div>
				) : entries.length === 0 ? (
					<div style={mutedNote}>No audit entries yet.</div>
				) : (
					<table style={tableStyle}>
						<thead>
							<tr>
								<th style={thStyle}>Action</th>
								<th style={thStyle}>Target</th>
								<th style={thStyle}>Outcome</th>
								<th style={thStyle}>When</th>
								<th style={thStyle}>Source</th>
							</tr>
						</thead>
						<tbody>
							{entries.map((entry) => (
								<AuditRow key={entry.id} entry={entry} />
							))}
						</tbody>
					</table>
				)}
			</div>
		</section>
	);
}
