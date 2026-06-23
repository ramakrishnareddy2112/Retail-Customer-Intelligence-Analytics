"""Execute named analytical SQL statements and preserve their outputs."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pandas as pd


QUERY_MARKER = re.compile(r"^-- name: ([a-z][a-z0-9_]*)\s*$", re.MULTILINE)


def parse_named_queries(path: Path) -> list[tuple[str, str]]:
    """Parse one SQL statement following each `-- name:` marker."""
    text = path.read_text(encoding="utf-8")
    matches = list(QUERY_MARKER.finditer(text))
    queries: list[tuple[str, str]] = []

    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        statement = text[start:end].strip()
        if not statement:
            raise ValueError(f"Named SQL query '{match.group(1)}' is empty in {path}.")
        queries.append((match.group(1), statement))

    if not queries:
        raise ValueError(f"No `-- name:` query markers found in {path}.")
    return queries


def execute_named_queries(
    database_path: Path, sql_paths: list[Path]
) -> dict[str, pd.DataFrame]:
    """Execute named read-only queries against SQLite."""
    outputs: dict[str, pd.DataFrame] = {}
    uri = f"file:{database_path.as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        for sql_path in sql_paths:
            for name, statement in parse_named_queries(sql_path):
                if name in outputs:
                    raise ValueError(f"Duplicate named SQL query: {name}")
                outputs[name] = pd.read_sql_query(statement, connection)
    return outputs

