# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Nodes router — read-only per-node capacity ``GET /api/v1/nodes`` (UI-04).

A thin, envelope-wrapped capacity view the UI's status bar / top-bar chips read
(UI-04). For each known node (v1: the single ``settings.default_node``) it reports
the compute backend's real used-memory FRACTION (``getNodeMemory``), the configured
``capacity_threshold``, and the strict over-threshold flag the capacity guard uses
(CAP-01: ``fraction > threshold``; the boundary ``== threshold`` is NOT over).

It exposes only what the provider can actually supply — no fabricated "free GB". The
UI derives its chip text from these real numbers.

Degrade-not-500 (mirrors ``health.py``): if ``getNodeMemory`` raises, the node is
reported with ``memoryUsedFraction = null`` and ``overThreshold = false`` at HTTP 200,
so a single unreachable backend never yields a 500 error oracle (T-02-06).
"""

from fastapi import APIRouter, Depends

from compute.provider import ComputeProvider
from config import settings
from lib.envelope import respond

from main import get_compute

router = APIRouter(prefix="/api/v1")


async def _node_capacity(compute: ComputeProvider, node: str) -> dict[str, object]:
    """Build one node's capacity row; degrade to a null fraction on any error.

    ``capacity_threshold`` is read live from ``settings`` so a runtime override is
    honored. ``overThreshold`` is the strict ``fraction > threshold`` guard (CAP-01),
    with the boundary (``==``) deliberately NOT over.
    """
    threshold = settings.capacity_threshold
    try:
        fraction: float | None = await compute.getNodeMemory(node)
    except Exception:
        fraction = None
    over_threshold = fraction is not None and fraction > threshold
    return {
        "node": node,
        "memoryUsedFraction": fraction,
        "capacityThreshold": threshold,
        "overThreshold": over_threshold,
    }


@router.get("/nodes")
async def list_nodes(
    compute: ComputeProvider = Depends(get_compute),
) -> dict[str, object]:
    """Return per-node capacity (fraction + threshold + over flag); degrade, never 500."""
    nodes = [await _node_capacity(compute, settings.default_node)]
    return respond(nodes)
