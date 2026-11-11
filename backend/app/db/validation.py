"""Parser for SQL files made of named queries (``-- name: some_name``)."""

from __future__ import annotations

import re

_NAME_MARKER = re.compile(r"^--\s*name:\s*(\w+)\s*$", re.MULTILINE)


def parse_named_queries(sql_text: str) -> dict[str, str]:
    """Split a SQL file into {name: statement}. Text before the first marker is ignored."""
    parts = _NAME_MARKER.split(sql_text)
    names, statements = parts[1::2], parts[2::2]
    queries = {
        name: statement.strip().rstrip(";")
        for name, statement in zip(names, statements, strict=True)
    }
    if len(queries) != len(names):
        raise ValueError("Duplicate query names in SQL file")
    return queries
