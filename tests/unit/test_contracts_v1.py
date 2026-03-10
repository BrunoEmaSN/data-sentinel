"""
Unit tests: Pydantic models in contracts/v1.
Edge cases: missing fields, wrong types, boundary values.
"""
import uuid
from decimal import Decimal
from datetime import datetime

import pytest
from pydantic import ValidationError

from contracts.v1.event import BaseEvent, EventEnvelope
from contracts.v1.order import OrderEvent, OrderItem, OrderPayload
from contracts.v1.transaction import TransactionSchema


class TestBaseEvent:
    """Edge cases for BaseEvent."""

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


class TestEventEnvelope:
    """Cases for the envelope with versioning."""

    def test_valid_defaults(self):
        e = EventEnvelope()
        assert e.event_id is not None
        assert e.timestamp is not None
        assert e.version == "1.0.0"
        assert e.source == "ecommerce_api"

    def test_version_evolution(self):
        e = EventEnvelope(version="2.0.0", source="orders_api")
        assert e.version == "2.0.0"
        assert e.source == "orders_api"


class TestOrderItem:
    """Business validation for order items."""

    def test_valid(self):
        item = OrderItem(sku="SKU-001", quantity=2, price=9.99)
        assert item.sku == "SKU-001"
        assert item.quantity == 2
        assert item.price == 9.99

    def test_quantity_zero_rejected(self):
        with pytest.raises(ValidationError):
            OrderItem(sku="X", quantity=0, price=1.0)

    def test_quantity_negative_rejected(self):
        with pytest.raises(ValidationError):
            OrderItem(sku="X", quantity=-1, price=1.0)

    def test_price_negative_rejected(self):
        with pytest.raises(ValidationError):
            OrderItem(sku="X", quantity=1, price=-1.0)


class TestOrderPayload:
    """Order payload: email, currency, items."""

    @pytest.fixture
    def valid_payload(self):
        return {
            "order_id": "ORD-123",
            "customer_email": "customer@example.com",
            "items": [{"sku": "A", "quantity": 1, "price": 10.0}],
            "total_amount": 10.0,
            "currency": "USD",
        }

    def test_valid(self, valid_payload):
        p = OrderPayload.model_validate(valid_payload)
        assert p.order_id == "ORD-123"
        assert str(p.customer_email) == "customer@example.com"
        assert len(p.items) == 1
        assert p.items[0].sku == "A"
        assert p.currency == "USD"

    def test_invalid_email(self, valid_payload):
        valid_payload["customer_email"] = "not-an-email"
        with pytest.raises(ValidationError):
            OrderPayload.model_validate(valid_payload)

    def test_currency_not_3_chars(self, valid_payload):
        valid_payload["currency"] = "US"
        with pytest.raises(ValidationError):
            OrderPayload.model_validate(valid_payload)


class TestOrderEvent:
    """Final contract: Envelope + Payload."""

    @pytest.fixture
    def valid_order_event(self):
        return {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "source": "ecommerce_api",
            "payload": {
                "order_id": "ORD-456",
                "customer_email": "buyer@shop.com",
                "items": [{"sku": "B", "quantity": 3, "price": 5.0}],
                "total_amount": 15.0,
                "currency": "EUR",
            },
        }

    def test_valid_full(self, valid_order_event):
        ev = OrderEvent.model_validate(valid_order_event)
        assert ev.version == "1.0.0"
        assert ev.source == "ecommerce_api"
        assert ev.payload.order_id == "ORD-456"
        assert ev.payload.customer_email
        assert len(ev.payload.items) == 1
        assert ev.payload.items[0].quantity == 3

    def test_contract_fail_before_process(self, valid_order_event):
        """If the contract is not met, it fails before processing (invalid payload)."""
        valid_order_event["payload"]["customer_email"] = "invalid"
        with pytest.raises(ValidationError):
            OrderEvent.model_validate(valid_order_event)


class TestTransactionSchema:
    """Edge cases for TransactionSchema."""

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
        """Simulates drift: 'price' field instead of 'amount'."""
        valid_payload["price"] = valid_payload.pop("amount")
        with pytest.raises(ValidationError) as exc_info:
            TransactionSchema.model_validate(valid_payload)
        errors = exc_info.value.errors()
        assert any("amount" in str(e.get("loc", [])) for e in errors)
