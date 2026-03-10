#!/usr/bin/env python3
"""
Script de simulación: Ruptura del Contrato (Data Sentinel).

Ejecutar en CI/CD para verificar que el sistema es resiliente:
  - El validation_gateway rechaza datos que no cumplen el contrato.
  - Los errores se capturan con detalle (campo, tipo) para el Agente de reparación.
  - El flujo se desvía de forma controlada hacia la auto-reparación (o DLQ).

Uso: python test_sentinel.py
"""
from datetime import datetime

from pydantic import ValidationError

from contracts.v1.order import OrderEvent


def validation_gateway(raw_data: dict) -> dict:
    """
    El portero que valida el contrato.
    Única responsabilidad: ¿Cumple el contrato? Sí/No.
    """
    try:
        event = OrderEvent.model_validate(raw_data)
        print(f"✅ [OK] Evento {event.payload.order_id} validado correctamente.")
        return {"status": "success", "data": event}
    except ValidationError as e:
        order_id = raw_data.get("payload", {}).get("order_id", "Desconocido")
        print(f"❌ [ALERTA] Esquema roto en evento: {order_id}")
        return {"status": "failed", "error": e.errors(), "order_id": order_id}


def ai_sentinel_repair(error_details: list, raw_data: dict) -> str:
    """
    Simula la intervención de la IA para reparar el dato.
    En producción, el LLM analiza error_details y sugiere una corrección.
    """
    print("🤖 [SENTINEL] Iniciando protocolo de auto-reparación...")
    order_id = raw_data.get("payload", {}).get("order_id", "N/A")
    return f"REPAIR_SUGGESTED_FOR_{order_id}"


# --- CASO DE PRUEBA: DATO INVÁLIDO (email malformado) ---
BAD_DATA = {
    "event_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": datetime.utcnow().isoformat(),
    "version": "1.0.0",
    "source": "ecommerce_api",
    "payload": {
        "order_id": "ORD-123",
        "customer_email": "esto-no-es-un-email",  # <--- ERROR AQUÍ
        "items": [{"sku": "PROD-1", "quantity": 1, "price": 10.5}],
        "total_amount": 10.5,
        "currency": "USD",
    },
}

# --- CASO DE PRUEBA: DATO VÁLIDO (opcional, para contrastar) ---
GOOD_DATA = {
    "event_id": "550e8400-e29b-41d4-a716-446655440001",
    "timestamp": datetime.utcnow().isoformat(),
    "version": "1.0.0",
    "source": "ecommerce_api",
    "payload": {
        "order_id": "ORD-456",
        "customer_email": "cliente@ejemplo.com",
        "items": [{"sku": "PROD-2", "quantity": 2, "price": 25.0}],
        "total_amount": 50.0,
        "currency": "EUR",
    },
}


def main() -> None:
    print("=== Data Sentinel: Simulación de Ruptura del Contrato ===\n")

    # 1. Caso inválido: debe fallar y disparar el flujo de reparación
    print("1. Enviando dato malformado (email inválido)...")
    result = validation_gateway(BAD_DATA)

    if result["status"] == "failed":
        repair_action = ai_sentinel_repair(result["error"], BAD_DATA)
        print(f"🔧 [REPARACIÓN] {repair_action}")
        print("\nDetalle de errores (para el Agente/LLM):")
        for err in result["error"]:
            print(f"   - {err}")

    # 2. Caso válido: debe pasar sin alerta
    print("\n2. Enviando dato válido...")
    validation_gateway(GOOD_DATA)

    print("\n=== Fin de la simulación ===")


if __name__ == "__main__":
    main()
