"""SQLite connection helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path


class DatabaseNotInitializedError(RuntimeError):
    """Raised when a data-backed command runs before setup."""


def connect(database_path: Path) -> sqlite3.Connection:
    """Open the local database with consistent safety settings."""

    if not database_path.exists():
        raise DatabaseNotInitializedError(
            f"Database not found at {database_path}. Run `uv run emporio-setup` first."
        )
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection
