# Developer entry points. Run `make help` for the list.
SHELL := /bin/bash
PY := .venv/bin/python
NPM := npm --prefix frontend

.DEFAULT_GOAL := help
.PHONY: help setup env db-init db-start db-stop migrate data etl pipeline api web \
        lint typecheck test test-unit test-integration test-web e2e e2e-docker ci validate \
        evaluate api-types screenshots powerbi-data docker-up docker-down

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

lint: ## Ruff (Python) and oxlint (TypeScript)
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

e2e-docker: ## Playwright end-to-end tests against the Docker Compose stack on :8080
	E2E_WEB_URL=http://localhost:8080 E2E_API_URL=http://localhost:8080 $(NPM) run e2e

docker-up: env ## Build and start the whole stack in containers (web on :8080)
	docker compose up --build --detach

docker-down: ## Stop the containers (keeps the data volume)
	docker compose down

validate: ## Run the independent SQL validation queries
	scripts/run_validation_queries.sh

evaluate: ## Score the anomaly detector against the injected scenarios
	$(PY) -m pipelines.evaluation

api-types: ## Regenerate the frontend API types from the OpenAPI schema
	$(PY) scripts/export_openapi.py
	$(NPM) run gen:api

screenshots: ## Capture the documentation screenshots from the running app
	$(NPM) run screenshots

powerbi-data: ## Export the star schema and expected values for Power BI
	$(PY) scripts/export_powerbi_assets.py

ci: ## Run the same checks as the CI workflow, locally
	scripts/ci_local.sh
