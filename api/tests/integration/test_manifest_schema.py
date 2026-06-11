# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Unit: the committed plugin manifest validates against its JSON-Schema (WORK-05).

Catches manifest drift in CI (Pitfall 5) and proves an unknown plugin ``type`` is
rejected fail-closed (the locked decision). The same ``manifest.schema.json`` is the
single source of truth shared with the boot-time jq gate in ``burrow-boot.sh`` — the
boot enum and this schema enum must stay identical so CI and boot never diverge.
"""

import json
import pathlib

import jsonschema
import pytest

# api/tests/integration/test_manifest_schema.py → parents[3] is the repo root
# (parents[0]=integration, [1]=tests, [2]=api, [3]=repo root).
_ROOT = pathlib.Path(__file__).resolve().parents[3]
_MANIFEST = _ROOT / "cc-worker-config" / "plugins" / "manifest.json"
_SCHEMA = _ROOT / "cc-worker-config" / "plugins" / "manifest.schema.json"


def test_repo_root_depth_reaches_actual_root() -> None:
    """Guard the ``parents[3]`` assumption: the manifest + schema files exist there."""
    assert _SCHEMA.is_file(), f"schema not at expected repo-root depth: {_SCHEMA}"
    assert _MANIFEST.is_file(), f"manifest not at expected repo-root depth: {_MANIFEST}"


def test_committed_manifest_matches_schema() -> None:
    """The committed manifest validates against the schema (raises nothing)."""
    schema = json.loads(_SCHEMA.read_text())
    manifest = json.loads(_MANIFEST.read_text())
    jsonschema.validate(manifest, schema)  # raises ValidationError on drift (Pitfall 5)


def test_unknown_type_is_rejected() -> None:
    """An unsupported plugin ``type`` raises (fail-closed enum, the locked decision)."""
    schema = json.loads(_SCHEMA.read_text())
    bad = {
        "schemaVersion": "1.0.0",
        "plugins": {"x": {"source": "s", "ref": "r", "type": "wat"}},
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)


def test_committed_claude_plugins_pin_immutable_refs() -> None:
    """No ``claude-plugin`` entry may pin the mutable ``main`` ref (Pitfall 1, SC-2)."""
    manifest = json.loads(_MANIFEST.read_text())
    for name, entry in manifest["plugins"].items():
        if entry["type"] == "claude-plugin":
            assert entry["ref"] != "main", (
                f"claude-plugin {name!r} pins mutable ref 'main' — not reproducible"
            )
