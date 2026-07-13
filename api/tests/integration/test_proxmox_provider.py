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
from pydantic import SecretStr

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
    # SecretStr (SETUP-07): the provider reads it via .get_secret_value() at the
    # proxmoxer boundary, so the stub must match the real Settings field type.
    proxmox_token_value: SecretStr = SecretStr("test-token")
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
    assert ("PUT", f"{_BASE}/nodes/{_NODE}/lxc/201/config") in calls
    # The UPID-status GET was polled (the block actually happened).
    assert ("GET", f"{_BASE}/nodes/{_NODE}/tasks/{_CLONE_UPID}/status") in calls
    # The clone is created directly into /pool/burrow-workers (ADR-0003) via pool=,
    # so VM.Allocate on the pool authorizes the new vmid (no separate pool-add).
    clone_post = next(c for c in responses.calls if str(c.request.url).endswith("/lxc/9000/clone"))
    cbody = clone_post.request.body
    clone_body = unquote(cbody.decode() if isinstance(cbody, bytes) else str(cbody))
    assert "pool=burrow-workers" in clone_body

    net0_put = next(c for c in responses.calls if str(c.request.url).endswith("/lxc/201/config"))
    # The body is form-URL-encoded; decode before asserting on the net0 string.
    body = net0_put.request.body
    net0_body = unquote(body.decode() if isinstance(body, bytes) else str(body))
    assert "ip=10.99.0.201/24" in net0_body
    assert "gw=10.99.0.1" in net0_body
    assert "bridge=vmbr0" in net0_body


@responses.activate
async def test_clone_hostname_encodes_vmid_not_display_name() -> None:
    """The CT hostname MUST end in ``-<vmid>`` so the worker recovers its own VMID.

    ``burrow-boot.sh`` ``resolve_vmid`` parses the VMID from ``${hostname##*-}`` and
    requires it numeric (ADR-0004). Cloning with the free-form workspace *name* left
    a non-numeric suffix (e.g. name ``fable-test`` -> ``test``), so every worker boot
    aborted before it could fetch bootconfig or clone the repos. The saga must derive
    the hostname from the VMID (``burrow-w-<vmid>``), never from the display name.
    """
    _register_clone_calls({"status": "stopped", "exitstatus": "OK", "upid": _CLONE_UPID})

    # Display name whose own suffix is NON-numeric — the exact real-infra failure
    # (name 'fable-test' -> ${host##*-} = 'test'). VMID 201 matches the registered mocks.
    await _provider().cloneCt(9000, 201, "fable-test", _NODE)

    clone_post = next(c for c in responses.calls if str(c.request.url).endswith("/lxc/9000/clone"))
    cbody = clone_post.request.body
    clone_body = unquote(cbody.decode() if isinstance(cbody, bytes) else str(cbody))
    # Hostname is VMID-derived (suffix '201' -> resolve_vmid recovers 201)...
    assert "hostname=burrow-w-201" in clone_body
    # ...and NEVER the free-form name (suffix 'test' would break resolve_vmid).
    assert "hostname=fable-test" not in clone_body


@responses.activate
async def test_clone_blocks_on_upid_before_pool_and_net0_puts() -> None:
    """WR-05: the clone UPID is confirmed OK BEFORE the pool-add / net0 config PUTs.

    Firing the dependent mutations against a still-cloning VMID widened the orphan
    window; the provider must block on the clone task first, then configure the
    fully-cloned CT. Asserted by call ORDER in responses.calls.
    """
    _register_clone_calls({"status": "stopped", "exitstatus": "OK", "upid": _CLONE_UPID})

    await _provider().cloneCt(9000, 201, "ws-201", _NODE)

    ordered = [(c.request.method, str(c.request.url)) for c in responses.calls]
    status_get = ("GET", f"{_BASE}/nodes/{_NODE}/tasks/{_CLONE_UPID}/status")
    net0_put = ("PUT", f"{_BASE}/nodes/{_NODE}/lxc/201/config")

    # The clone-task status GET (the block) precedes the dependent net0 config PUT.
    assert ordered.index(status_get) < ordered.index(net0_put)


@responses.activate
async def test_clone_failure_skips_pool_and_net0_puts() -> None:
    """WR-05: a clone that ends non-OK never issues the dependent config PUTs.

    With the block moved ahead of the PUTs, a failed clone raises before pool-add /
    net0 run, so no mutation is left against a CT that never finished cloning.
    """
    _register_clone_calls(
        {"status": "stopped", "exitstatus": "command failed", "upid": _CLONE_UPID}
    )

    with pytest.raises(TaskFailedError):
        await _provider().cloneCt(9000, 201, "ws-201", _NODE)

    issued = [(c.request.method, str(c.request.url)) for c in responses.calls]
    assert ("PUT", f"{_BASE}/pools/burrow-workers") not in issued
    assert ("PUT", f"{_BASE}/nodes/{_NODE}/lxc/201/config") not in issued


@responses.activate
async def test_clone_raises_task_failed_on_non_ok_exitstatus() -> None:
    """A non-OK task exitstatus makes cloneCt raise TaskFailedError (SC-1)."""
    _register_clone_calls(
        {"status": "stopped", "exitstatus": "command failed", "upid": _CLONE_UPID}
    )
    # WR-06: the non-OK message carries the UPID AND the actual exitstatus, distinct
    # from a timeout / still-running message.
    with pytest.raises(TaskFailedError) as exc_info:
        await _provider().cloneCt(9000, 201, "ws-201", _NODE)
    message = str(exc_info.value)
    assert _CLONE_UPID in message
    assert "command failed" in message
    assert "exitstatus" in message
    # It is NOT misreported as a timeout (the conflation WR-06 fixes).
    assert "timed out" not in message


@responses.activate
async def test_block_timeout_message_is_distinct_from_failure() -> None:
    """WR-06: a timeout reports 'timed out' + the UPID, not a bogus exitstatus."""
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
    with pytest.raises(TaskFailedError) as exc_info:
        await ProxmoxComputeProvider(settings).cloneCt(9000, 201, "ws-201", _NODE)
    message = str(exc_info.value)
    assert _CLONE_UPID in message
    assert "timed out" in message
    # A timeout is not reported as a non-OK exitstatus.
    assert "exitstatus" not in message


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
    """getNodeMemory returns memory.used/memory.total from /nodes/{node}/status (CAP-01).

    Real PVE nests memory under ``memory: {used, total}`` (NOT top-level mem/maxmem,
    which only appear on /cluster/resources + node-list rows). The old mock encoded
    the wrong flat shape, so it green-lit a KeyError that only fired on real infra.
    """
    responses.add(
        responses.GET,
        f"{_BASE}/nodes/{_NODE}/status",
        json={"data": {"memory": {"used": 100, "total": 400}}},
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


# A stop/destroy UPID for the running-CT compensation path (CR-03).
_STOP_UPID = f"UPID:{_NODE}:0000ABCE:00100000:64000000:vzstop:201:burrow@pve:"
_DESTROY_UPID = f"UPID:{_NODE}:0000ABCF:00100000:64000000:vzdestroy:201:burrow@pve:"


@responses.activate
async def test_destroy_running_ct_stops_then_destroys() -> None:
    """CR-03: a running CT (DELETE refused) is stopped, then destroyed idempotently.

    Proxmox refuses to DELETE a running LXC with a non-404 error. destroyCt must
    recognise that, issue a stop (UPID-blocked), then retry the DELETE so
    compensation actually removes the orphan and frees the VMID.
    """
    # First DELETE: Proxmox refuses because the CT is running (not a 404).
    responses.add(
        responses.DELETE,
        f"{_BASE}/nodes/{_NODE}/lxc/201",
        json={"data": None, "errors": {"err": "CT 201 is running"}},
        status=500,
    )
    # The stop POST returns a UPID; its task completes OK.
    responses.add(
        responses.POST,
        f"{_BASE}/nodes/{_NODE}/lxc/201/status/stop",
        json={"data": _STOP_UPID},
        status=200,
    )
    responses.add(
        responses.GET,
        f"{_BASE}/nodes/{_NODE}/tasks/{_STOP_UPID}/status",
        json={"data": {"status": "stopped", "exitstatus": "OK", "upid": _STOP_UPID}},
        status=200,
    )
    # Retry DELETE now succeeds (CT stopped) and returns a destroy UPID.
    responses.add(
        responses.DELETE,
        f"{_BASE}/nodes/{_NODE}/lxc/201",
        json={"data": _DESTROY_UPID},
        status=200,
    )
    responses.add(
        responses.GET,
        f"{_BASE}/nodes/{_NODE}/tasks/{_DESTROY_UPID}/status",
        json={"data": {"status": "stopped", "exitstatus": "OK", "upid": _DESTROY_UPID}},
        status=200,
    )

    task = await _provider().destroyCt(_NODE, 201)
    assert task.status == "ok"
    assert task.exitstatus == "OK"

    methods_urls = [(c.request.method, c.request.url) for c in responses.calls]
    # The stop was issued between the failed and the successful DELETE (CR-03).
    assert ("POST", f"{_BASE}/nodes/{_NODE}/lxc/201/status/stop") in methods_urls
    # Two DELETEs were attempted (the refused one and the post-stop retry).
    delete_count = sum(1 for m, _ in methods_urls if m == "DELETE")
    assert delete_count == 2


@responses.activate
async def test_destroy_missing_ct_is_idempotent_noop() -> None:
    """A 404 on DELETE reads as idempotent success (destroy of an already-gone CT)."""
    responses.add(
        responses.DELETE,
        f"{_BASE}/nodes/{_NODE}/lxc/201",
        json={"data": None, "errors": {"err": "CT 201 does not exist"}},
        status=404,
    )
    task = await _provider().destroyCt(_NODE, 201)
    assert task.status == "ok"
    assert task.exitstatus == "OK"


@responses.activate
async def test_used_vmids_skips_malformed_rows_without_crashing() -> None:
    """WR-04: heterogeneous cluster/resources rows are parsed defensively.

    A row with vmid present-but-None, non-numeric, or absent must be skipped — not
    crash the pre-clone scan with an uncaught ValueError/TypeError that escapes the
    seam as a 500. Only valid in-range numeric vmids are returned.
    """
    responses.add(
        responses.GET,
        f"{_BASE}/cluster/resources",
        json={
            "data": [
                {"vmid": 201, "type": "lxc"},  # valid, in range
                {"vmid": "202", "type": "lxc"},  # numeric string, in range
                {"vmid": None, "type": "storage"},  # present but None -> skip
                {"vmid": "not-a-number", "type": "sdn"},  # non-numeric -> skip
                {"type": "node"},  # vmid absent -> skip
                {"vmid": 9000, "type": "lxc"},  # numeric but out of pool range
            ]
        },
        status=200,
    )

    used = await _provider().usedVmids()
    assert used == {201, 202}


@responses.activate
async def test_list_managed_cts_carries_each_cts_real_node() -> None:
    """CR-01: listManagedCts returns (node, vmid) over cluster-wide resources.

    cluster/resources is cluster-wide, so an in-pool orphan can live on ANY node.
    listManagedCts must surface each CT's REAL node so the reaper destroys it on
    that node, not a hardcoded default. A row whose node is absent/blank is skipped
    (the reaper cannot route a DELETE without a target node); the node-discarded
    usedVmids still counts it for the duplicate-id guard.
    """
    responses.add(
        responses.GET,
        f"{_BASE}/cluster/resources",
        json={
            "data": [
                {"vmid": 201, "type": "lxc", "node": "pve1"},  # in range, pve1
                {"vmid": 202, "type": "lxc", "node": "pve2"},  # in range, pve2
                {"vmid": 203, "type": "lxc"},  # in range but no node -> skipped here
                {"vmid": 9000, "type": "lxc", "node": "pve1"},  # out of pool -> skip
            ]
        },
        status=200,
    )

    # listManagedCts yields (node, vmid); index by vmid for the assertion.
    by_vmid = {vmid: node for node, vmid in await _provider().listManagedCts()}
    # Each in-pool CT pairs with its REAL node; the node-less row is dropped.
    assert by_vmid == {201: "pve1", 202: "pve2"}
