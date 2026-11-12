#!/usr/bin/env bash
# Runs locally the checks defined in .github/workflows/ci.yml.
#
#   scripts/ci_local.sh            everything, including end-to-end tests
#   SKIP_E2E=1 scripts/ci_local.sh skip the browser tests
#
# Needs the project-local PostgreSQL (`make db-init`) and installed dependencies (`make setup`).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
NPM=(npm --prefix frontend)

step() { printf '\n\033[1m== %s\033[0m\n' "$1"; }

step "Database"
scripts/dev_db.sh start

step "Python: lint and format"
"$PY" -m ruff check .
"$PY" -m ruff format --check .

step "Python: type check"
"$PY" -m mypy

step "Warehouse: generate, migrate, load"
"$PY" -m pipelines.generate
"$PY" -m alembic upgrade head
"$PY" -m pipelines.etl

step "Python: tests with coverage"
"$PY" -m pytest --cov -q

step "Independent SQL validation"
scripts/run_validation_queries.sh

step "Web: lint, types, tests, build"
"${NPM[@]}" run lint
"${NPM[@]}" run typecheck
"${NPM[@]}" run test
"${NPM[@]}" run build

if [[ "${SKIP_E2E:-0}" == "1" ]]; then
  step "End-to-end tests skipped (SKIP_E2E=1)"
else
  step "End-to-end tests"
  "${NPM[@]}" run e2e
fi

printf '\n\033[1mAll checks passed.\033[0m\n'
