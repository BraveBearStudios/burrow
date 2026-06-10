// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// layoutStore owns the react-mosaic layout (UI-02) + the active workspace, the
// ONLY persisted client state in Burrow. It holds the MosaicNode<string> tree
// and activeWorkspaceId, mutates it (open / split / close / setActive), persists
// just those two keys to localStorage (zustand `persist` + `partialize`), and
// reconciles the persisted tree against the live workspace list on load (UI-05):
// leaves whose id is gone are dropped, the tree rebalances, and the active id is
// retargeted to a surviving leaf (or null). Workspace *status* never lives here —
// it stays in TanStack Query (Pitfall 11), so this store is pure view state.

import type {
	MosaicDirection,
	MosaicNode,
} from "react-mosaic-component/lib/types";
// Import the tree utilities from the deep util path, not the package barrel:
// the barrel re-exports the <Mosaic> React components, which transitively pull
// react-mosaic's bundled react-dom@16 and crash in this React-19 / jsdom store
// context. mosaicUtilities only depends on lodash, so the pure store + its unit
// test stay free of the React component graph.
import {
	createBalancedTreeFromLeaves,
	getLeaves,
} from "react-mosaic-component/lib/util/mosaicUtilities";
import { create } from "zustand";
import { persist } from "zustand/middleware";

/** localStorage key for the persisted layout (exported for the tests). */
export const LAYOUT_STORAGE_KEY = "burrow-layout";

export interface LayoutState {
	/** The react-mosaic tree, or null when no panels are open. */
	mosaicNode: MosaicNode<string> | null;
	/** The focused panel ↔ sidebar active row (two-way synced). */
	activeWorkspaceId: string | null;
	/** Replace the tree wholesale — the `<Mosaic onChange>` path. */
	setNode: (node: MosaicNode<string> | null) => void;
	/** Open a panel: empty → single leaf, else split-right; marks it active. */
	openPanel: (id: string) => void;
	/** Close a panel: prune the leaf + rebalance; last leaf → null. */
	closePanel: (id: string) => void;
	/** Split an open panel along `dir` (the id stays present exactly once). */
	splitPanel: (id: string, dir: MosaicDirection) => void;
	/** Mark a panel active (drives the sidebar/panel ring). */
	setActive: (id: string) => void;
	/** Drop leaves whose id is not in `liveIds`, rebalance, retarget active. */
	reconcile: (liveIds: Set<string>) => void;
}

/** True when `id` is already a leaf in `node`. */
function hasLeaf(node: MosaicNode<string> | null, id: string): boolean {
	return getLeaves(node).includes(id);
}

/**
 * Append `id` to the tree as a new leaf. An empty tree becomes the bare leaf;
 * otherwise the existing leaves + the new id are rebuilt into a balanced tree so
 * splits stay roughly equal-area (react-mosaic's own balancing helper).
 */
function addLeaf(
	node: MosaicNode<string> | null,
	id: string,
	startDirection: MosaicDirection = "row",
): MosaicNode<string> {
	if (node === null) {
		return id;
	}
	const leaves = getLeaves(node);
	if (leaves.includes(id)) {
		return node;
	}
	// createBalancedTreeFromLeaves returns non-null for a non-empty leaf list.
	return createBalancedTreeFromLeaves(
		[...leaves, id],
		startDirection,
	) as MosaicNode<string>;
}

/**
 * Rebuild the tree from exactly `leaves`, balanced. Returns null for an empty
 * list (the "no panels open" state). Used by close + reconcile to prune.
 */
function treeFromLeaves(
	leaves: string[],
	startDirection: MosaicDirection = "row",
): MosaicNode<string> | null {
	if (leaves.length === 0) {
		return null;
	}
	if (leaves.length === 1) {
		return leaves[0];
	}
	return createBalancedTreeFromLeaves(leaves, startDirection);
}

/** Pick the active id after a prune: keep it if still present, else first leaf. */
function retargetActive(
	current: string | null,
	leaves: string[],
): string | null {
	if (current && leaves.includes(current)) {
		return current;
	}
	return leaves[0] ?? null;
}

export const useLayoutStore = create<LayoutState>()(
	persist(
		(set, get) => ({
			mosaicNode: null,
			activeWorkspaceId: null,

			setNode: (node) => set({ mosaicNode: node }),

			openPanel: (id) => {
				const { mosaicNode } = get();
				if (hasLeaf(mosaicNode, id)) {
					set({ activeWorkspaceId: id });
					return;
				}
				set({ mosaicNode: addLeaf(mosaicNode, id), activeWorkspaceId: id });
			},

			closePanel: (id) => {
				const { mosaicNode, activeWorkspaceId } = get();
				const leaves = getLeaves(mosaicNode).filter((leaf) => leaf !== id);
				set({
					mosaicNode: treeFromLeaves(leaves),
					activeWorkspaceId: retargetActive(activeWorkspaceId, leaves),
				});
			},

			splitPanel: (id, dir) => {
				const { mosaicNode } = get();
				if (!hasLeaf(mosaicNode, id)) {
					return;
				}
				// Re-adding an open leaf is a no-op (deduped); split by rebuilding the
				// existing leaves balanced along `dir` so the affordance reflows them.
				set({
					mosaicNode: treeFromLeaves(getLeaves(mosaicNode), dir),
					activeWorkspaceId: id,
				});
			},

			setActive: (id) => set({ activeWorkspaceId: id }),

			reconcile: (liveIds) => {
				const { mosaicNode, activeWorkspaceId } = get();
				const survivors = getLeaves(mosaicNode).filter((leaf) =>
					liveIds.has(leaf),
				);
				set({
					mosaicNode: treeFromLeaves(survivors),
					activeWorkspaceId: retargetActive(activeWorkspaceId, survivors),
				});
			},
		}),
		{
			name: LAYOUT_STORAGE_KEY,
			// Persist ONLY the view state — never server-derived status (Pitfall 11).
			partialize: (state) => ({
				mosaicNode: state.mosaicNode,
				activeWorkspaceId: state.activeWorkspaceId,
			}),
		},
	),
);
