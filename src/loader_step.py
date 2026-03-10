"""
Loader (Final): escucha validated_data y schema_fixed; persiste en destino (DWH).

Idempotencia: usa event_id del Envelope para verificar si el evento ya fue procesado.
En reintentos por fallo de red no se duplican registros en el DWH.
"""
from motia import FlowContext, queue

# State para idempotencia: claves por event_id (o request_id si no hay event_id)
LOADER_PROCESSED_GROUP = "loader"
LOADER_PROCESSED_STREAM = "loader_processed"

config = {
    "name": "DataLoader",
    "description": "Inserta datos validados o reparados en el DWH (idempotente por event_id)",
    "triggers": [
        queue("validated_data"),
        queue("schema_fixed"),
    ],
    "enqueues": [],
    "flows": ["data-sentinel"],
}


def _idempotency_key(data: dict) -> str:
    """Clave única para este evento: event_id del Envelope o request_id como fallback."""
    event_id = data.get("event_id")
    if event_id is not None:
        return str(event_id)
    return data.get("request_id", "unknown")


async def _already_processed(ctx: FlowContext, key: str) -> bool:
    """True si este evento ya fue cargado (evita duplicados en reintentos)."""
    try:
        from motia import Stream
        stream = Stream[dict](LOADER_PROCESSED_STREAM)
        marker = await stream.get(LOADER_PROCESSED_GROUP, key)
        return marker is not None
    except Exception:
        return False


async def _mark_processed(ctx: FlowContext, key: str, data: dict) -> None:
    """Marca el evento como procesado en el State (para idempotencia)."""
    try:
        from motia import Stream
        stream = Stream[dict](LOADER_PROCESSED_STREAM)
        await stream.set(LOADER_PROCESSED_GROUP, key, {"loaded": True, "request_id": data.get("request_id")})
    except Exception as e:
        ctx.logger.warning("Could not mark event as processed", {"key": key, "error": str(e)})


async def handler(data: dict, ctx: FlowContext) -> None:
    """
    Carga en DWH de forma idempotente: si event_id ya fue procesado, se omite.
    Así los reintentos por fallo de red no duplican registros.
    """
    key = _idempotency_key(data)
    request_id = data.get("request_id", "unknown")

    if await _already_processed(ctx, key):
        ctx.logger.info("Event already loaded (idempotent skip)", {"request_id": request_id, "event_id": key})
        return

    ctx.logger.info("Loading to DWH", {"request_id": request_id, "event_id": key})
    # En producción: conectar a BD/warehouse e insertar.
    # Aquí solo logueamos como simulación.
    ctx.logger.info("Data loaded successfully", {"request_id": request_id, "keys": list(data.keys())})

    await _mark_processed(ctx, key, data)
