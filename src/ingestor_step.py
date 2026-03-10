"""
Ingestor (Gateway): receives raw JSON via API and emits raw_event.
Does not validate; only receives, adds metadata and enqueues.
"""
import uuid
from datetime import datetime

from motia import ApiRequest, ApiResponse, FlowContext, http

config = {
    "name": "DataIngestor",
    "description": "Receives webhook data (Stripe, Shopify, etc.) and enqueues raw_event",
    "triggers": [http("POST", "/ingest")],
    "enqueues": ["raw_event"],
    "flows": ["data-sentinel"],
}


async def handler(req: ApiRequest, ctx: FlowContext) -> ApiResponse:
    """Receives JSON body, adds metadata and enqueues to raw_event."""
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
