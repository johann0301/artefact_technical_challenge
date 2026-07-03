import json
import sqlite3
from pathlib import Path

from emporio.etl import build_database


def test_build_database_loads_all_source_rows(tmp_path: Path) -> None:
    database_path = tmp_path / "emporio.db"

    counts = build_database(database_path)

    assert counts == {
        "categories": 9,
        "products": 65,
        "customers": 50,
        "orders": 20,
        "order_items": 22,
        "promotions": 25,
    }
    connection = sqlite3.connect(database_path)
    try:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        specs_json = connection.execute(
            "SELECT specs_json FROM products WHERE product_id = 95"
        ).fetchone()[0]
        assert json.loads(specs_json)["top"] == "Cedro Sólido"
    finally:
        connection.close()


def test_build_database_is_idempotent(tmp_path: Path) -> None:
    database_path = tmp_path / "emporio.db"
    build_database(database_path)

    build_database(database_path)

    connection = sqlite3.connect(database_path)
    try:
        assert connection.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 65
    finally:
        connection.close()
