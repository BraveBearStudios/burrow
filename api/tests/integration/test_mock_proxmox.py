# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""TEST-01 self-tests: the mock_proxmox factories drive the REAL provider.

This is the v1.3 HARD GATE (STATE blockers gate #2): it closes the structural
Fake-vs-real proxmoxer gap. The in-memory ``FakeComputeProvider`` returns
``ComputeTask(upid=None, status="ok")`` instantly and never reaches ``_block`` UPID
polling or the ``ResourceException`` inspector branches; these tests therefore drive
the REAL ``ProxmoxComputeProvider`` (never the Fake) over ``responses``-mocked HTTP,
proving the factories exercise exactly those Fake-untriggered code paths.

proxmoxer rides ``requests`` -> mocked with ``responses``, NEVER ``respx``
(RESEARCH Pitfall 3/5). Mirrors ``test_proxmox_provider.py`` (the verified analog):
the ``_Settings`` stub, the ``_provider`` helper, and the ``@responses.activate``
round-trip asserting on ``responses.calls``.
"""

from dataclasses import dataclass

import pytest
import responses

from compute.provider import TaskFailedError
from compute.proxmoxProvider import ProxmoxComputeProvider

from tests.integration.mock_proxmox import (
    make_upid,
    register_task_poll,
    resource_exception,
)


@dataclass
class _Settings:
    """Settings stub carrying only the keys ProxmoxComputeProvider reads.

    Mirrors ``test_proxmox_provider.py``'s stub: a CA path (passed straight to
    ``verify_ssl``, never disabled), the pool range, net0 topology, and timeouts.
    Values are illustrative placeholders — no real host/secret (threat T-10-03).
    """

    proxmox_host: str = "pve1.local"
    proxmox_user: str = "burrow@pve"
    proxmox_token_name: str = "burrow"
    proxmox_token_value: str = "test-token"  # noqa: S105  # placeholder, not a real secret
    proxmox_ca_cert_path: str = "/etc/burrow/pve-ca.pem"
    worker_pool_start: int = 200
    worker_pool_end: int = 299
    worker_subnet: str = "10.99.0.0/24"
    worker_gateway: str = "10.99.0.1"
    worker_bridge: str = "vmbr0"
    worker_prefix: int = 24
    clone_timeout: float = 5.0
    task_timeout: float = 5.0


def _provider(host: str) -> ProxmoxComputeProvider:
    return ProxmoxComputeProvider(_Settings(proxmox_host=host))


@responses.activate
async def test_real_provider_start_blocks_on_upid_running_to_stopped() -> None:
    """The REAL startCt blocks on a multi-poll running->stopped UPID and returns ok.

    The Fake never reaches ``_block``; this drives the real ``startCt`` -> ``_block``
    UPID polling the factories model (running x2 then stopped). Asserts the task
    resolves ok/OK with the same UPID, and that the status GET was actually polled.
    """
    host, node, vmid = "pve1.local", "pve1", 201
    upid = make_upid(node, vmid, "vzstart")
    base = f"https://{host}:8006/api2/json"
    responses.add(
        responses.POST,
        f"{base}/nodes/{node}/lxc/{vmid}/status/start",
        json={"data": upid},
        status=200,
    )
    register_task_poll(host, node, upid, exitstatus="OK", running_polls=2)

    task = await _provider(host).startCt(node, vmid)

    assert task.status == "ok"
    assert task.exitstatus == "OK"
    assert task.upid == upid
    # The block actually polled the task-status endpoint (T-10-02: prove the real
    # call happened over responses, not a silently-bypassed transport).
    status_get = ("GET", f"{base}/nodes/{node}/tasks/{upid}/status")
    calls = [(c.request.method, c.request.url) for c in responses.calls]
    assert status_get in calls


@responses.activate
async def test_real_provider_destroy_is_idempotent_on_not_found() -> None:
    """A 404-shaped ResourceException drives destroyCt's idempotent branch.

    The factory-built ``ResourceException(404, ...)`` is raised at the transport leg,
    so the REAL ``destroyCt`` hits ``_is_not_found`` and treats an already-gone CT as
    success (no raise) — a branch the Fake never reaches.
    """
    host, node, vmid = "pve1.local", "pve1", 201
    base = f"https://{host}:8006/api2/json"
    responses.add(
        responses.DELETE,
        f"{base}/nodes/{node}/lxc/{vmid}",
        body=resource_exception(404, "CT 201 does not exist"),
    )

    task = await _provider(host).destroyCt(node, vmid)

    assert task.status == "ok"
    assert task.exitstatus == "OK"


@responses.activate
async def test_real_provider_destroy_running_ct_stops_then_destroys() -> None:
    """A 500 'CT is running' ResourceException drives the stop-then-destroy retry.

    The first DELETE raises the factory-built running-shaped exception; the REAL
    ``destroyCt`` recognises it via ``_is_running_or_locked``, issues a UPID-blocked
    stop, then retries the DELETE (which now succeeds) — the compensation path the
    Fake never exercises. Asserts the stop was issued and two DELETEs were attempted.
    """
    host, node, vmid = "pve1.local", "pve1", 201
    base = f"https://{host}:8006/api2/json"
    stop_upid = make_upid(node, vmid, "vzstop")
    destroy_upid = make_upid(node, vmid, "vzdestroy")

    # First DELETE: refused because the CT is running (factory-built 500).
    responses.add(
        responses.DELETE,
        f"{base}/nodes/{node}/lxc/{vmid}",
        body=resource_exception(500, "CT 201 is running"),
    )
    # The stop POST returns a UPID; its task completes OK.
    responses.add(
        responses.POST,
        f"{base}/nodes/{node}/lxc/{vmid}/status/stop",
        json={"data": stop_upid},
        status=200,
    )
    register_task_poll(host, node, stop_upid, exitstatus="OK", running_polls=1)
    # Retry DELETE now succeeds and returns a destroy UPID that completes OK.
    responses.add(
        responses.DELETE,
        f"{base}/nodes/{node}/lxc/{vmid}",
        json={"data": destroy_upid},
        status=200,
    )
    register_task_poll(host, node, destroy_upid, exitstatus="OK", running_polls=1)

    task = await _provider(host).destroyCt(node, vmid)

    assert task.status == "ok"
    assert task.exitstatus == "OK"

    methods_urls = [(c.request.method, c.request.url) for c in responses.calls]
    # The stop was issued between the refused and the successful DELETE (CR-03).
    assert ("POST", f"{base}/nodes/{node}/lxc/{vmid}/status/stop") in methods_urls
    delete_count = sum(1 for m, _ in methods_urls if m == "DELETE")
    assert delete_count == 2


@responses.activate
async def test_real_provider_start_raises_on_non_ok_exitstatus() -> None:
    """A stopped-but-non-OK task makes the REAL startCt surface a typed error.

    Drives ``_block``'s Mode-3 (stopped, non-OK exitstatus) — another path the Fake's
    instant ok never reaches. ``startCt`` only wraps the POST leg, so ``_block`` raises
    the typed ``TaskFailedError`` directly; no driver exception crosses the seam.
    """
    host, node, vmid = "pve1.local", "pve1", 202
    base = f"https://{host}:8006/api2/json"
    upid = make_upid(node, vmid, "vzstart")
    responses.add(
        responses.POST,
        f"{base}/nodes/{node}/lxc/{vmid}/status/start",
        json={"data": upid},
        status=200,
    )
    register_task_poll(host, node, upid, exitstatus="command failed", running_polls=1)

    with pytest.raises(TaskFailedError) as exc_info:
        await _provider(host).startCt(node, vmid)
    # The non-OK exitstatus is surfaced in the real _block failure message.
    assert "command failed" in str(exc_info.value)
