"""Deterministic, parameterized tools exposed to the support agent."""

from __future__ import annotations

import json
from contextlib import closing
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from emporio.db import connect
from emporio.models import (
    AuthError,
    NotFound,
    OrderItem,
    OrderStatus,
    ProductDetails,
    ProductSummary,
)
from emporio.normalization import (
    normalize_compact,
    normalize_email,
    normalize_phone,
    normalize_search,
)

EFFECTIVE_PRICE_SQL = """
CASE
    WHEN promo.is_active = 1
    THEN CAST(ROUND(p.price_cents * (100 - promo.discount_percent) / 100.0) AS INTEGER)
    ELSE p.price_cents
END
"""

CATEGORY_ALIASES = {
    "guitarra": "guitarras",
    "baixo": "baixos",
    "bateria": "baterias",
    "teclado": "teclados",
    "violao": "violoes",
    "ukulele": "ukuleles",
}

ORDER_STATUS_LABELS = {
    "pending": "pendente",
    "confirmed": "confirmado",
    "processing": "em processamento",
    "shipped": "enviado",
    "delivered": "entregue",
    "cancelled": "cancelado",
}

PAYMENT_LABELS = {
    "pix": "PIX",
    "debit": "cartão de débito",
    "boleto": "boleto bancário",
}

GENERIC_ORDER_ERROR = (
    "Não foi possível localizar esse pedido para o telefone ou e-mail informado. "
    "Confira os dados ou tente o telefone cadastrado."
)


def _cents_to_brl(value: int) -> Decimal:
    return (Decimal(value) / 100).quantize(Decimal("0.01"))


def _brl_to_cents(value: float) -> int:
    return int((Decimal(str(value)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _product_from_row(row: object, *, details: bool = False) -> ProductSummary | ProductDetails:
    data = dict(row)  # type: ignore[arg-type]
    common = {
        "product_id": data["product_id"],
        "name": data["name"],
        "category": data["category"],
        "stock_quantity": data["stock_quantity"],
        "original_price_brl": _cents_to_brl(data["price_cents"]),
        "effective_price_brl": _cents_to_brl(data["effective_price_cents"]),
        "discount_percent": data["discount_percent"],
        "promotion_description": data["promotion_description"],
    }
    if details:
        return ProductDetails(
            **common,
            description=data["description"],
            specs=json.loads(data["specs_json"]),
        )
    return ProductSummary(**common)


def search_products(
    database_path: Path,
    query: str | None = None,
    category: str | None = None,
    max_price: float | None = None,
    min_price: float | None = None,
) -> list[ProductSummary]:
    """Search available products using explicit filters and effective promotional prices."""

    conditions = ["p.status = 'active'", "p.stock_quantity > 0"]
    parameters: list[object] = []

    if query and normalize_search(query):
        for token in normalize_search(query).split():
            conditions.append("(p.name_normalized LIKE ? OR p.description_normalized LIKE ?)")
            pattern = f"%{token}%"
            parameters.extend((pattern, pattern))

    if category and normalize_search(category):
        normalized_category = normalize_search(category)
        normalized_category = CATEGORY_ALIASES.get(normalized_category, normalized_category)
        conditions.append("c.name_normalized = ?")
        parameters.append(normalized_category)

    if max_price is not None:
        conditions.append(f"{EFFECTIVE_PRICE_SQL} <= ?")
        parameters.append(_brl_to_cents(max_price))
    if min_price is not None:
        conditions.append(f"{EFFECTIVE_PRICE_SQL} >= ?")
        parameters.append(_brl_to_cents(min_price))

    statement = f"""
        SELECT
            p.product_id,
            p.name,
            c.name AS category,
            p.stock_quantity,
            p.price_cents,
            {EFFECTIVE_PRICE_SQL} AS effective_price_cents,
            promo.discount_percent,
            promo.description AS promotion_description
        FROM products AS p
        JOIN categories AS c ON c.category_id = p.category_id
        LEFT JOIN promotions AS promo
            ON promo.product_id = p.product_id AND promo.is_active = 1
        WHERE {" AND ".join(conditions)}
        ORDER BY effective_price_cents, p.name
    """

    with closing(connect(database_path)) as connection:
        rows = connection.execute(statement, parameters).fetchall()
    return [_product_from_row(row) for row in rows]  # type: ignore[misc]


def get_product_details(database_path: Path, product_name: str) -> ProductDetails | NotFound:
    """Return one catalog product, accepting compact names such as `GD20`."""

    normalized_name = normalize_compact(product_name)
    if not normalized_name:
        return NotFound(message="Informe o nome ou modelo do instrumento.")

    statement = f"""
        SELECT
            p.product_id,
            p.name,
            c.name AS category,
            p.stock_quantity,
            p.price_cents,
            {EFFECTIVE_PRICE_SQL} AS effective_price_cents,
            promo.discount_percent,
            promo.description AS promotion_description,
            p.description,
            p.specs_json
        FROM products AS p
        JOIN categories AS c ON c.category_id = p.category_id
        LEFT JOIN promotions AS promo
            ON promo.product_id = p.product_id AND promo.is_active = 1
        WHERE p.status = 'active' AND p.name_compact LIKE ?
        ORDER BY
            CASE WHEN p.name_compact = ? THEN 0 ELSE 1 END,
            LENGTH(p.name_compact)
        LIMIT 1
    """
    pattern = f"%{normalized_name}%"
    with closing(connect(database_path)) as connection:
        row = connection.execute(statement, (pattern, normalized_name)).fetchone()
    if row is None:
        return NotFound(message=f"Não encontrei um instrumento ativo para “{product_name}”.")
    return _product_from_row(row, details=True)  # type: ignore[return-value]


def _payment_label(value: str) -> str:
    if value.startswith("credit_"):
        installments = value.removeprefix("credit_").removesuffix("x")
        return f"cartão de crédito em {installments}x"
    return PAYMENT_LABELS.get(value, value.replace("_", " "))


def _order_from_row(connection: object, row: object, today: date) -> OrderStatus:
    order = dict(row)  # type: ignore[arg-type]
    item_rows = connection.execute(  # type: ignore[attr-defined]
        """
        SELECT oi.product_id, p.name AS product_name, oi.quantity
        FROM order_items AS oi
        JOIN products AS p ON p.product_id = oi.product_id
        WHERE oi.order_id = ?
        ORDER BY p.name
        """,
        (order["order_id"],),
    ).fetchall()
    estimated_delivery = (
        date.fromisoformat(order["estimated_delivery"]) if order["estimated_delivery"] else None
    )
    delivered = order["status"] == "delivered"
    receipt_date = estimated_delivery if delivered else None
    return OrderStatus(
        order_id=order["order_id"],
        order_date=date.fromisoformat(order["order_date"]),
        status=ORDER_STATUS_LABELS.get(order["status"], order["status"]),
        total_brl=_cents_to_brl(order["total_cents"]),
        payment_method=_payment_label(order["payment_method"]),
        tracking_code=order["tracking_code"],
        estimated_delivery=estimated_delivery,
        receipt_date=receipt_date,
        receipt_date_is_estimated=delivered and estimated_delivery is not None,
        # Computed in code so the model never does date arithmetic (it miscounts).
        days_since_receipt=(today - receipt_date).days if receipt_date else None,
        notes=order["notes"],
        items=[OrderItem(**dict(item)) for item in item_rows],
    )


def get_order_status(
    database_path: Path,
    customer_phone_or_email: str,
    order_id: int | None = None,
    today: date | None = None,
) -> list[OrderStatus] | AuthError:
    """Return only orders owned by the customer identified by phone or e-mail."""

    today = today or date.today()
    raw_identifier = customer_phone_or_email.strip()
    if "@" in raw_identifier:
        column = "email_normalized"
        identifier = normalize_email(raw_identifier)
    else:
        column = "phone_normalized"
        identifier = normalize_phone(raw_identifier)
        if len(identifier) < 10:
            return AuthError(message=GENERIC_ORDER_ERROR)

    with closing(connect(database_path)) as connection:
        customers = connection.execute(
            f"SELECT customer_id FROM customers WHERE {column} = ?",  # noqa: S608
            (identifier,),
        ).fetchall()
        if len(customers) != 1:
            return AuthError(message=GENERIC_ORDER_ERROR)

        parameters: list[object] = [customers[0]["customer_id"]]
        order_filter = ""
        if order_id is not None:
            order_filter = "AND order_id = ?"
            parameters.append(order_id)
        rows = connection.execute(
            f"""
            SELECT *
            FROM orders
            WHERE customer_id = ? {order_filter}
            ORDER BY order_date DESC, order_id DESC
            """,  # noqa: S608
            parameters,
        ).fetchall()
        if order_id is not None and not rows:
            return AuthError(message=GENERIC_ORDER_ERROR)
        return [_order_from_row(connection, row, today) for row in rows]
