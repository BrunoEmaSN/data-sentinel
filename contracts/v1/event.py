"""
Base event model for the pipeline.

Includes BaseEvent (legacy) and EventEnvelope: the "envelope" that lets the Validator
know what to do with the message before reading the payload (versioning, source, etc.).
"""
import uuid
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class BaseEvent(BaseModel):
    """Base event with traceability metadata (compatibility with TransactionSchema)."""

    event_id: UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = "unknown"

    model_config = {"str_strict": True}


# --- THE ENVELOPE (Metadata) ---
# Any event with this structure can be traced in the Motia Workbench.
# The Validator can inspect version/source before parsing the payload.


class EventEnvelope(BaseModel):
    """
    Event envelope: required metadata for traceability and versioning.
    Use as base for contracts that separate header (envelope) and body (payload).
    """

    event_id: UUID = Field(
        default_factory=uuid.uuid4,
        description="Unique event identifier for correlation and replay.",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Event emission time (UTC).",
    )
    version: str = Field(
        default="1.0.0",
        description="Payload schema version; crucial for evolution without breaking changes.",
    )
    source: str = Field(
        default="ecommerce_api",
        description="System or service that emitted the event (e.g. ecommerce_api, stripe).",
    )

    model_config = {"str_strict": True}
