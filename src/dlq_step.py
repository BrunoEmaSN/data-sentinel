"""
Dead Letter Queue: receives events that the AI Agent could not repair.
Only logs and optionally persists for human inspection.
"""
from motia import FlowContext, queue

config = {
    "name": "DeadLetterQueue",
    "description": "Receives unrecoverable events for human inspection",
    "triggers": [queue("validation_unrecoverable")],
    "enqueues": [],
    "flows": ["data-sentinel"],
}


async def handler(data: dict, ctx: FlowContext) -> None:
    """Logs the event in DLQ without retrying validation."""
    request_id = data.get("request_id", "unknown")
    ctx.logger.warning(
        "DLQ: unrecoverable validation error",
        {
            "request_id": request_id,
            "error_count": len(data.get("error_details", [])),
        },
    )
    # In production: persist to storage (S3, table, etc.) for review.
    ctx.logger.info("DLQ event logged", {"request_id": request_id})
