# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Shared capacity comparator (WSX-01, CAP-01).

``_fits(fraction, threshold)`` is the SINGLE source of truth for "does this node's
used-memory fraction fit under the capacity threshold". Both ``GET /api/v1/nodes``
(the UI's displayed capacity) and (Plan 02) auto-select call it, so the displayed
capacity and the placement decision can never drift (T-09-01).

Semantics mirror the CAP-01 guard exactly: strict ``>`` refuses, the boundary ``==``
is ELIGIBLE — i.e. ``fraction <= threshold``. A node at exactly ``capacity_threshold``
fits.

This module is pure arithmetic by design (T-09-02): it imports NO provider concrete,
no ``proxmoxer``, no ``aiosqlite``, so the seam-leakage guard stays green.
"""

__all__ = ["_fits"]


def _fits(fraction: float, threshold: float) -> bool:
    """True when ``fraction`` fits under ``threshold`` (strict ``>`` refuses; ``==`` eligible)."""
    return fraction <= threshold
