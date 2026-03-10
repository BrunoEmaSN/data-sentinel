"""
Test scenarios as described in the plan:
1. Happy path: valid JSON -> validated_data -> Loader
2. Schema drift: renamed field -> validation_error -> Healing Agent -> schema_fixed
3. Data corruption: garbage -> validation_error -> DLQ
"""
import uuid
from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from contracts.v1.order import OrderEvent
from contracts.v1.transaction import TransactionSchema


def test_scenario_happy_path_contract():
    """Happy path at contract level: valid JSON parses correctly."""
    payload = {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "source": "stripe",
        "amount": "100.50",
        "currency": "USD",
        "user_id": str(uuid.uuid4()),
        "email": "user@example.com",
        "description": "Payment",
    }
    t = TransactionSchema.model_validate(payload)
    assert t.amount == Decimal("100.50")
    assert t.currency == "USD"
    assert t.email == "user@example.com"


def test_scenario_schema_drift_detected():
    """Schema drift: 'email' -> 'user_email' (or 'price' -> 'amount') must fail validation."""
    payload = {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "source": "shopify",
        "amount": "50.00",
        "currency": "EUR",
        "user_id": str(uuid.uuid4()),
        "user_email": "user@shopify.com",  # drift: should be 'email'
    }
    with pytest.raises(ValidationError) as exc_info:
        TransactionSchema.model_validate(payload)
    errors = exc_info.value.errors()
    assert any("email" in str(e.get("loc", [])) or "Missing" in str(e.get("msg", "")) for e in errors)


def test_scenario_schema_drift_price_instead_of_amount():
    """Classic schema drift: 'price' instead of 'amount'."""
    payload = {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "source": "api",
        "price": "25.00",
        "currency": "GBP",
        "user_id": str(uuid.uuid4()),
        "email": "a@b.co",
    }
    with pytest.raises(ValidationError):
        TransactionSchema.model_validate(payload)


def test_scenario_data_corruption_rejected():
    """Data corruption: string where number is expected -> validation fails."""
    payload = {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "source": "broken",
        "amount": "basura",
        "currency": "USD",
        "user_id": str(uuid.uuid4()),
        "email": "x@y.com",
    }
    with pytest.raises(ValidationError) as exc_info:
        TransactionSchema.model_validate(payload)
    errors = exc_info.value.errors()
    assert any("amount" in str(e.get("loc", [])) for e in errors)


def test_scenario_data_corruption_invalid_uuid():
    """Data corruption: user_id is not a UUID."""
    payload = {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "source": "x",
        "amount": "1.00",
        "currency": "USD",
        "user_id": "not-a-uuid",
        "email": "a@b.com",
    }
    with pytest.raises(ValidationError):
        TransactionSchema.model_validate(payload)


# --- Data Sentinel: OrderEvent contract breach ---


def test_sentinel_order_event_contract_rupture_invalid_email():
    """
    Data Sentinel simulation: malformed data (invalid email) is rejected
    and the error is captured in detail for repair/DLQ.
    """
    bad_data = {
        "event_id": "550e8400-e29b-41d4-a716-446655440000",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "source": "ecommerce_api",
        "payload": {
            "order_id": "ORD-123",
            "customer_email": "esto-no-es-un-email",
            "items": [{"sku": "PROD-1", "quantity": 1, "price": 10.5}],
            "total_amount": 10.5,
            "currency": "USD",
        },
    }
    with pytest.raises(ValidationError) as exc_info:
        OrderEvent.model_validate(bad_data)
    errors = exc_info.value.errors()
    assert any("customer_email" in str(e.get("loc", [])) for e in errors)


def test_sentinel_order_event_valid_passes():
    """Contrast: valid data passes the validation_gateway (OrderEvent)."""
    good_data = {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "source": "ecommerce_api",
        "payload": {
            "order_id": "ORD-456",
            "customer_email": "customer@example.com",
            "items": [{"sku": "PROD-2", "quantity": 2, "price": 25.0}],
            "total_amount": 50.0,
            "currency": "EUR",
        },
    }
    event = OrderEvent.model_validate(good_data)
    assert event.payload.order_id == "ORD-456"
    assert str(event.payload.customer_email) == "customer@example.com"
