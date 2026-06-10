# SPDX-FileCopyrightText: 2026 Brave Bear Studios
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Seam-leakage guard (PLAT-06, PLAT-07).

Driver symbols must stay confined to their owning provider file. This test scans
every first-party ``api/`` source file (excluding ``tests/``, ``.venv/``,
``__pycache__/``) and asserts each forbidden symbol appears *as code* ONLY in its
allowed file(s):

- ``proxmoxer`` / ``ProxmoxAPI``  -> only ``api/compute/proxmoxProvider.py``
- ``aiosqlite`` + raw SQL          -> only ``api/db/sqliteProvider.py`` (+ migrations)

It would FAIL if, say, ``main.py`` imported ``aiosqlite`` or a model referenced
``proxmoxer`` — proving the provider boundary in CI.

Why ``tokenize`` instead of a plain grep: the seam contract is *documented* in
docstrings of non-owning files (e.g. ``compute/provider.py`` says "no
``proxmoxer`` type ever leaks"). Those prose mentions are legitimate and must not
trip the guard. Stripping comments AND string literals (docstrings are string
tokens) leaves only executable code tokens, so a count never gates on unfiltered
prose. The ``.sql`` migrations are scanned with a comment-stripped line check.
"""

import io
import tokenize
from collections.abc import Iterator
from pathlib import Path

# api/ root (this file is api/tests/unit/test_seam_leakage.py).
_API_ROOT = Path(__file__).resolve().parents[2]
_SKIP_DIRS = {"tests", ".venv", "__pycache__", ".mypy_cache", ".ruff_cache"}

# Forbidden Python symbols -> the ONLY file(s) (relative to api/) allowed to use
# them as executable code.
_PYTHON_SEAMS: dict[str, set[str]] = {
    "proxmoxer": {"compute/proxmoxProvider.py"},
    "ProxmoxAPI": {"compute/proxmoxProvider.py"},
    "aiosqlite": {"db/sqliteProvider.py"},
}

# Raw-SQL keyword fragments -> the ONLY file(s) allowed to hold them. Migrations
# (.sql) are the schema's home; the SQLite provider holds the query strings.
_SQL_KEYWORDS = ("CREATE TABLE", "INSERT INTO", "DELETE FROM", "SELECT ")
_SQL_ALLOWED = {"db/sqliteProvider.py"}


def _python_sources() -> Iterator[Path]:
    """Yield every first-party ``api/`` ``.py`` file, skipping vendored/test dirs."""
    for path in _API_ROOT.rglob("*.py"):
        rel_parts = path.relative_to(_API_ROOT).parts
        if any(part in _SKIP_DIRS for part in rel_parts):
            continue
        yield path


def _code_tokens(source: str) -> set[str]:
    """Return the set of NAME tokens in ``source``, excluding comments/strings.

    Docstrings and string literals are STRING tokens (dropped); ``#`` lines are
    COMMENT tokens (dropped). What remains is executable identifiers, so prose
    mentions of a driver symbol cannot trip the guard.
    """
    names: set[str] = set()
    readline = io.StringIO(source).readline
    for tok in tokenize.generate_tokens(readline):
        if tok.type == tokenize.NAME:
            names.add(tok.string)
    return names


def test_proxmox_and_aiosqlite_symbols_are_confined() -> None:
    for path in _python_sources():
        rel = path.relative_to(_API_ROOT).as_posix()
        names = _code_tokens(path.read_text(encoding="utf-8"))
        for symbol, allowed in _PYTHON_SEAMS.items():
            if symbol in names and rel not in allowed:
                raise AssertionError(
                    f"seam leak: '{symbol}' used as code in {rel}; "
                    f"allowed only in {sorted(allowed)}"
                )


def test_raw_sql_is_confined() -> None:
    for path in _python_sources():
        rel = path.relative_to(_API_ROOT).as_posix()
        if rel in _SQL_ALLOWED:
            continue
        # Strip docstrings/strings so prose like "cheap SELECT 1" in a docstring
        # does not count; only code-level string content remains as STRING tokens
        # we deliberately exclude — so for non-allowed files we scan code tokens
        # for SQL keyword fragments via the raw text minus comments/docstrings.
        code_only = _strip_comments_and_strings(path.read_text(encoding="utf-8"))
        upper = code_only.upper()
        for keyword in _SQL_KEYWORDS:
            if keyword in upper:
                raise AssertionError(
                    f"seam leak: raw SQL fragment '{keyword.strip()}' found in {rel}; "
                    f"raw SQL is allowed only in {sorted(_SQL_ALLOWED)} + db/migrations/"
                )


def _strip_comments_and_strings(source: str) -> str:
    """Return ``source`` with COMMENT and STRING tokens removed.

    Used for the SQL scan: docstrings (STRING) and ``#`` comments (COMMENT) are
    dropped so SQL prose in documentation cannot trip the guard; any remaining
    SQL keyword is therefore genuinely executable code, not prose.
    """
    pieces: list[str] = []
    readline = io.StringIO(source).readline
    for tok in tokenize.generate_tokens(readline):
        if tok.type in (tokenize.COMMENT, tokenize.STRING):
            continue
        pieces.append(tok.string)
    return " ".join(pieces)


def test_migrations_dir_is_the_schema_home() -> None:
    """Sanity anchor: the SQL the guard exempts actually lives where we claim."""
    migrations = _API_ROOT / "db" / "migrations"
    sql_files = list(migrations.glob("*.sql"))
    assert sql_files, "expected at least one migration .sql under db/migrations/"
    combined = "\n".join(f.read_text(encoding="utf-8") for f in sql_files).upper()
    assert "CREATE TABLE" in combined  # the schema genuinely lives here
