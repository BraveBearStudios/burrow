# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Shared capacity helper + worker_nodes derivation tests (WSX-01, Wave 0).

``_fits(fraction, threshold)`` is the SINGLE capacity comparator both ``/nodes`` and
(Plan 02) auto-select call, so the displayed capacity and the placement decision
never drift (T-09-01). Semantics mirror the CAP-01 guard: strict ``>`` refuses, the
boundary ``==`` is ELIGIBLE (``fraction <= threshold``).

``Settings.worker_nodes`` is the topology list auto-select iterates. Its default is
DERIVED from the resolved ``default_node`` (not a hardcoded ``["pve1"]`` literal), so a
``BURROW_DEFAULT_NODE`` / explicit ``default_node`` override propagates; an explicit
non-empty ``worker_nodes`` is left untouched.
"""

from config import Settings

from lib.capacity import _fits


def test_fits_below_threshold_is_eligible() -> None:
    assert _fits(0.79, 0.80) is True


def test_fits_at_boundary_is_eligible() -> None:
    """Boundary: fraction == threshold is ELIGIBLE (mirrors CAP-01 strict >)."""
    assert _fits(0.80, 0.80) is True


def test_fits_above_threshold_is_not_eligible() -> None:
    """Strict >: fraction above threshold refuses (no overcommit)."""
    assert _fits(0.81, 0.80) is False


def test_worker_nodes_default_tracks_default_node() -> None:
    """Default worker_nodes == [default_node], proving it is derived, not hardcoded."""
    settings = Settings()
    assert settings.worker_nodes == [settings.default_node]


def test_worker_nodes_default_follows_default_node_override() -> None:
    """An explicit default_node override propagates into the derived worker_nodes default."""
    settings = Settings(default_node="pveX")
    assert settings.worker_nodes == ["pveX"]


def test_worker_nodes_explicit_override_is_respected() -> None:
    """An explicit non-empty worker_nodes is left untouched by the validator."""
    settings = Settings(worker_nodes=["a", "b"])
    assert settings.worker_nodes == ["a", "b"]


def test_worker_nodes_normalizes_whitespace_empties_and_dupes() -> None:
    """WR-02: strip whitespace, drop empty entries, de-dup preserving order."""
    settings = Settings(worker_nodes=["pve1", "", "pve1", " pve2 "])
    assert settings.worker_nodes == ["pve1", "pve2"]


def test_worker_nodes_all_empty_falls_back_to_default_node() -> None:
    """WR-02: when nothing survives normalization, fall back to [default_node]."""
    settings = Settings(default_node="pveZ", worker_nodes=["", "  "])
    assert settings.worker_nodes == ["pveZ"]
