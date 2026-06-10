// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// useNodes is the TanStack Query poll of GET /api/v1/nodes (the 02-01 backend),
// the source for the Navbar capacity chips + the StatusBar capacity readout
// (UI-04). Each row is the provider's REAL used-memory fraction + threshold +
// over-flag — no fabricated "GB free" (02-UI-SPEC: show the real number). The
// poll matches the workspace list cadence so the chips stay in step with the
// sidebar; the server is the sole source of truth (no mirroring into Zustand).

import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { NodeCapacity } from "../types/workspace";

/** The query key the capacity chips + status bar share. */
export const NODES_KEY = ["nodes"] as const;

/** ~3s poll so capacity tracks the workspace list (UI-04). */
const POLL_INTERVAL_MS = 3000;

/** Poll per-node capacity (UI-04). */
export function useNodes() {
	return useQuery({
		queryKey: NODES_KEY,
		queryFn: () => api<NodeCapacity[]>("/nodes"),
		refetchInterval: POLL_INTERVAL_MS,
	});
}
