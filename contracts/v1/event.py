"""
Modelo base de evento para el pipeline.
"""
import uuid
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class BaseEvent(BaseModel):
    """Evento base con metadatos de trazabilidad."""

    event_id: UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = "unknown"

    model_config = {"str_strict": True}
