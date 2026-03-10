"""
Loader (Final): listens to validated_data and schema_fixed; persists to destination (DWH).

Idempotency: uses Envelope event_id to check if the event was already processed.
On retries due to network failure, records are not duplicated in the DWH.
"""
from motia import FlowContext, queue

# State for idempotency: keys by event_id (or request_id if no event_id)
LOADER_PROCESSED_GROUP = "loader"
LOADER_PROCESSED_STREAM = "loader_processed"

config = {
    "name": "DataLoader",
    "description": "Inserts validated or repaired data into the DWH (idempotent by event_id)",
    "triggers": [
        queue("validated_data"),
        queue("schema_fixed"),
    ],
    "enqueues": [],
    "flows": ["data-sentinel"],
}


def _idempotency_key(data: dict) -> str:
    """Unique key for this event: Envelope event_id or request_id as fallback."""
    event_id = data.get("event_id")
    if event_id is not None:
        return str(event_id)
    return data.get("request_id", "unknown")


async def _already_processed(ctx: FlowContext, key: str) -> bool:
    """True if this event was already loaded (avoids duplicates on retries)."""
    try:
        from motia import Stream
        stream = Stream[dict](LOADER_PROCESSED_STREAM)
        marker = await stream.get(LOADER_PROCESSED_GROUP, key)
        return marker is not None
    except Exception:
        return False


async def _mark_processed(ctx: FlowContext, key: str, data: dict) -> None:
    """Marks the event as processed in State (for idempotency)."""
    try:
        from motia import Stream
        stream = Stream[dict](LOADER_PROCESSED_STREAM)
        await stream.set(LOADER_PROCESSED_GROUP, key, {"loaded": True, "request_id": data.get("request_id")})
    except Exception as e:
        ctx.logger.warning("Could not mark event as processed", {"key": key, "error": str(e)})


async def handler(data: dict, ctx: FlowContext) -> None:
    """
    Loads to DWH idempotently: if event_id was already processed, skip.
    Thus retries due to network failure do not duplicate records.
    """
    key = _idempotency_key(data)
    request_id = data.get("request_id", "unknown")

    if await _already_processed(ctx, key):
        ctx.logger.info("Event already loaded (idempotent skip)", {"request_id": request_id, "event_id": key})
        return

    ctx.logger.info("Loading to DWH", {"request_id": request_id, "event_id": key})
    # In production: connect to DB/warehouse and insert.
    # Here we only log as simulation.
    ctx.logger.info("Data loaded successfully", {"request_id": request_id, "keys": list(data.keys())})

    await _mark_processed(ctx, key, data)
