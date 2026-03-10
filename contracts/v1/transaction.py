"""
Transaction schema - source of truth for validation.
"""
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from contracts.v1.event import BaseEvent


class TransactionSchema(BaseEvent):
    """
    Expected schema for a transaction.
    Used by the Validator and as reference in the Repair Agent.
    """

    amount: Decimal = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)
    user_id: UUID
    email: str = Field(..., pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    description: str | None = None

    model_config = {"str_strict": True}
