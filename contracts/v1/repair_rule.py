"""
Reglas de reparación (Cache-Aside): "lección aprendida" por el Sentinel.

Estructura persistida en State con TTL para que las APIs de terceros
puedan cambiar y la IA re-evalúe tras la expiración.
"""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# Tipos de transformación estructural (zero hallucination)
TransformationType = Literal["rename", "cast_to_float", "cast_to_int", "map_value"]


class RepairRule(BaseModel):
    """
    Una regla de reparación: mapeo origen -> destino y tipo de transformación.
    Solo transformaciones estructurales; nunca inventar valores de negocio.
    """

    source_field: str = Field(..., description="Nombre del campo en el payload que falla o debe transformarse.")
    target_field: str = Field(..., description="Nombre del campo esperado por el esquema (o mismo que source si es cast).")
    transformation_type: TransformationType = Field(
        default="rename",
        description="Tipo: rename, cast_to_float, cast_to_int, map_value.",
    )
    # Para map_value: opcional dict de reemplazo (ej. {"yes": true, "no": false})
    value_map: dict[str, Any] | None = Field(default=None, description="Solo para transformation_type=map_value.")

    model_config = {"str_strict": True}


class StoredRepairRule(BaseModel):
    """
    Regla guardada en State con TTL. Tras expires_at la regla se considera
    expirada y el sistema puede volver a consultar a la IA.
    """

    rules: list[RepairRule] = Field(default_factory=list, description="Lista de reglas para este tipo de error.")
    expires_at: datetime = Field(..., description="Fecha de expiración (TTL); tras ella la regla se ignora.")
    # Compatibilidad: si viene solo field_mapping de versión anterior
    field_mapping: dict[str, str] | None = Field(default=None, description="Legacy: mapeo source -> target (rename).")

    model_config = {"str_strict": True}
