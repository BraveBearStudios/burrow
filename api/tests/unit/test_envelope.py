# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Envelope contract tests (PLAT-02).

The standard envelope is ``{data, meta:{requestId, timestamp}, error}``. These
tests pin the exact shape, the requestId echo, and an ISO-8601 UTC timestamp.
"""

from datetime import datetime

from lib.envelope import respond, respond_error


def _assert_meta(meta: dict[str, object]) -> None:
    """meta carries exactly requestId + an ISO-8601 UTC timestamp."""
    assert set(meta.keys()) == {"requestId", "timestamp"}
    assert isinstance(meta["requestId"], str) and meta["requestId"]
    timestamp = meta["timestamp"]
    assert isinstance(timestamp, str)
    # Parses as ISO-8601 and is UTC-aware.
    parsed = datetime.fromisoformat(timestamp)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() is not None
    assert parsed.utcoffset().total_seconds() == 0  # type: ignore[union-attr]


def test_respond_shape() -> None:
    env = respond({"hello": "world"})
    assert set(env.keys()) == {"data", "meta", "error"}
    assert env["data"] == {"hello": "world"}
    assert env["error"] is None
    _assert_meta(env["meta"])


def test_respond_error_shape() -> None:
    env = respond_error("not_found", "no such workspace")
    assert set(env.keys()) == {"data", "meta", "error"}
    assert env["data"] is None
    assert env["error"] == {"code": "not_found", "message": "no such workspace"}
    _assert_meta(env["meta"])


def test_respond_echoes_request_id() -> None:
    env = respond(None, request_id="req-123")
    assert env["meta"]["requestId"] == "req-123"


def test_respond_error_echoes_request_id() -> None:
    env = respond_error("bad", "boom", request_id="req-456")
    assert env["meta"]["requestId"] == "req-456"


def test_request_ids_are_unique_when_unspecified() -> None:
    first = respond(None)["meta"]["requestId"]
    second = respond(None)["meta"]["requestId"]
    assert first != second
