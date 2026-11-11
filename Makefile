# Developer entry points. Run `make help` for the list.
SHELL := /bin/bash
PY := .venv/bin/python
NPM := npm --prefix frontend

.DEFAULT_GOAL := help
.PHONY: help setup env db-init db-start db-stop migrate data etl pipeline api web \
        lint typecheck test test-unit test-integration test-web e2e ci docs-kpi powerbi-data

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

env: ## Create .env from .env.example if missing
	@test -f .env || (cp .env.example .env && echo "Created .env — review the values.")

setup: env ## Install Python and Node dependencies
	test -d .venv || python3.12 -m venv .venv
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -e ".[dev]"
	$(NPM) install

db-init: env ## Initialise and start the project-local PostgreSQL cluster
	scripts/dev_db.sh init

db-start: ## Start the local PostgreSQL cluster
	scripts/dev_db.sh start

db-stop: ## Stop the local PostgreSQL cluster
	scripts/dev_db.sh stop

migrate: ## Apply Alembic migrations
	$(PY) -m alembic upgrade head

data: ## Generate the synthetic source extracts (fixed seed)
	$(PY) -m pipelines.generate

etl: ## Validate, transform and load the extracts into PostgreSQL
	$(PY) -m pipelines.etl

pipeline: data migrate etl ## Generate data, migrate the schema and run the ETL

api: ## Run the FastAPI server with reload
	$(PY) -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000

web: ## Run the Vite dev server
	$(NPM) run dev

lint: ## Ruff (Python) and ESLint (TypeScript)
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .
	$(NPM) run lint

typecheck: ## mypy (Python) and tsc (TypeScript)
	$(PY) -m mypy
	$(NPM) run typecheck

test-unit: ## Python tests that do not need a database
	$(PY) -m pytest -m "not integration"

test-integration: ## Python tests against PostgreSQL
	$(PY) -m pytest -m integration

test: ## Full Python test suite with coverage
	$(PY) -m pytest --cov

test-web: ## Frontend unit and component tests
	$(NPM) run test

e2e: ## Playwright end-to-end tests (starts API and web servers)
	$(NPM) run e2e

docs-kpi: ## Regenerate docs/KPI_CATALOG.md from the code catalog
	$(PY) scripts/export_kpi_catalog.py

powerbi-data: ## Export the star schema and expected values for Power BI
	$(PY) scripts/export_powerbi_assets.py

ci: ## Run the same checks as the CI workflow, locally
	scripts/ci_local.sh
