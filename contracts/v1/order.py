"""
Contrato de Orden (Envelope + Payload).

Ejemplo de estructura Sobre/Cuerpo: el Validador puede inspeccionar
event_id, version y source antes de validar el payload.
Documentación en cada campo para catálogo de datos y OpenAPI.
"""
from typing import List

from pydantic import BaseModel, EmailStr, Field

from contracts.v1.event import EventEnvelope


# --- EL CUERPO (Payload) ---
# Definido por Data Engineering y Negocio; validación de negocio integrada.


class OrderItem(BaseModel):
    """Línea de detalle de una orden."""

    sku: str = Field(..., description="Código único del producto (SKU).")
    quantity: int = Field(..., gt=0, description="Cantidad; debe ser al menos 1.")
    price: float = Field(..., ge=0, description="Precio unitario; no negativo.")

    model_config = {"str_strict": True}


class OrderPayload(BaseModel):
    """Payload de negocio de una orden: datos que importan para procesamiento y analytics."""

    order_id: str = Field(..., description="Identificador de negocio de la orden.")
    customer_email: EmailStr = Field(..., description="Email del cliente para notificaciones y factura.")
    items: List[OrderItem] = Field(..., description="Lista de ítems de la orden.")
    total_amount: float = Field(..., ge=0, description="Total de la orden; debe ser >= 0.")
    currency: str = Field(
        ...,
        min_length=3,
        max_length=3,
        description="Código ISO 4217 de moneda (ej. USD, EUR).",
    )

    model_config = {"str_strict": True}


# --- EL CONTRATO FINAL (Envelope + Payload) ---


class OrderEvent(EventEnvelope):
    """
    Evento de orden completo: sobre (metadata) + payload (datos de negocio).
    Toda ingestión de órdenes debe validarse contra este contrato;
    si falla, el sistema debe etiquetar como UNPROCESSED_DLQ en el Workbench.
    """

    payload: OrderPayload = Field(..., description="Cuerpo de la orden validado por el esquema de negocio.")

    model_config = {"str_strict": True}
