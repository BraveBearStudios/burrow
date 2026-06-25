# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""TEST-01: factories for the mocked-proxmoxer integration tier.

The hard gate that closes the structural Fake-vs-real proxmoxer gap: the in-memory
``FakeComputeProvider`` returns ``ComputeTask(upid=None, status="ok")`` instantly and
never exercises real UPID async-task polling or ``proxmoxer.core.ResourceException``
error shapes. These factories let a test drive the REAL ``ProxmoxComputeProvider``
through those exact paths over mocked HTTP.

proxmoxer rides ``requests``, so its HTTP leg is mocked with ``responses`` — NEVER
``respx`` (respx patches ``httpx`` only and would never intercept the proxmoxer leg;
RESEARCH Pitfall 3/5). Mirrors the established substrate in
``tests/integration/test_proxmox_provider.py``.

Three verified proxmoxer 2.3.0 shapes back these factories:

- ``Tasks.blocking_status`` (proxmoxer/tools/tasks.py) decodes the node from the UPID,
  then polls ``prox.nodes(node).tasks(task_id).status.get()`` until
  ``data["status"] == "stopped"``. proxmoxer unwraps the ``data`` envelope, so the
  registered status GET body is ``{"data": {"status": ..., "exitstatus": ...}}``.
- ``decode_upid`` asserts the UPID is exactly 9 colon-separated segments starting
  ``UPID:`` — a short/garbage UPID raises ``AssertionError`` and fails loudly
  (RESEARCH Pitfall 4 / threat T-10-01).
- ``ResourceException(status_code, status_message, content, errors=None, exit_code=None)``
  (proxmoxer/core.py) — the real provider's defensive ``_is_not_found`` /
  ``_is_running_or_locked`` inspectors key on ``status_code`` + message text.

Factories only (YAGNI / CONTEXT-locked): do not promote to a shared pytest fixture
until a second consumer appears.
"""

import responses
from proxmoxer.core import ResourceException


def make_upid(node: str, vmid: int, ttype: str) -> str:
    """A real-shaped 9-segment UPID (``decode_upid`` asserts exactly 9 ':' fields).

    Segments: ``UPID:node:pid:pstart:starttime:type:id:user:comment``. The pid /
    pstart / starttime fields are hex (``decode_upid`` parses them with base 16); the
    trailing comment segment is intentionally empty (the analog's UPIDs end ``:``).
    """
    return f"UPID:{node}:0000ABCD:00100000:64000000:{ttype}:{vmid}:burrow@pve:"


def register_task_poll(
    host: str,
    node: str,
    upid: str,
    *,
    exitstatus: str = "OK",
    running_polls: int = 1,
) -> None:
    """Register ``running_polls`` 'running' status GETs then one 'stopped' GET.

    ``responses`` replays registered responses in registration order, so N ``running``
    then one ``stopped`` models a real async task completing after a few polls — the
    exact ``running``->``stopped`` sequence the Fake never triggers. proxmoxer unwraps
    the ``data`` envelope, so the registered body is what ``_block`` inspects
    (``status`` + ``exitstatus``).
    """
    base = f"https://{host}:8006/api2/json"
    url = f"{base}/nodes/{node}/tasks/{upid}/status"
    for _ in range(running_polls):
        responses.add(
            responses.GET,
            url,
            json={"data": {"status": "running", "upid": upid}},
            status=200,
        )
    responses.add(
        responses.GET,
        url,
        json={"data": {"status": "stopped", "exitstatus": exitstatus, "upid": upid}},
        status=200,
    )


def resource_exception(
    status_code: int, message: str, content: str = ""
) -> ResourceException:
    """Construct a ``ResourceException`` in the verified proxmoxer shape.

    ``status_code`` + ``message`` text are exactly what the real provider's
    ``_is_not_found`` (404 / "does not exist") and ``_is_running_or_locked``
    ("running" / "is locked") inspectors read.
    """
    return ResourceException(status_code, message, content)
