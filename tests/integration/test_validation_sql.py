"""Runs the independent SQL validation queries: each must return zero violations."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import Engine, text

from backend.app.db.validation import parse_named_queries

pytestmark = pytest.mark.integration

QUERIES = parse_named_queries(
    (Path(__file__).resolve().parents[2] / "database" / "sql" / "validation_queries.sql").read_text(
        "utf-8"
    )
)


def test_validation_file_is_parsed() -> None:
    assert len(QUERIES) >= 15


@pytest.mark.parametrize("name", sorted(QUERIES))
def test_validation_query_returns_no_violations(loaded_engine: Engine, name: str) -> None:
    with loaded_engine.connect() as connection:
        violations = connection.execute(text(QUERIES[name])).fetchall()
    assert violations == [], f"{name}: {len(violations)} violating rows, e.g. {violations[:3]}"


def test_parser_rejects_duplicate_names() -> None:
    with pytest.raises(ValueError, match="Duplicate"):
        parse_named_queries("-- name: a\nSELECT 1;\n-- name: a\nSELECT 2;")
