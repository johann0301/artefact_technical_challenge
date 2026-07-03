"""Idempotent CSV-to-SQLite ingestion for the supplied challenge data."""

from __future__ import annotations

import csv
import json
import sqlite3
from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from emporio.config import DATA_DIR
from emporio.normalization import (
    normalize_compact,
    normalize_email,
    normalize_phone,
    normalize_search,
)

FILE_PREFIX = "desafio_tecnico_ai_eng - "
CSV_PATHS = {
    name: DATA_DIR / f"{FILE_PREFIX}{name}.csv"
    for name in ("categories", "products", "customers", "orders", "order_items", "promotions")
}

SCHEMA = """
CREATE TABLE categories (
    category_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    name_normalized TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL
);

CREATE TABLE products (
    product_id INTEGER PRIMARY KEY,
    price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
    name TEXT NOT NULL,
    name_normalized TEXT NOT NULL,
    name_compact TEXT NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(category_id),
    description TEXT NOT NULL,
    description_normalized TEXT NOT NULL,
    stock_quantity INTEGER NOT NULL CHECK (stock_quantity >= 0),
    status TEXT NOT NULL,
    specs_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    phone_normalized TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL,
    email_normalized TEXT NOT NULL,
    city TEXT NOT NULL
);

CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    order_date TEXT NOT NULL,
    status TEXT NOT NULL,
    total_cents INTEGER NOT NULL CHECK (total_cents >= 0),
    payment_method TEXT NOT NULL,
    tracking_code TEXT,
    estimated_delivery TEXT,
    notes TEXT
);

CREATE TABLE order_items (
    order_id INTEGER NOT NULL REFERENCES orders(order_id),
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    PRIMARY KEY (order_id, product_id)
);

CREATE TABLE promotions (
    promotion_id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    discount_percent INTEGER NOT NULL CHECK (discount_percent BETWEEN 0 AND 100),
    description TEXT NOT NULL,
    is_active INTEGER NOT NULL CHECK (is_active IN (0, 1))
);

CREATE INDEX idx_products_catalog
    ON products(status, stock_quantity, category_id, price_cents);
CREATE INDEX idx_products_name ON products(name_compact);
CREATE INDEX idx_customers_email ON customers(email_normalized);
CREATE INDEX idx_orders_customer ON orders(customer_id, order_date DESC);
CREATE INDEX idx_promotions_product_active ON promotions(product_id, is_active);
"""


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Required source file not found: {path}")
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _money_to_cents(value: str) -> int:
    amount = Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(amount * 100)


def _none_if_blank(value: str) -> str | None:
    stripped = value.strip()
    return stripped or None


def _insert_many(
    connection: sqlite3.Connection,
    statement: str,
    values: Iterable[tuple[object, ...]],
) -> None:
    connection.executemany(statement, values)


def build_database(database_path: Path) -> dict[str, int]:
    """Rebuild the SQLite database atomically and return source row counts."""

    rows = {name: _read_csv(path) for name, path in CSV_PATHS.items()}
    temporary_path = database_path.with_name(f"{database_path.name}.tmp")
    temporary_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path.unlink(missing_ok=True)

    connection = sqlite3.connect(temporary_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA)
        with connection:
            _insert_many(
                connection,
                "INSERT INTO categories VALUES (?, ?, ?, ?)",
                (
                    (
                        int(row["category_id"]),
                        row["name"],
                        normalize_search(row["name"]),
                        row["description"],
                    )
                    for row in rows["categories"]
                ),
            )
            _insert_many(
                connection,
                "INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    (
                        int(row["product_id"]),
                        _money_to_cents(row["price_brl"]),
                        row["name"],
                        normalize_search(row["name"]),
                        normalize_compact(row["name"]),
                        int(row["category_id"]),
                        row["description"],
                        normalize_search(row["description"]),
                        int(row["stock_quantity"]),
                        row["status"],
                        json.dumps(
                            json.loads(row["specs"]),
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        row["created_at"],
                    )
                    for row in rows["products"]
                ),
            )
            _insert_many(
                connection,
                "INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    (
                        int(row["customer_id"]),
                        row["name"],
                        row["phone"],
                        normalize_phone(row["phone"]),
                        row["email"],
                        normalize_email(row["email"]),
                        row["city"],
                    )
                    for row in rows["customers"]
                ),
            )
            _insert_many(
                connection,
                "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    (
                        int(row["order_id"]),
                        int(row["customer_id"]),
                        row["order_date"],
                        row["status"],
                        _money_to_cents(row["total_brl"]),
                        row["payment_method"],
                        _none_if_blank(row["tracking_code"]),
                        _none_if_blank(row["estimated_delivery"]),
                        _none_if_blank(row["notes"]),
                    )
                    for row in rows["orders"]
                ),
            )
            _insert_many(
                connection,
                "INSERT INTO order_items VALUES (?, ?, ?)",
                (
                    (int(row["order_id"]), int(row["product_id"]), int(row["quantity"]))
                    for row in rows["order_items"]
                ),
            )
            _insert_many(
                connection,
                "INSERT INTO promotions VALUES (?, ?, ?, ?, ?)",
                (
                    (
                        int(row["promotion_id"]),
                        int(row["product_id"]),
                        int(Decimal(row["discount_percent"])),
                        row["description"],
                        int(row["is_active"]),
                    )
                    for row in rows["promotions"]
                ),
            )

        foreign_key_violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_violations:
            raise ValueError(f"Foreign-key violations found: {foreign_key_violations}")

        duplicate_active_promotions = connection.execute(
            """
            SELECT product_id, COUNT(*) AS promotion_count
            FROM promotions
            WHERE is_active = 1
            GROUP BY product_id
            HAVING COUNT(*) > 1
            """
        ).fetchall()
        if duplicate_active_promotions:
            raise ValueError(
                f"Products with multiple active promotions: {duplicate_active_promotions}"
            )
    except Exception:
        connection.close()
        temporary_path.unlink(missing_ok=True)
        raise
    else:
        connection.close()
        temporary_path.replace(database_path)

    return {name: len(table_rows) for name, table_rows in rows.items()}
