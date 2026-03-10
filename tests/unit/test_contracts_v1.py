"""
Unit tests: modelos Pydantic en contracts/v1.
Casos borde: campos faltantes, tipos erróneos, valores límite.
"""
import uuid
from decimal import Decimal
from datetime import datetime

import pytest
from pydantic import ValidationError

from contracts.v1.event import BaseEvent
from contracts.v1.transaction import TransactionSchema


class TestBaseEvent:
    """Casos borde para BaseEvent."""

    def test_valid_minimal(self):
        e = BaseEvent(source="stripe")
        assert e.source == "stripe"
        assert e.event_id is not None
        assert e.timestamp is not None

    def test_valid_full(self):
        e = BaseEvent(event_id=uuid.uuid4(), timestamp=datetime.utcnow(), source="shopify")
        assert e.source == "shopify"

    def test_invalid_source_empty(self):
        with pytest.raises(ValidationError):
            BaseEvent(source="")

    def test_invalid_event_id_type(self):
        with pytest.raises(ValidationError):
            BaseEvent(event_id="not-a-uuid", source="x")


class TestTransactionSchema:
    """Casos borde para TransactionSchema."""

    @pytest.fixture
    def valid_payload(self):
        return {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "source": "stripe",
            "amount": "99.99",
            "currency": "USD",
            "user_id": str(uuid.uuid4()),
            "email": "user@example.com",
            "description": "Test",
        }

    def test_valid_full(self, valid_payload):
        t = TransactionSchema.model_validate(valid_payload)
        assert t.amount == Decimal("99.99")
        assert t.currency == "USD"
        assert t.email == "user@example.com"

    def test_valid_description_optional(self, valid_payload):
        del valid_payload["description"]
        t = TransactionSchema.model_validate(valid_payload)
        assert t.description is None

    def test_missing_required_field(self, valid_payload):
        del valid_payload["amount"]
        with pytest.raises(ValidationError) as exc_info:
            TransactionSchema.model_validate(valid_payload)
        errors = exc_info.value.errors()
        assert any("amount" in str(e.get("loc", [])) for e in errors)

    def test_wrong_type_amount_string_garbage(self, valid_payload):
        valid_payload["amount"] = "not-a-number"
        with pytest.raises(ValidationError):
            TransactionSchema.model_validate(valid_payload)

    def test_amount_zero_rejected(self, valid_payload):
        valid_payload["amount"] = "0"
        with pytest.raises(ValidationError):
            TransactionSchema.model_validate(valid_payload)

    def test_amount_negative_rejected(self, valid_payload):
        valid_payload["amount"] = "-10"
        with pytest.raises(ValidationError):
            TransactionSchema.model_validate(valid_payload)

    def test_currency_not_3_chars(self, valid_payload):
        valid_payload["currency"] = "US"
        with pytest.raises(ValidationError):
            TransactionSchema.model_validate(valid_payload)

    def test_invalid_email(self, valid_payload):
        valid_payload["email"] = "not-an-email"
        with pytest.raises(ValidationError):
            TransactionSchema.model_validate(valid_payload)

    def test_schema_drift_price_instead_of_amount(self, valid_payload):
        """Simula drift: campo 'price' en lugar de 'amount'."""
        valid_payload["price"] = valid_payload.pop("amount")
        with pytest.raises(ValidationError) as exc_info:
            TransactionSchema.model_validate(valid_payload)
        errors = exc_info.value.errors()
        assert any("amount" in str(e.get("loc", [])) for e in errors)
