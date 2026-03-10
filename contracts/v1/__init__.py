"""
Contratos v1 - Fuente de verdad para esquemas del dominio.
"""
from contracts.v1.event import BaseEvent, EventEnvelope
from contracts.v1.order import OrderEvent, OrderItem, OrderPayload
from contracts.v1.repair_rule import RepairRule, StoredRepairRule
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
]
