"""Fixtures shared by the whole Python test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from pipelines.generate.dataset import Dataset, build_dataset

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def dataset() -> Dataset:
    """The synthetic dataset built in memory with the project seed."""
    return build_dataset()
