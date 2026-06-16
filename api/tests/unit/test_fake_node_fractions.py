# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""FakeComputeProvider per-node fraction tests (WSX-01, Wave 0).

The auto-select matrix (Plan 02) proves multi-node placement over the Fake, so the
Fake must report a DIFFERENT used-memory fraction per node name. This is an OPTIONAL
``node_fractions`` kwarg with a single-float fallback, so every existing caller
(``FakeComputeProvider()`` / ``FakeComputeProvider(node_memory=...)``) stays unchanged.
"""

import pytest

from compute.fakeProvider import FakeComputeProvider


async def test_default_fraction_unchanged_without_kwargs() -> None:
    """Backward-compat: no kwargs -> the 0.25 float default for any node."""
    fake = FakeComputeProvider()
    assert await fake.getNodeMemory("anynode") == pytest.approx(0.25)


async def test_single_float_fallback_unchanged() -> None:
    """Backward-compat: node_memory=0.90 -> 0.90 for any node (single-float path)."""
    fake = FakeComputeProvider(node_memory=0.90)
    assert await fake.getNodeMemory("pve1") == pytest.approx(0.90)


async def test_per_node_fraction_lookup() -> None:
    """node_fractions maps each node name to its own fraction."""
    fake = FakeComputeProvider(node_fractions={"pve1": 0.6, "pve2": 0.3})
    assert await fake.getNodeMemory("pve1") == pytest.approx(0.6)
    assert await fake.getNodeMemory("pve2") == pytest.approx(0.3)


async def test_node_absent_from_dict_falls_back_to_single_value() -> None:
    """A node not in node_fractions falls back to the single node_memory value."""
    fake = FakeComputeProvider(node_fractions={"pve1": 0.6}, node_memory=0.25)
    # pve1 is in the dict.
    assert await fake.getNodeMemory("pve1") == pytest.approx(0.6)
    # pve2 is NOT in the dict -> single-float fallback.
    assert await fake.getNodeMemory("pve2") == pytest.approx(0.25)
