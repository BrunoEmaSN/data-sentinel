"""
Contratos v1 - Fuente de verdad para esquemas del dominio.
"""
from contracts.v1.event import BaseEvent
from contracts.v1.transaction import TransactionSchema

__all__ = ["BaseEvent", "TransactionSchema"]
