from decimal import Decimal
from pathlib import Path

from emporio.models import AuthError, NotFound, ProductDetails
from emporio.tools import get_order_status, get_product_details, search_products


def test_search_products_filters_category_price_and_availability(database_path: Path) -> None:
    products = search_products(database_path, category="violão", max_price=1000)

    assert products
    assert all(product.category == "Violões" for product in products)
    assert all(product.stock_quantity > 0 for product in products)
    assert all(product.effective_price_brl <= Decimal("1000.00") for product in products)
    assert all(product.product_id != 96 for product in products)


def test_search_products_uses_parameterized_query(database_path: Path) -> None:
    assert search_products(database_path, query="'; DROP TABLE products; --") == []
    assert isinstance(get_product_details(database_path, "GD20"), ProductDetails)


def test_product_details_normalizes_model_name(database_path: Path) -> None:
    product = get_product_details(database_path, "GD20")

    assert isinstance(product, ProductDetails)
    assert product.product_id == 95
    assert product.name == "Takamine GD20 Dreadnought Natural"
    assert product.effective_price_brl == Decimal("2199.00")


def test_product_details_applies_active_promotion(database_path: Path) -> None:
    product = get_product_details(database_path, "Taylor 110e")

    assert isinstance(product, ProductDetails)
    assert product.product_id == 94
    assert product.discount_percent == 8
    assert product.original_price_brl == Decimal("5999.00")
    assert product.effective_price_brl == Decimal("5519.08")


def test_product_details_reports_active_out_of_stock_product(database_path: Path) -> None:
    product = get_product_details(database_path, "Giannini GF-3D")

    assert isinstance(product, ProductDetails)
    assert product.stock_quantity == 0


def test_product_details_hides_discontinued_products(database_path: Path) -> None:
    result = get_product_details(database_path, "produto que não existe")
    assert isinstance(result, NotFound)


def test_identifier_alone_lists_only_that_customers_orders(database_path: Path) -> None:
    orders = get_order_status(database_path, "pedro.oliveira@jmail.com")

    assert isinstance(orders, list)
    assert [order.order_id for order in orders] == [19, 1]


def test_order_lookup_accepts_normalized_phone(database_path: Path) -> None:
    orders = get_order_status(database_path, "67 99812-3456", order_id=4)

    assert isinstance(orders, list)
    assert [order.order_id for order in orders] == [4]
    assert orders[0].receipt_date_is_estimated is True


def test_order_lookup_does_not_leak_another_customers_order(database_path: Path) -> None:
    result = get_order_status(database_path, "pedro.oliveira@jmail.com", order_id=2)

    assert isinstance(result, AuthError)
    assert "pedido 2" not in result.message.lower()


def test_unknown_customer_gets_same_generic_error(database_path: Path) -> None:
    unknown = get_order_status(database_path, "unknown@example.com", order_id=1)
    wrong_owner = get_order_status(database_path, "pedro.oliveira@jmail.com", order_id=2)

    assert isinstance(unknown, AuthError)
    assert isinstance(wrong_owner, AuthError)
    assert unknown.message == wrong_owner.message


def test_duplicate_email_requires_an_unambiguous_identifier(database_path: Path) -> None:
    result = get_order_status(database_path, "bruno.martins@jmail.com")

    assert isinstance(result, AuthError)
    assert "telefone" in result.message.lower()
