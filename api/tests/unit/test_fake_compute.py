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
