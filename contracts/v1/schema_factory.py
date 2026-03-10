"""
Factory de validación por versión del contrato.

Permite instanciar la clase correcta (OrderEvent v1, v2, etc.) según el campo
version del EventEnvelope. Cuando version "2.0.0" añada campos obligatorios nuevos,
registrar aquí OrderEventV2 y el pipeline seguirá funcionando sin breaking changes.
"""
from typing import Type

from contracts.v1.order import OrderEvent
from contracts.v1.transaction import TransactionSchema

# Registro: version -> modelo de orden. Añadir "2.0.0": OrderEventV2 cuando exista.
ORDER_EVENT_REGISTRY: dict[str, Type[OrderEvent]] = {
    "1.0.0": OrderEvent,
    # "2.0.0": OrderEventV2,  # cuando tengas campos nuevos obligatorios
}

# Transacciones: por ahora un solo esquema; ampliar si se versiona.
TRANSACTION_REGISTRY: dict[str, Type] = {
    "1.0.0": TransactionSchema,
}


def get_order_event_model(version: str) -> Type[OrderEvent] | None:
    """
    Devuelve el modelo de OrderEvent para la versión indicada.
    Si la versión no está registrada, devuelve None (el llamador puede fallar o usar default).
    """
    return ORDER_EVENT_REGISTRY.get(version)


def get_order_event_model_or_latest(version: str) -> Type[OrderEvent]:
    """
    Devuelve el modelo para la versión, o el más reciente conocido (1.0.0) si no existe.
    Útil para no romper cuando lleguen versiones nuevas aún no soportadas.
    """
    return get_order_event_model(version) or OrderEvent


def get_transaction_model(version: str) -> Type[TransactionSchema]:
    """Devuelve el modelo de transacción para la versión (por ahora siempre TransactionSchema)."""
    return TRANSACTION_REGISTRY.get(version) or TransactionSchema
