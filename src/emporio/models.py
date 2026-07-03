"""Structured values returned by agent tools."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class ProductSummary(BaseModel):
    product_id: int
    name: str
    category: str
    stock_quantity: int
    original_price_brl: Decimal
    effective_price_brl: Decimal
    discount_percent: int | None = None
    promotion_description: str | None = None


class ProductDetails(ProductSummary):
    description: str
    specs: dict[str, Any]


class NotFound(BaseModel):
    message: str


class AuthError(BaseModel):
    message: str


class OrderItem(BaseModel):
    product_id: int
    product_name: str
    quantity: int = Field(ge=1)


class OrderStatus(BaseModel):
    order_id: int
    order_date: date
    status: str
    total_brl: Decimal
    payment_method: str
    tracking_code: str | None = None
    estimated_delivery: date | None = None
    receipt_date: date | None = None
    receipt_date_is_estimated: bool = False
    notes: str | None = None
    items: list[OrderItem]


class PolicyChunk(BaseModel):
    section: str
    title: str
    content: str
    source: str
    pages: str
    distance: float | None = None
