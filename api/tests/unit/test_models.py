# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Model alias round-trip tests (PLAT-09).

``CamelModel`` accepts snake_case (Python/DB) field names on input and emits
camelCase JSON on output. These tests pin both directions on ``Workspace`` and
confirm the ``WorkspaceStatus`` literal rejects an unknown status.
"""

import pytest
from pydantic import ValidationError

from models.workspace import Workspace

_SNAKE_ROW = {
    "id": "ws-1",
    "name": "demo",
    "status": "running",
    "vmid": 201,
    "node": "pve1",
    "lxc_ip": "10.99.0.201",
    "project_repo": "git@example.com:acme/app.git",
    "project_branch": "main",
    "plugin_set": "default",
    "created_at": "2026-06-10T00:00:00.000Z",
    "stopped_at": None,
    "destroyed_at": None,
    "deleted_at": None,
}


def test_accepts_snake_case_and_emits_camel_case() -> None:
    ws = Workspace.model_validate(_SNAKE_ROW)
    dumped = ws.model_dump(by_alias=True)
    # camelCase aliases on output.
    assert dumped["lxcIp"] == "10.99.0.201"
    assert dumped["projectRepo"] == "git@example.com:acme/app.git"
    assert dumped["projectBranch"] == "main"
    assert dumped["pluginSet"] == "default"
    assert dumped["createdAt"] == "2026-06-10T00:00:00.000Z"
    # snake_case keys are NOT present on the camelCase wire shape.
    assert "lxc_ip" not in dumped
    assert "project_repo" not in dumped


def test_accepts_camel_case_input() -> None:
    camel_row = {
        "id": "ws-2",
        "name": "demo2",
        "status": "creating",
        "vmid": None,
        "node": "pve1",
        "lxcIp": None,
        "projectRepo": "git@example.com:acme/app2.git",
        "projectBranch": "dev",
        "pluginSet": "default",
        "createdAt": "2026-06-10T00:00:00.000Z",
        "stoppedAt": None,
        "destroyedAt": None,
        "deletedAt": None,
    }
    ws = Workspace.model_validate(camel_row)
    assert ws.project_repo == "git@example.com:acme/app2.git"
    assert ws.project_branch == "dev"
    assert ws.lxc_ip is None


def test_round_trip_snake_to_camel_to_snake() -> None:
    ws = Workspace.model_validate(_SNAKE_ROW)
    camel = ws.model_dump(by_alias=True)
    again = Workspace.model_validate(camel)
    assert again == ws


def test_rejects_invalid_status() -> None:
    bad = {**_SNAKE_ROW, "status": "zombie"}
    with pytest.raises(ValidationError):
        Workspace.model_validate(bad)
