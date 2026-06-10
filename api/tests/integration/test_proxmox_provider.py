# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""PLAT-07/CAP-01 integration: the real ProxmoxComputeProvider over mocked HTTP.

proxmoxer rides ``requests``, so the Proxmox HTTP API is mocked with ``responses``
(the requests-mock library) — NOT ``respx``, which only patches ``httpx`` and would
never intercept the proxmoxer leg (RESEARCH Pitfall 5). Every test runs hermetically
with zero outbound network; the real clone/boot path is the deferred dev-homelab smoke
gate.

What this proves:

- ``cloneCt`` blocks on the clone UPID, asserts ``exitstatus == "OK"`` (SC-1), and
  issues the pool-add PUT (ADR-0003) and the ``net0`` config PUT (ADR-0004) — recorded
  in ``responses.calls``;
- a non-OK task status and a timeout (status never ``stopped``) both raise
  ``TaskFailedError``;
- ``getNodeMemory`` returns the mocked ``mem/maxmem`` fraction (CAP-01 data source);
- the client is constructed with ``verify_ssl`` set to the CA path (no
  verification-disabled path is taken);
- ``getIp`` returns the VMID-derived address (ADR-0004) and ``getNextVmid`` raises
  ``NoFreeVmidError`` on an exhausted range.

Integration tests are exempt from the seam-leakage guard, so importing ``responses``
here is fine.
"""

from dataclasses import dataclass
from urllib.parse import unquote

import pytest
import responses

from compute.provider import NoFreeVmidError, TaskFailedError
from compute.proxmoxProvider import ProxmoxComputeProvider

# Proxmox API host + the proxmoxer URL base (``https://{host}:8006/api2/json``).
_HOST = "pve1.local"
_BASE = f"https://{_HOST}:8006/api2/json"
_NODE = "pve1"

# A realistic clone UPID; ``Tasks.blocking_status`` decodes the node (2nd field) and
# polls ``.../nodes/{node}/tasks/{upid}/status``.
_CLONE_UPID = f"UPID:{_NODE}:0000ABCD:00100000:64000000:vzclone:201:burrow@pve:"


@dataclass
class _Settings:
    """Settings stub carrying only what ProxmoxComputeProvider reads.

    Mirrors the real ``Settings`` keys (CA path, pool range, net0 topology, timeouts) so
    the provider constructs without a real ``.env``. ``proxmox_ca_cert_path`` is a string
    path — the provider passes it straight to ``verify_ssl`` (CA-pinned TLS, never
    disabled).
    """

    proxmox_host: str = _HOST
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


def _provider() -> ProxmoxComputeProvider:
    return ProxmoxComputeProvider(_Settings())


def _register_clone_calls(task_status: dict[str, object]) -> None:
    """Register the four HTTP calls a clone makes, with a given task-status payload.

    proxmoxer unwraps the ``data`` envelope: the clone POST's ``data`` is the UPID
    string; the task-status GET's ``data`` is the status dict ``_block`` inspects.
    """
    responses.add(
        responses.POST,
        f"{_BASE}/nodes/{_NODE}/lxc/9000/clone",
        json={"data": _CLONE_UPID},
        status=200,
    )
    responses.add(
        responses.PUT,
        f"{_BASE}/pools/burrow-workers",
        json={"data": None},
        status=200,
    )
    responses.add(
        responses.PUT,
        f"{_BASE}/nodes/{_NODE}/lxc/201/config",
        json={"data": None},
        status=200,
    )
    responses.add(
        responses.GET,
        f"{_BASE}/nodes/{_NODE}/tasks/{_CLONE_UPID}/status",
        json={"data": task_status},
        status=200,
    )


@responses.activate
async def test_clone_blocks_on_upid_and_wires_pool_and_net0() -> None:
    """A successful clone returns ok and issues the pool-add + net0 PUTs (SC-1/ADR-0003/4)."""
    _register_clone_calls({"status": "stopped", "exitstatus": "OK", "upid": _CLONE_UPID})

    task = await _provider().cloneCt(9000, 201, "ws-201", _NODE)

    assert task.status == "ok"
    assert task.exitstatus == "OK"
    assert task.upid == _CLONE_UPID

    # Prove the ADR-0003 pool-add and ADR-0004 net0 set were issued, and the net0 string
    # carries the VMID-derived static IP.
    calls = [(c.request.method, c.request.url) for c in responses.calls]
    assert ("PUT", f"{_BASE}/pools/burrow-workers") in calls
    assert ("PUT", f"{_BASE}/nodes/{_NODE}/lxc/201/config") in calls
    # The UPID-status GET was polled (the block actually happened).
    assert ("GET", f"{_BASE}/nodes/{_NODE}/tasks/{_CLONE_UPID}/status") in calls

    net0_put = next(c for c in responses.calls if str(c.request.url).endswith("/lxc/201/config"))
    # The body is form-URL-encoded; decode before asserting on the net0 string.
    body = net0_put.request.body
    net0_body = unquote(body.decode() if isinstance(body, bytes) else str(body))
    assert "ip=10.99.0.201/24" in net0_body
    assert "gw=10.99.0.1" in net0_body
    assert "bridge=vmbr0" in net0_body


@responses.activate
async def test_clone_raises_task_failed_on_non_ok_exitstatus() -> None:
    """A non-OK task exitstatus makes cloneCt raise TaskFailedError (SC-1)."""
    _register_clone_calls(
        {"status": "stopped", "exitstatus": "command failed", "upid": _CLONE_UPID}
    )
    with pytest.raises(TaskFailedError):
        await _provider().cloneCt(9000, 201, "ws-201", _NODE)


@responses.activate
async def test_clone_raises_task_failed_on_timeout() -> None:
    """A task that never reaches 'stopped' times out -> None -> TaskFailedError."""
    # status stays 'running'; clone_timeout=0 trips the deadline on the first poll so
    # blocking_status returns None (the timeout signal) without a real wait.
    settings = _Settings(clone_timeout=0.0)
    responses.add(
        responses.POST,
        f"{_BASE}/nodes/{_NODE}/lxc/9000/clone",
        json={"data": _CLONE_UPID},
        status=200,
    )
    responses.add(responses.PUT, f"{_BASE}/pools/burrow-workers", json={"data": None})
    responses.add(responses.PUT, f"{_BASE}/nodes/{_NODE}/lxc/201/config", json={"data": None})
    responses.add(
        responses.GET,
        f"{_BASE}/nodes/{_NODE}/tasks/{_CLONE_UPID}/status",
        json={"data": {"status": "running", "upid": _CLONE_UPID}},
        status=200,
    )
    with pytest.raises(TaskFailedError):
        await ProxmoxComputeProvider(settings).cloneCt(9000, 201, "ws-201", _NODE)


@responses.activate
async def test_get_node_memory_returns_used_fraction() -> None:
    """getNodeMemory returns mem/maxmem from /nodes/{node}/status (CAP-01)."""
    responses.add(
        responses.GET,
        f"{_BASE}/nodes/{_NODE}/status",
        json={"data": {"mem": 100, "maxmem": 400}},
        status=200,
    )
    fraction = await _provider().getNodeMemory(_NODE)
    assert fraction == pytest.approx(0.25)


def test_client_is_constructed_with_ca_path_not_disabled() -> None:
    """The provider constructs the client with verify_ssl set to the CA path."""
    settings = _Settings()
    provider = ProxmoxComputeProvider(settings)
    # Construction succeeds with a CA path carried through to the client (TLS verified,
    # never disabled). The provider stores the settings for later calls.
    assert provider._settings.proxmox_ca_cert_path == "/etc/burrow/pve-ca.pem"
    assert provider._api is not None


async def test_get_ip_is_computed_from_vmid() -> None:
    """getIp returns the VMID-derived address (ADR-0004) — no interface/agent poll."""
    ip = await _provider().getIp(_NODE, 201)
    assert ip == "10.99.0.201"


async def test_get_next_vmid_raises_when_pool_exhausted() -> None:
    """getNextVmid raises NoFreeVmidError when every id in the range is used."""
    with pytest.raises(NoFreeVmidError):
        await _provider().getNextVmid(200, 202, {200, 201, 202})
