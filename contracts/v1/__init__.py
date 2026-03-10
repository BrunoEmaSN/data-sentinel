"""
Contratos v1 - Fuente de verdad para esquemas del dominio.
"""
from contracts.v1.event import BaseEvent, EventEnvelope
from contracts.v1.order import OrderEvent, OrderItem, OrderPayload
from contracts.v1.repair_rule import RepairRule, StoredRepairRule
from contracts.v1.schema_factory import (
    get_order_event_model,
    get_order_event_model_or_latest,
    get_transaction_model,
)
from contracts.v1.transaction import TransactionSchema

__all__ = [
    "BaseEvent",
    "EventEnvelope",
    "OrderEvent",
    "OrderItem",
    "OrderPayload",
    "RepairRule",
    "StoredRepairRule",
    "TransactionSchema",
    "get_order_event_model",
    "get_order_event_model_or_latest",
    "get_transaction_model",
]
