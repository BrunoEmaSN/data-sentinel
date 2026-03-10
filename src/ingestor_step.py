"""
Ingestor (Gateway): recibe JSON crudo vía API y emite raw_event.
No valida; solo recibe, añade metadatos y encola.
"""
import uuid
from datetime import datetime

from motia import ApiRequest, ApiResponse, FlowContext, http

config = {
    "name": "DataIngestor",
    "description": "Recibe datos de webhooks (Stripe, Shopify, etc.) y encola raw_event",
    "triggers": [http("POST", "/ingest")],
    "enqueues": ["raw_event"],
    "flows": ["data-sentinel"],
}


async def handler(req: ApiRequest, ctx: FlowContext) -> ApiResponse:
    """Recibe body JSON, añade metadatos y encola a raw_event."""
    body = req.body if isinstance(req.body, dict) else {}
    request_id = str(uuid.uuid4())
    payload = {
        "request_id": request_id,
        "received_at": datetime.utcnow().isoformat(),
        "source": body.get("source", "unknown"),
        "raw": body,
    }
    ctx.logger.info("Raw data received", {"request_id": request_id, "source": payload["source"]})
    await ctx.enqueue({"topic": "raw_event", "data": payload})
    return ApiResponse(status=202, body={"request_id": request_id, "status": "accepted"})
