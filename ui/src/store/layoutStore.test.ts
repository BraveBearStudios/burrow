// SPDX-FileCopyrightText: 2026 Brave Bear Studios
// SPDX-License-Identifier: AGPL-3.0-or-later

// layoutStore tests (UI-02 tree mutations + UI-05 reconcile + persistence).
// The store owns the react-mosaic MosaicNode tree + the active workspace id;
// it persists ONLY those two keys to localStorage (no server status mirroring,
// Pitfall 11) and reconciles the persisted tree against the live workspace list
// on load (gone leaves dropped, the tree rebalances, active id retargeted).

import type { MosaicNode } from "react-mosaic-component/lib/types";
import { getLeaves } from "react-mosaic-component/lib/util/mosaicUtilities";
import { beforeEach, describe, expect, it } from "vitest";
import { LAYOUT_STORAGE_KEY, useLayoutStore } from "./layoutStore";

/** Reset the store + persisted state so each test starts from an empty tree. */
function resetStore(): void {
	localStorage.clear();
	useLayoutStore.setState({ mosaicNode: null, activeWorkspaceId: null });
}

/** Sorted leaf ids of the current tree — order-independent membership checks. */
function leafSet(node: MosaicNode<string> | null): string[] {
	return getLeaves(node).sort();
}

describe("layoutStore — tree mutations (UI-02)", () => {
	beforeEach(resetStore);

	it("openPanel on an empty tree sets a single leaf + active id", () => {
		useLayoutStore.getState().openPanel("a");
		const { mosaicNode, activeWorkspaceId } = useLayoutStore.getState();
		expect(mosaicNode).toBe("a");
		expect(activeWorkspaceId).toBe("a");
	});

	it("openPanel on a one-leaf tree splits into a row containing both ids", () => {
		const store = useLayoutStore.getState();
		store.openPanel("a");
		store.openPanel("b");
		const { mosaicNode } = useLayoutStore.getState();
		expect(typeof mosaicNode).toBe("object");
		expect((mosaicNode as { direction: string }).direction).toBe("row");
		expect(leafSet(mosaicNode)).toEqual(["a", "b"]);
		// The newly opened panel becomes active.
		expect(useLayoutStore.getState().activeWorkspaceId).toBe("b");
	});

	it("openPanel is idempotent for an already-open id (no duplicate leaf)", () => {
		const store = useLayoutStore.getState();
		store.openPanel("a");
		store.openPanel("a");
		expect(leafSet(useLayoutStore.getState().mosaicNode)).toEqual(["a"]);
	});

	it("splitPanel('column') re-orients the tree to a column split (ids appear once)", () => {
		const store = useLayoutStore.getState();
		store.openPanel("a");
		store.openPanel("b"); // default open splits along a row
		store.splitPanel("a", "column");
		const { mosaicNode } = useLayoutStore.getState();
		expect((mosaicNode as { direction: string }).direction).toBe("column");
		// The split keeps every id exactly once (balanced, not duplicated).
		expect(getLeaves(mosaicNode).filter((id) => id === "a")).toHaveLength(1);
		expect(getLeaves(mosaicNode)).toHaveLength(2);
		// The split target becomes active.
		expect(useLayoutStore.getState().activeWorkspaceId).toBe("a");
	});

	it("splitPanel on a lone open panel keeps it a single leaf (nothing to split against)", () => {
		const store = useLayoutStore.getState();
		store.openPanel("a");
		store.splitPanel("a", "column");
		expect(useLayoutStore.getState().mosaicNode).toBe("a");
	});

	it("splitPanel is a no-op for an id that is not open", () => {
		const store = useLayoutStore.getState();
		store.openPanel("a");
		store.splitPanel("ghost", "row");
		expect(getLeaves(useLayoutStore.getState().mosaicNode)).toEqual(["a"]);
	});

	it("closePanel prunes a leaf and the sibling becomes the parent", () => {
		const store = useLayoutStore.getState();
		store.openPanel("a");
		store.openPanel("b");
		store.closePanel("a");
		const { mosaicNode } = useLayoutStore.getState();
		expect(mosaicNode).toBe("b");
	});

	it("closePanel on the last leaf clears the tree to null", () => {
		const store = useLayoutStore.getState();
		store.openPanel("a");
		store.closePanel("a");
		expect(useLayoutStore.getState().mosaicNode).toBeNull();
		expect(useLayoutStore.getState().activeWorkspaceId).toBeNull();
	});

	it("setActive updates activeWorkspaceId (sidebar/panel two-way sync)", () => {
		const store = useLayoutStore.getState();
		store.openPanel("a");
		store.openPanel("b");
		store.setActive("a");
		expect(useLayoutStore.getState().activeWorkspaceId).toBe("a");
	});

	it("setNode replaces the tree (the <Mosaic onChange> path)", () => {
		const tree: MosaicNode<string> = {
			direction: "row",
			first: "a",
			second: "b",
		};
		useLayoutStore.getState().setNode(tree);
		expect(useLayoutStore.getState().mosaicNode).toEqual(tree);
	});
});

describe("layoutStore — reconcile against the live list (UI-05)", () => {
	beforeEach(resetStore);

	it("drops leaves whose id is gone and rebalances the tree", () => {
		const store = useLayoutStore.getState();
		store.openPanel("a");
		store.openPanel("b");
		store.openPanel("c");
		// Only a + c are still live (b destroyed / absent).
		store.reconcile(new Set(["a", "c"]));
		expect(leafSet(useLayoutStore.getState().mosaicNode)).toEqual(["a", "c"]);
	});

	it("clears the tree when no persisted leaf survives", () => {
		const store = useLayoutStore.getState();
		store.openPanel("a");
		store.openPanel("b");
		store.reconcile(new Set<string>());
		expect(useLayoutStore.getState().mosaicNode).toBeNull();
	});

	it("retargets activeWorkspaceId when the active workspace is gone", () => {
		const store = useLayoutStore.getState();
		store.openPanel("a");
		store.openPanel("b");
		store.setActive("b");
		// b is gone — active must move to a surviving leaf (or null).
		store.reconcile(new Set(["a"]));
		expect(useLayoutStore.getState().activeWorkspaceId).toBe("a");
	});

	it("clears activeWorkspaceId when no leaf survives", () => {
		const store = useLayoutStore.getState();
		store.openPanel("a");
		store.setActive("a");
		store.reconcile(new Set(["other"]));
		expect(useLayoutStore.getState().activeWorkspaceId).toBeNull();
	});

	it("keeps the active id when it is still live", () => {
		const store = useLayoutStore.getState();
		store.openPanel("a");
		store.openPanel("b");
		store.setActive("a");
		store.reconcile(new Set(["a", "b"]));
		expect(useLayoutStore.getState().activeWorkspaceId).toBe("a");
		expect(leafSet(useLayoutStore.getState().mosaicNode)).toEqual(["a", "b"]);
	});

	it("is a no-op on an empty tree", () => {
		useLayoutStore.getState().reconcile(new Set(["a"]));
		expect(useLayoutStore.getState().mosaicNode).toBeNull();
	});
});

describe("layoutStore — persistence (localStorage partialize)", () => {
	beforeEach(resetStore);

	it("persists ONLY mosaicNode + activeWorkspaceId (no server status)", () => {
		const store = useLayoutStore.getState();
		store.openPanel("a");
		store.openPanel("b");
		store.setActive("a");

		const raw = localStorage.getItem(LAYOUT_STORAGE_KEY);
		expect(raw).not.toBeNull();
		const persisted = JSON.parse(raw as string).state as Record<
			string,
			unknown
		>;
		// Exactly the two view-state keys — nothing else (no status mirror).
		expect(Object.keys(persisted).sort()).toEqual([
			"activeWorkspaceId",
			"mosaicNode",
		]);
		expect(persisted.activeWorkspaceId).toBe("a");
		expect(leafSet(persisted.mosaicNode as MosaicNode<string>)).toEqual([
			"a",
			"b",
		]);
	});
});
