# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Auto node-selection unit matrix (WSX-01, criterion 5).

``WorkspaceService.selectNode()`` picks the least-loaded node that fits under the
capacity threshold when the operator supplies no node. The behaviors below are the
LOCKED selection contract (09-RESEARCH §"The selection algorithm"):

- least-loaded-fitting node is chosen,
- an over-threshold node is never chosen,
- a node at exactly the threshold is eligible (``_fits`` is ``<=``),
- equally-loaded candidates tie-break by node NAME ascending (deterministic),
- a node whose ``getNodeMemory`` raises is skipped (degrade-not-500 parity),
- no node fits -> the existing ``CapacityError`` (``capacity_exceeded``) with a
  manual-pick hint, and NO row is persisted (selection precedes reservation).

``selectNode`` is exercised directly over a ``FakeComputeProvider(node_fractions=…)``
and a settings object whose ``worker_nodes`` / ``capacity_threshold`` are monkeypatched
per test — no DB or saga is needed for the selection unit.
"""

from dataclasses import dataclass
from pathlib import Path

import pytest

from compute.fakeProvider import FakeComputeProvider
from db.sqliteProvider import SqliteProvider
from lib.errors import CapacityError
from models.workspace import WorkspaceCreate
from services.workspaceService import WorkspaceService

from config import settings as real_settings


@dataclass
class _DbSettings:
    database_path: str


@pytest.fixture
async def db(tmp_path: Path) -> SqliteProvider:
    provider = SqliteProvider(_DbSettings(database_path=str(tmp_path / "select.db")))
    await provider.migrate()
    return provider


def _service(
    compute: FakeComputeProvider,
    db: SqliteProvider,
    monkeypatch: pytest.MonkeyPatch,
    *,
    worker_nodes: list[str],
    threshold: float | None = None,
) -> WorkspaceService:
    """Build a service over the Fake with monkeypatched topology/threshold.

    Mutates the shared ``real_settings`` singleton via ``monkeypatch`` (auto-restored
    at teardown) so each test sets its own ``worker_nodes`` candidate list without
    leaking into the next test.
    """
    monkeypatch.setattr(real_settings, "worker_nodes", worker_nodes, raising=False)
    if threshold is not None:
        monkeypatch.setattr(real_settings, "capacity_threshold", threshold, raising=False)
    return WorkspaceService(compute=compute, db=db, settings=real_settings)


# ── selectNode matrix ──────────────────────────────────────────────────────


async def test_selects_least_loaded_fitting_node(
    db: SqliteProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Least-loaded fitting node wins: pve2 (0.3) over pve1 (0.6) and pve3 (0.5)."""
    compute = FakeComputeProvider(node_fractions={"pve1": 0.6, "pve2": 0.3, "pve3": 0.5})
    service = _service(
        compute, db, monkeypatch, worker_nodes=["pve1", "pve2", "pve3"], threshold=0.80
    )

    assert await service.selectNode() == "pve2"


async def test_over_threshold_node_is_skipped(
    db: SqliteProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An over-threshold node (pve1 0.9) is never chosen; pve2 (0.3) wins."""
    compute = FakeComputeProvider(node_fractions={"pve1": 0.9, "pve2": 0.3})
    service = _service(compute, db, monkeypatch, worker_nodes=["pve1", "pve2"], threshold=0.80)

    assert await service.selectNode() == "pve2"


async def test_boundary_node_at_threshold_is_eligible(
    db: SqliteProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A node at exactly the threshold (0.80) is eligible (``_fits`` is ``<=``)."""
    compute = FakeComputeProvider(node_fractions={"pve1": 0.80})
    service = _service(compute, db, monkeypatch, worker_nodes=["pve1"], threshold=0.80)

    assert await service.selectNode() == "pve1"


async def test_tie_breaks_by_node_name_ascending(
    db: SqliteProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Equal fractions tie-break by node name ascending: pve1 over pve2 at 0.4."""
    compute = FakeComputeProvider(node_fractions={"pve2": 0.4, "pve1": 0.4})
    # worker_nodes lists pve2 first to prove the tie-break is by NAME, not order.
    service = _service(compute, db, monkeypatch, worker_nodes=["pve2", "pve1"], threshold=0.80)

    assert await service.selectNode() == "pve1"


async def test_no_fit_raises_capacity_error_with_manual_pick_hint(
    db: SqliteProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """All nodes over threshold -> CapacityError (capacity_exceeded) + manual-pick hint."""
    compute = FakeComputeProvider(node_fractions={"pve1": 0.95, "pve2": 0.9})
    service = _service(compute, db, monkeypatch, worker_nodes=["pve1", "pve2"], threshold=0.80)

    with pytest.raises(CapacityError) as excinfo:
        await service.selectNode()

    assert excinfo.value.code == "capacity_exceeded"
    assert "manual" in str(excinfo.value).lower()
    # Selection precedes reservation: no workspace row is persisted on a no-fit.
    assert await db.listWorkspaces() == []


async def test_raising_node_is_skipped_then_fitting_node_chosen(
    db: SqliteProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A node whose getNodeMemory raises is skipped; a remaining fitting node wins."""
    compute = FakeComputeProvider(node_fractions={"pve2": 0.3})
    original = compute.getNodeMemory

    async def _raise_pve1(node: str) -> float:
        if node == "pve1":
            raise RuntimeError("compute backend down for pve1")
        return await original(node)

    monkeypatch.setattr(compute, "getNodeMemory", _raise_pve1)
    service = _service(compute, db, monkeypatch, worker_nodes=["pve1", "pve2"], threshold=0.80)

    assert await service.selectNode() == "pve2"


async def test_all_nodes_raising_raises_capacity_error(
    db: SqliteProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If every candidate's getNodeMemory raises, none fit -> CapacityError."""
    compute = FakeComputeProvider()

    async def _always_raise(node: str) -> float:
        raise RuntimeError("compute backend down")

    monkeypatch.setattr(compute, "getNodeMemory", _always_raise)
    service = _service(compute, db, monkeypatch, worker_nodes=["pve1", "pve2"], threshold=0.80)

    with pytest.raises(CapacityError) as excinfo:
        await service.selectNode()

    assert excinfo.value.code == "capacity_exceeded"


# ── WorkspaceCreate.node Optional ───────────────────────────────────────────


def test_workspace_create_node_defaults_to_none_when_omitted() -> None:
    """Omitting ``node`` defaults to None (auto signal)."""
    payload = WorkspaceCreate(name="auto", project_repo="git@example.com:acme/auto.git")
    assert payload.node is None


def test_workspace_create_node_explicit_none_is_valid() -> None:
    """An explicit ``node=None`` is valid (auto signal)."""
    payload = WorkspaceCreate(
        name="auto", project_repo="git@example.com:acme/auto.git", node=None
    )
    assert payload.node is None


def test_workspace_create_explicit_node_is_preserved() -> None:
    """An explicit node string is the unchanged manual path."""
    payload = WorkspaceCreate(
        name="manual", project_repo="git@example.com:acme/manual.git", node="pve3"
    )
    assert payload.node == "pve3"
