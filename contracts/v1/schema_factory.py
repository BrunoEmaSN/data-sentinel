"""
Validation factory by contract version.

Allows instantiating the correct class (OrderEvent v1, v2, etc.) based on the
EventEnvelope version field. When version "2.0.0" adds new required fields,
register OrderEventV2 here and the pipeline will keep working without breaking changes.
"""
from typing import Type

from contracts.v1.order import OrderEvent
from contracts.v1.transaction import TransactionSchema

# Registry: version -> order model. Add "2.0.0": OrderEventV2 when it exists.
ORDER_EVENT_REGISTRY: dict[str, Type[OrderEvent]] = {
    "1.0.0": OrderEvent,
    # "2.0.0": OrderEventV2,  # when you have new required fields
}

# Transactions: single schema for now; extend if versioned.
TRANSACTION_REGISTRY: dict[str, Type] = {
    "1.0.0": TransactionSchema,
}


def get_order_event_model(version: str) -> Type[OrderEvent] | None:
    """
    Returns the OrderEvent model for the given version.
    If the version is not registered, returns None (caller may fail or use default).
    """
    return ORDER_EVENT_REGISTRY.get(version)


def get_order_event_model_or_latest(version: str) -> Type[OrderEvent]:
    """
    Returns the model for the version, or the latest known (1.0.0) if it does not exist.
    Useful to avoid breaking when new unsupported versions arrive.
    """
    return get_order_event_model(version) or OrderEvent


def get_transaction_model(version: str) -> Type[TransactionSchema]:
    """Returns the transaction model for the version (for now always TransactionSchema)."""
    return TRANSACTION_REGISTRY.get(version) or TransactionSchema
