// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// useAdminStore holds the credential-surface admin secret for the SESSION ONLY
// (ADR-0015 / CRED-02). It is deliberately IN-MEMORY: no zustand `persist`, no
// localStorage/sessionStorage, and it never reaches the TanStack Query cache. A
// page reload drops it, so the operator re-enters the secret — the secret is
// never durable client-side. Admin-gated hooks read `secret` and pass it as the
// `X-Burrow-Admin` header; a rejected gate calls `clear()`.

import { create } from "zustand";

export interface AdminState {
	/** The admin secret for this session, or null when not yet entered / cleared. */
	secret: string | null;
	/** Set the in-memory secret (from the wizard step or the unlock prompt). */
	setSecret: (secret: string) => void;
	/** Drop the secret (logout / a rejected admin gate). */
	clear: () => void;
}

/**
 * Plain in-memory store — NO persist middleware by design. The secret must never
 * be written to any web storage or survive a reload (ADR-0015 hardening).
 */
export const useAdminStore = create<AdminState>((set) => ({
	secret: null,
	setSecret: (secret) => set({ secret }),
	clear: () => set({ secret: null }),
}));
