from __future__ import annotations

from datetime import date
from pydantic import BaseModel, ConfigDict, Field


class FoodLineItem(BaseModel):
    raw_item_name: str
    quantity: float | None = None
    quantity_text: str | None = None
    unit: str | None = None
    unit_price: float | None = None
    line_total: float | None = None


class FoodInvoice(BaseModel):
    model_config = ConfigDict(extra="ignore")

    vendor_name: str | None = None
    invoice_number: str | None = None
    invoice_date: date | None = None
    currency: str | None = None
    line_items: list[FoodLineItem] = Field(default_factory=list)
    subtotal: float | None = None
    tax: float | None = None
    total: float | None = None

