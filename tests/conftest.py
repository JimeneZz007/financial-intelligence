"""Fixtures shared by the whole Python test suite.

Integration tests use a dedicated PostgreSQL database (POSTGRES_TEST_DB). It is migrated
with Alembic and loaded by the real ETL pipeline once per session, so those tests exercise
the same path as production data.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text
from sqlalchemy.exc import OperationalError

from backend.app.core.config import get_settings
from backend.app.db.session import build_engine
from pipelines.etl.runner import RunSummary, run_pipeline
from pipelines.generate.dataset import Dataset, build_dataset, write_dataset

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def dataset() -> Dataset:
    """The synthetic dataset built in memory with the project seed."""
    return build_dataset()


@pytest.fixture(scope="session")
def source_dir(dataset: Dataset, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Raw extracts written to a temporary directory."""
    directory = tmp_path_factory.mktemp("synthetic")
    write_dataset(dataset, directory)
    return directory


@pytest.fixture(scope="session")
def test_engine() -> Iterator[Engine]:
    """Engine bound to the test database, with the schema migrated to head."""
    settings = get_settings()
    url = settings.database_url(settings.postgres_test_db)
    engine = build_engine(url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError as error:  # pragma: no cover - depends on the environment
        pytest.fail(
            f"Integration tests need PostgreSQL ({settings.postgres_test_db}). "
            f"Run `make db-init`. Original error: {error.orig}"
        )

    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option(
        "sqlalchemy.url", url.render_as_string(hide_password=False).replace("%", "%%")
    )
    config.attributes["configure_logging"] = False
    command.upgrade(config, "head")
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def pipeline_run(test_engine: Engine, source_dir: Path) -> RunSummary:
    """The ETL executed once against the test database."""
    summary = run_pipeline(test_engine, source_dir)
    assert summary.succeeded, summary.error_message
    return summary


@pytest.fixture(scope="session")
def loaded_engine(test_engine: Engine, pipeline_run: RunSummary) -> Engine:
    """Engine whose database holds the full synthetic dataset."""
    return test_engine
