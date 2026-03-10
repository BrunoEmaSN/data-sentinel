"""
Escenarios de prueba descritos en el plan:
1. Happy path: JSON perfecto -> validated_data -> Loader
2. Schema drift: campo renombrado -> validation_error -> Healing Agent -> schema_fixed
3. Data corruption: basura -> validation_error -> DLQ
"""
import uuid
from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from contracts.v1.transaction import TransactionSchema


def test_scenario_happy_path_contract():
    """Happy path a nivel de contrato: JSON válido se parsea correctamente."""
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
    """Schema drift: 'email' -> 'user_email' (o 'price' -> 'amount') debe fallar validación."""
    payload = {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "source": "shopify",
        "amount": "50.00",
        "currency": "EUR",
        "user_id": str(uuid.uuid4()),
        "user_email": "user@shopify.com",  # drift: debería ser 'email'
    }
    with pytest.raises(ValidationError) as exc_info:
        TransactionSchema.model_validate(payload)
    errors = exc_info.value.errors()
    assert any("email" in str(e.get("loc", [])) or "Missing" in str(e.get("msg", "")) for e in errors)


def test_scenario_schema_drift_price_instead_of_amount():
    """Schema drift clásico: 'price' en lugar de 'amount'."""
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
    """Data corruption: string donde debe ir número -> validación falla."""
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
    """Data corruption: user_id no es UUID."""
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
