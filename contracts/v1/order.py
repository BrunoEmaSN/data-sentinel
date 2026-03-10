"""
Order contract (Envelope + Payload).

Example of Envelope/Body structure: the Validator can inspect
event_id, version and source before validating the payload.
Documentation on each field for data catalog and OpenAPI.
"""
from typing import List

from pydantic import BaseModel, EmailStr, Field

from contracts.v1.event import EventEnvelope


# --- THE BODY (Payload) ---
# Defined by Data Engineering and Business; integrated business validation.


class OrderItem(BaseModel):
    """Order line item."""

    sku: str = Field(..., description="Unique product code (SKU).")
    quantity: int = Field(..., gt=0, description="Quantity; must be at least 1.")
    price: float = Field(..., ge=0, description="Unit price; non-negative.")

    model_config = {"str_strict": True}


class OrderPayload(BaseModel):
    """Order business payload: data that matters for processing and analytics."""

    order_id: str = Field(..., description="Business identifier of the order.")
    customer_email: EmailStr = Field(..., description="Customer email for notifications and invoice.")
    items: List[OrderItem] = Field(..., description="List of order items.")
    total_amount: float = Field(..., ge=0, description="Order total; must be >= 0.")
    currency: str = Field(
        ...,
        min_length=3,
        max_length=3,
        description="ISO 4217 currency code (e.g. USD, EUR).",
    )

    model_config = {"str_strict": True}


# --- FINAL CONTRACT (Envelope + Payload) ---


class OrderEvent(EventEnvelope):
    """
    Full order event: envelope (metadata) + payload (business data).
    All order ingestion must validate against this contract;
    on failure, the system must tag as UNPROCESSED_DLQ in the Workbench.
    """

    payload: OrderPayload = Field(..., description="Order body validated by the business schema.")

    model_config = {"str_strict": True}
