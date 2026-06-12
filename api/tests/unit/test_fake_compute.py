# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""FakeComputeProvider contract tests (PLAT-07, PLAT-08).

The Fake honors the ``ComputeProvider`` ABC, is deterministic, and models the
lifecycle honestly (clone -> stopped, start -> running, destroy -> removed) so
the Phase-1 saga can run hermetically with zero Proxmox.
"""

import pytest

from models.compute import BootConfig

from compute.fakeProvider import FakeComputeProvider
from compute.provider import ComputeProvider, NoFreeVmidError


def test_is_compute_provider() -> None:
    assert isinstance(FakeComputeProvider(), ComputeProvider)


async def test_clone_start_getip_is_deterministic_and_stable() -> None:
    fake = FakeComputeProvider()
    # No IP before the container exists / is running.
    assert await fake.getIp("pve1", 201) is None

    clone_task = await fake.cloneCt(9000, 201, "ws-201", "pve1")
    assert clone_task.status == "ok"
    # Cloned but not started -> no IP yet.
    assert await fake.getIp("pve1", 201) is None

    start_task = await fake.startCt("pve1", 201)
    assert start_task.status == "ok"

    ip_first = await fake.getIp("pve1", 201)
    ip_second = await fake.getIp("pve1", 201)
    assert ip_first == "10.99.0.201"
    assert ip_first == ip_second  # stable across calls

    # A second provider derives the SAME IP for the same vmid (pure function).
    other = FakeComputeProvider()
    await other.cloneCt(9000, 201, "ws-201", "pve1")
    await other.startCt("pve1", 201)
    assert await other.getIp("pve1", 201) == ip_first


async def test_destroy_frees_the_vmid() -> None:
    fake = FakeComputeProvider()
    await fake.cloneCt(9000, 205, "ws-205", "pve1")
    assert 205 in await fake.usedVmids()

    await fake.destroyCt("pve1", 205)
    assert 205 not in await fake.usedVmids()
    # The freed id is reusable.
    assert await fake.getNextVmid(205, 210, set()) == 205


async def test_destroy_running_ct_is_idempotent_and_frees_vmid() -> None:
    """CR-03: destroying a *running* CT stops-then-removes it and frees the VMID.

    The cloned-but-running case (a half-started clone) must not orphan the CT.
    The Fake models the real provider's stop-then-destroy, so a destroy on a
    running container leaves no leftover and frees the id.
    """
    fake = FakeComputeProvider()
    await fake.cloneCt(9000, 206, "ws-206", "pve1")
    await fake.startCt("pve1", 206)  # CT is now RUNNING
    assert (await fake.getStatus("pve1", 206)).status == "running"

    # Destroy a running CT: no error, the container is gone, the VMID is freed.
    task = await fake.destroyCt("pve1", 206)
    assert task.status == "ok"
    assert 206 not in await fake.usedVmids()

    # Idempotent: a second destroy on the now-missing CT is still a no-op success.
    again = await fake.destroyCt("pve1", 206)
    assert again.status == "ok"


async def test_list_managed_cts_carries_the_real_node() -> None:
    """CR-01: listManagedCts pairs each VMID with the node it was cloned on."""
    fake = FakeComputeProvider()
    await fake.cloneCt(9000, 210, "ws-210", "pve1")
    await fake.cloneCt(9000, 211, "ws-211", "pve2")

    # listManagedCts yields (node, vmid); index by vmid for the assertion.
    by_vmid = {vmid: node for node, vmid in await fake.listManagedCts()}
    assert by_vmid == {210: "pve1", 211: "pve2"}
    # usedVmids is the node-discarded projection of the same set.
    assert await fake.usedVmids() == {210, 211}


async def test_destroy_on_wrong_node_is_swallowed_and_leaves_ct() -> None:
    """CR-01: a wrong-node destroy models the real provider's swallowed 404.

    Proxmox routes DELETE to nodes(node).lxc(vmid); a DELETE aimed at the wrong
    node 404s and destroyCt swallows it as idempotent success WITHOUT removing the
    CT that lives on another node. The Fake mirrors this so a reaper that targets
    the wrong node is observable (the CT survives), proving the CR-01 fix.
    """
    fake = FakeComputeProvider()
    await fake.cloneCt(9000, 212, "ws-212", "pve2")  # lives on pve2

    # Destroy aimed at the WRONG node: success envelope, but the CT is untouched.
    task = await fake.destroyCt("pve1", 212)
    assert task.status == "ok"
    assert 212 in await fake.usedVmids()  # the off-node CT was NOT removed

    # Destroy aimed at the RIGHT node removes it and frees the VMID.
    await fake.destroyCt("pve2", 212)
    assert 212 not in await fake.usedVmids()


async def test_get_next_vmid_skips_used_and_known() -> None:
    fake = FakeComputeProvider()
    await fake.cloneCt(9000, 200, "ws-200", "pve1")  # 200 now known to the provider
    # 201 passed in `used`; provider-known 200 also skipped -> first free is 202.
    assert await fake.getNextVmid(200, 210, {201}) == 202


async def test_get_next_vmid_raises_when_exhausted() -> None:
    fake = FakeComputeProvider()
    with pytest.raises(NoFreeVmidError):
        await fake.getNextVmid(200, 202, {200, 201, 202})


async def test_inject_boot_config_is_a_noop() -> None:
    fake = FakeComputeProvider()
    await fake.cloneCt(9000, 207, "ws-207", "pve1")
    config = BootConfig(
        config_repo="git@example.com:acme/config.git",
        config_branch="main",
        project_repo="git@example.com:acme/app.git",
        project_branch="main",
    )
    # Accepts and discards (no-op); mutates nothing observable.
    await fake.injectBootConfig(207, config)
    assert 207 in await fake.usedVmids()


async def test_wait_task_returns_ok() -> None:
    fake = FakeComputeProvider()
    task = await fake.waitTask("pve1", "UPID:fake:0000", timeout=5.0)
    assert task.status == "ok"
    assert task.exitstatus == "OK"


async def test_lifecycle_status_transitions() -> None:
    fake = FakeComputeProvider()
    await fake.cloneCt(9000, 208, "ws-208", "pve1")
    assert (await fake.getStatus("pve1", 208)).status == "stopped"
    await fake.startCt("pve1", 208)
    assert (await fake.getStatus("pve1", 208)).status == "running"
    await fake.stopCt("pve1", 208)
    assert (await fake.getStatus("pve1", 208)).status == "stopped"


async def test_healthcheck_is_true() -> None:
    assert await FakeComputeProvider().healthcheck() is True
