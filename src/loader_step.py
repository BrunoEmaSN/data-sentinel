"""
Loader (Final): escucha validated_data y schema_fixed; persiste en destino (DWH).
Sin validación; solo persistencia o reenvío.
"""
from motia import FlowContext, queue

config = {
    "name": "DataLoader",
    "description": "Inserta datos validados o reparados en el Data Warehouse",
    "triggers": [
        queue("validated_data"),
        queue("schema_fixed"),
    ],
    "enqueues": [],
    "flows": ["data-sentinel"],
}


async def handler(data: dict, ctx: FlowContext) -> None:
    """Recibe payload ya válido; simula/realiza inserción en DWH."""
    request_id = data.get("request_id", "unknown")
    ctx.logger.info("Loading to DWH", {"request_id": request_id})
    # En producción: conectar a BD/warehouse e insertar.
    # Aquí solo logueamos como simulación.
    ctx.logger.info("Data loaded successfully", {"request_id": request_id, "keys": list(data.keys())})
