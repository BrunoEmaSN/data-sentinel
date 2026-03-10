"""
Modelo base de evento para el pipeline.

Incluye BaseEvent (legacy) y EventEnvelope: el "sobre" que permite al Validador
saber qué hacer con el mensaje antes de leer el payload (versionado, source, etc.).
"""
import uuid
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class BaseEvent(BaseModel):
    """Evento base con metadatos de trazabilidad (compatibilidad con TransactionSchema)."""

    event_id: UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = "unknown"

    model_config = {"str_strict": True}


# --- EL SOBRE (Metadata) ---
# Todo evento con esta estructura puede rastrearse en el Workbench de Motia.
# El Validador puede inspeccionar version/source antes de parsear el payload.


class EventEnvelope(BaseModel):
    """
    Envelope de evento: metadatos obligatorios para trazabilidad y versionado.
    Usar como base para contratos que separan header (sobre) y body (payload).
    """

    event_id: UUID = Field(
        default_factory=uuid.uuid4,
        description="Identificador único del evento para correlación y replay.",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Momento de emisión del evento (UTC).",
    )
    version: str = Field(
        default="1.0.0",
        description="Versión del esquema del payload; crucial para evolución sin breaking changes.",
    )
    source: str = Field(
        default="ecommerce_api",
        description="Sistema o servicio que emitió el evento (ej. ecommerce_api, stripe).",
    )

    model_config = {"str_strict": True}
