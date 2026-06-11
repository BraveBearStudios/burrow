# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Boot-harness fixtures: loopback fake control plane + bare-repo factory + stub ttyd.

These reuse the loopback-fake idiom of ``tests/integration/conftest.py`` (bind on
``127.0.0.1:0``, yield a handle, tear down automatically) but for a SUBPROCESS
substrate rather than an in-process ASGI app:

- ``fake_control_plane`` — a stdlib ``http.server`` on an ephemeral loopback port
  serving the FROZEN ``{data, meta, error}`` envelope (Shared Pattern D) at
  ``/api/v1/internal/bootconfig/<vmid>`` with ``gitCredential`` set to the
  module-level ``_SENTINEL_CREDENTIAL``. A ``down`` variant (every request 503s)
  drives the retry-then-fail test.
- ``bare_repos`` — a ``git init --bare`` factory seeding a config repo
  (``claude/CLAUDE.md`` + a tag for ref-pinning) and a project repo, exposed as
  ``file://`` paths so the boot script's clones are real-but-hermetic.
- ``manifest_config_repo`` — a factory (Plan 02) that additionally seeds a
  ``claude-plugin`` source repo (its own ``file://`` bare repo, tagged for
  ref-pinning) and writes ``plugins/manifest.json`` into the config repo so the
  boot script's ``process_manifest`` step has real, pinned, hermetic plugin
  sources to clone. Supports a ``binary`` entry (must be SKIPPED at boot) and an
  ``unknown``-type variant (must FAIL the boot fail-closed).
- ``stub_ttyd_path`` — a temp dir holding the committed ``stub_ttyd_bin`` as an
  executable named ``ttyd``, to prepend to the subprocess ``PATH`` so the boot
  completes without a real terminal (records the frozen argv instead).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

# A high-entropy value that cannot occur incidentally; if it shows up in any
# captured boot output or in worker.env, the credential leaked (T-03-01..03,
# block_on=high). Mirrors tests/integration/test_bootconfig.py.
_SENTINEL_CREDENTIAL = "SENTINEL-bootcred-9f2c4e7a1b6d8054-DO-NOT-LOG"

# Repo root from api/tests/boot/conftest.py → parents[3].
_ROOT = Path(__file__).resolve().parents[3]
_BOOT_SCRIPT = _ROOT / "cc-worker-config" / "lxc" / "worker-template" / "burrow-boot.sh"
_STUB_TTYD_BIN = Path(__file__).resolve().parent / "stub_ttyd_bin"


class FakeControlPlane:
    """A live loopback fake bootconfig endpoint plus the values the test asserts on.

    ``url`` is the ``http://127.0.0.1:<port>`` base the boot script's ``CONTROL_PLANE``
    points at. ``config_repo`` / ``project_repo`` are the ``file://`` bare-repo paths
    the served envelope advertises. ``git_credential`` is the sentinel the no-leak
    test hunts for.
    """

    def __init__(
        self,
        *,
        url: str,
        config_repo: str,
        config_branch: str,
        project_repo: str,
        project_branch: str,
        git_credential: str,
    ) -> None:
        self.url = url
        self.config_repo = config_repo
        self.config_branch = config_branch
        self.project_repo = project_repo
        self.project_branch = project_branch
        self.git_credential = git_credential


def _make_handler(payload: dict[str, str] | None) -> type[BaseHTTPRequestHandler]:
    """Build a request handler: ``payload is None`` → always 503 (the down variant)."""

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler API)
            if payload is None or "/api/v1/internal/bootconfig/" not in self.path:
                self.send_response(503)
                self.end_headers()
                return
            body = json.dumps({"data": payload, "meta": {}, "error": None}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: object) -> None:  # silence the stderr access log
            return

    return _Handler


def _seed_bare_repo(
    repos_root: Path, name: str, files: dict[str, str], tag: str | None = None
) -> str:
    """git init a work tree, commit ``files`` on ``main`` (+ optional ``tag``), bare-clone it.

    Returns the bare repo's ``file://`` URL so the boot script can clone it hermetically.
    """
    work = repos_root / f"{name}-work"
    work.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        target = work / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    env = {
        "GIT_AUTHOR_NAME": "Burrow Test",
        "GIT_AUTHOR_EMAIL": "test@example.invalid",
        "GIT_COMMITTER_NAME": "Burrow Test",
        "GIT_COMMITTER_EMAIL": "test@example.invalid",
    }

    def run(*args: str) -> None:
        subprocess.run(
            ["git", *args], cwd=work, check=True, capture_output=True, text=True, env={**env}
        )

    run("init", "-q", "-b", "main")
    run("add", "-A")
    run("commit", "-q", "-m", "seed")
    if tag is not None:
        run("tag", tag)
    bare = repos_root / f"{name}.git"
    subprocess.run(
        ["git", "clone", "-q", "--bare", str(work), str(bare)],
        check=True,
        capture_output=True,
        text=True,
    )
    return bare.as_uri()  # file:// URL


@pytest.fixture
def bare_repos(tmp_path: Path) -> dict[str, str]:
    """Create file:// bare config + project repos; return their URLs + branch + tag.

    The config repo carries ``claude/CLAUDE.md`` (the boot script copies it to
    ``~/CLAUDE.md``) and a ``plugins/manifest.json`` (the boot's ``process_manifest``
    requires one — a missing manifest fails the boot fail-closed). The manifest pins a
    single ``claude-plugin`` to a real seeded ``file://`` source repo so the happy path
    installs cleanly. The project repo carries a ``README.md``. All committed on ``main``;
    the config + plugin repos are tagged ``v1.0.0`` so ref-pinning is exercisable.
    """
    repos_root = tmp_path / "repos"
    repos_root.mkdir()
    plugin_url = _seed_bare_repo(
        repos_root,
        "plugin-example-claude-plugin",
        {"plugin.json": '{"name": "example-claude-plugin"}\n'},
        tag="v1.0.0",
    )
    manifest = (
        json.dumps(
            {
                "schemaVersion": "1.0.0",
                "plugins": {
                    "example-claude-plugin": {
                        "source": plugin_url,
                        "ref": "v1.0.0",
                        "type": "claude-plugin",
                    }
                },
            },
            indent=2,
        )
        + "\n"
    )
    config_url = _seed_bare_repo(
        repos_root,
        "cc-worker-config",
        {
            "claude/CLAUDE.md": "# Worker CLAUDE.md (seeded)\n",
            "plugins/manifest.json": manifest,
        },
        tag="v1.0.0",
    )
    project_url = _seed_bare_repo(repos_root, "project", {"README.md": "# Project (seeded)\n"})
    return {
        "config_repo": config_url,
        "config_branch": "main",
        "project_repo": project_url,
        "project_branch": "main",
    }


class ManifestConfigRepo:
    """A config repo whose ``plugins/manifest.json`` drives the boot's ``process_manifest``.

    ``config_repo`` is the ``file://`` bare config repo URL the bootconfig advertises.
    ``project_repo`` is a sibling project repo. ``claude_plugin_names`` are the entries
    that MUST be cloned into ``~/.claude/plugins/<name>``; ``skipped_names`` are the
    binary/npm-global entries that MUST NOT produce a plugin dir at boot.
    """

    def __init__(
        self,
        *,
        config_repo: str,
        project_repo: str,
        claude_plugin_names: list[str],
        skipped_names: list[str],
    ) -> None:
        self.config_repo = config_repo
        self.project_repo = project_repo
        self.config_branch = "main"
        self.project_branch = "main"
        self.claude_plugin_names = claude_plugin_names
        self.skipped_names = skipped_names


@pytest.fixture
def manifest_config_repo(tmp_path: Path) -> Callable[..., ManifestConfigRepo]:
    """Factory: build a config repo with a seeded ``plugins/manifest.json``.

    Keyword args:
      - ``include_binary`` (default True): add a ``binary`` entry that must be SKIPPED.
      - ``bad_type`` (default False): give the binary-slot entry an UNKNOWN ``type`` so
        the boot-time jq gate fails the boot fail-closed (the locked decision).

    Always seeds ONE ``claude-plugin`` source repo (its own ``file://`` bare repo tagged
    ``v1.0.0``) so ``install_claude_plugin`` does a real, pinned, hermetic clone.
    """
    repos_root = tmp_path / "repos"
    repos_root.mkdir(exist_ok=True)
    call_count = {"n": 0}

    def _build(*, include_binary: bool = True, bad_type: bool = False) -> ManifestConfigRepo:
        call_count["n"] += 1
        suffix = f"-{call_count['n']}" if call_count["n"] > 1 else ""

        # A real claude-plugin source repo, pinned to an immutable tag (SC-2).
        plugin_name = "example-claude-plugin"
        plugin_url = _seed_bare_repo(
            repos_root,
            f"plugin-{plugin_name}{suffix}",
            {"plugin.json": '{"name": "example-claude-plugin"}\n', "README.md": "# plugin\n"},
            tag="v1.0.0",
        )

        plugins: dict[str, dict[str, str]] = {
            plugin_name: {"source": plugin_url, "ref": "v1.0.0", "type": "claude-plugin"},
        }
        skipped_names: list[str] = []
        if include_binary:
            # A baked-at-provision entry: its source is never cloned at boot.
            plugins["rtk"] = {
                "source": "github.com/brave-bear-studios/rtk",
                "ref": "v0.1.0",
                "type": "wat" if bad_type else "binary",
            }
            if not bad_type:
                skipped_names.append("rtk")

        manifest = json.dumps({"schemaVersion": "1.0.0", "plugins": plugins}, indent=2) + "\n"
        config_url = _seed_bare_repo(
            repos_root,
            f"cc-worker-config{suffix}",
            {
                "claude/CLAUDE.md": "# Worker CLAUDE.md (seeded)\n",
                "plugins/manifest.json": manifest,
            },
            tag="v1.0.0",
        )
        project_url = _seed_bare_repo(
            repos_root, f"project{suffix}", {"README.md": "# Project (seeded)\n"}
        )
        return ManifestConfigRepo(
            config_repo=config_url,
            project_repo=project_url,
            claude_plugin_names=[plugin_name],
            skipped_names=skipped_names,
        )

    return _build


@contextmanager
def serve_bootconfig(repo: ManifestConfigRepo) -> Iterator[FakeControlPlane]:
    """Serve the FROZEN bootconfig envelope for a ``ManifestConfigRepo`` on loopback.

    A context manager (not a fixture) so the two-boots-identical test can stand the
    fake control plane up around two sequential boot runs over the SAME config repo.
    """
    payload = {
        "configRepo": repo.config_repo,
        "configBranch": repo.config_branch,
        "projectRepo": repo.project_repo,
        "projectBranch": repo.project_branch,
        "gitCredential": _SENTINEL_CREDENTIAL,
    }
    server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(payload))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = str(server.server_address[0]), int(server.server_address[1])
    try:
        yield FakeControlPlane(
            url=f"http://{host}:{port}",
            config_repo=repo.config_repo,
            config_branch=repo.config_branch,
            project_repo=repo.project_repo,
            project_branch=repo.project_branch,
            git_credential=_SENTINEL_CREDENTIAL,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture
def fake_control_plane(bare_repos: dict[str, str]) -> Iterator[FakeControlPlane]:
    """Serve the FROZEN bootconfig envelope on a loopback ephemeral port (the UP variant)."""
    payload = {
        "configRepo": bare_repos["config_repo"],
        "configBranch": bare_repos["config_branch"],
        "projectRepo": bare_repos["project_repo"],
        "projectBranch": bare_repos["project_branch"],
        "gitCredential": _SENTINEL_CREDENTIAL,
    }
    server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(payload))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = str(server.server_address[0]), int(server.server_address[1])
    try:
        yield FakeControlPlane(
            url=f"http://{host}:{port}",
            config_repo=bare_repos["config_repo"],
            config_branch=bare_repos["config_branch"],
            project_repo=bare_repos["project_repo"],
            project_branch=bare_repos["project_branch"],
            git_credential=_SENTINEL_CREDENTIAL,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture
def down_control_plane() -> Iterator[str]:
    """A loopback server that 503s every request — drives the retry-then-fail test."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(None))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = str(server.server_address[0]), int(server.server_address[1])
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture
def stub_ttyd_path(tmp_path: Path) -> Path:
    """Copy the committed stub ttyd into a temp dir as an executable named ``ttyd``.

    Returned dir is meant to be prepended to the subprocess ``PATH`` so the boot
    script's final ``exec ttyd ...`` resolves to the stub (records argv, exits 0).
    """
    bindir = tmp_path / "stub-bin"
    bindir.mkdir()
    dest = bindir / "ttyd"
    shutil.copyfile(_STUB_TTYD_BIN, dest)
    dest.chmod(0o755)
    return bindir


@pytest.fixture
def boot_script() -> Path:
    """Absolute path to the burrow-boot.sh under test."""
    return _BOOT_SCRIPT


# Re-export the seam helpers the test module reaches for.
SENTINEL_CREDENTIAL = _SENTINEL_CREDENTIAL


def make_boot_env(
    *,
    control_plane: str,
    home: Path,
    etc_burrow: Path,
    stub_bin: Path,
    vmid_hostname: str = "burrow-w-241",
) -> dict[str, str]:
    """Build the hermetic subprocess env for a boot run (see test module for use)."""
    return {
        "PATH": f"{stub_bin}{os.pathsep}{os.environ.get('PATH', '')}",
        "HOME": str(home),
        "CONTROL_PLANE": control_plane,
        "BURROW_ETC": str(etc_burrow),
        "BURROW_HOSTNAME": vmid_hostname,
        "STUB_TTYD_ARGV_FILE": str(home / "ttyd-argv.txt"),
        # Keep git hermetic and non-interactive regardless of the host's config.
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": str(home / ".gitconfig-absent"),
    }


__all__ = [
    "FakeControlPlane",
    "ManifestConfigRepo",
    "SENTINEL_CREDENTIAL",
    "make_boot_env",
    "serve_bootconfig",
]
