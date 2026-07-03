from collections.abc import Iterator
from pathlib import Path

import pytest

from emporio.etl import build_database


@pytest.fixture(scope="session")
def database_path(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    path = tmp_path_factory.mktemp("database") / "emporio.db"
    build_database(path)
    yield path
