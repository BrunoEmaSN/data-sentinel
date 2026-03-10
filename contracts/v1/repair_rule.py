"""
Repair rules (Cache-Aside): "lesson learned" by the Sentinel.

Structure persisted in State with TTL so third-party APIs
can change and the AI re-evaluates after expiry.
"""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# Structural transformation types (zero hallucination)
TransformationType = Literal["rename", "cast_to_float", "cast_to_int", "map_value"]


class RepairRule(BaseModel):
    """
    A repair rule: source -> target mapping and transformation type.
    Structural transformations only; never invent business values.
    """

    source_field: str = Field(..., description="Name of the field in the payload that fails or must be transformed.")
    target_field: str = Field(..., description="Name of the field expected by the schema (or same as source if cast).")
    transformation_type: TransformationType = Field(
        default="rename",
        description="Type: rename, cast_to_float, cast_to_int, map_value.",
    )
    # For map_value: optional replacement dict (e.g. {"yes": true, "no": false})
    value_map: dict[str, Any] | None = Field(default=None, description="Only for transformation_type=map_value.")

    model_config = {"str_strict": True}


class StoredRepairRule(BaseModel):
    """
    Rule stored in State with TTL. After expires_at the rule is considered
    expired and the system may query the AI again.
    """

    rules: list[RepairRule] = Field(default_factory=list, description="List of rules for this error type.")
    expires_at: datetime = Field(..., description="Expiration date (TTL); after it the rule is ignored.")
    # Compatibility: if only field_mapping from previous version
    field_mapping: dict[str, str] | None = Field(default=None, description="Legacy: source -> target mapping (rename).")

    model_config = {"str_strict": True}
