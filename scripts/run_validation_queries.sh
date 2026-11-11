#!/usr/bin/env bash
# Runs every query in database/sql/validation_queries.sql against the development
# database. Each query lists rule violations, so the expected output is "0 rows" for all.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$ROOT/.venv/bin/python" - "$ROOT/database/sql/validation_queries.sql" <<'PY'
import sys
from pathlib import Path

from sqlalchemy import text

from backend.app.db.session import build_engine
from backend.app.db.validation import parse_named_queries

queries = parse_named_queries(Path(sys.argv[1]).read_text("utf-8"))
failed = 0
with build_engine().connect() as connection:
    for name, sql in queries.items():
        violations = len(connection.execute(text(sql)).fetchall())
        failed += violations > 0
        print(f"{'OK  ' if violations == 0 else 'FAIL'}  {name}  ({violations} rows)")
print(f"\n{len(queries) - failed}/{len(queries)} validation queries returned zero violations.")
sys.exit(1 if failed else 0)
PY
