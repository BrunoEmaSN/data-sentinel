"""
Esquema de transacción - verdad de negocio para validación.
"""
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from contracts.v1.event import BaseEvent


class TransactionSchema(BaseEvent):
    """
    Esquema esperado de una transacción.
    Usado por el Validador y como referencia en el Agente de reparación.
    """

    amount: Decimal = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)
    user_id: UUID
    email: str = Field(..., pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    description: str | None = None

    model_config = {"str_strict": True}
