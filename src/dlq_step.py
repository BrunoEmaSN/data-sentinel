"""
Dead Letter Queue: recibe eventos que el Agente de IA no pudo reparar.
Solo registra y opcionalmente persiste para inspección humana.
"""
from motia import FlowContext, queue

config = {
    "name": "DeadLetterQueue",
    "description": "Recibe eventos irreparables para inspección humana",
    "triggers": [queue("validation_unrecoverable")],
    "enqueues": [],
    "flows": ["data-sentinel"],
}


async def handler(data: dict, ctx: FlowContext) -> None:
    """Registra el evento en DLQ sin reintentar validación."""
    request_id = data.get("request_id", "unknown")
    ctx.logger.warning(
        "DLQ: unrecoverable validation error",
        {
            "request_id": request_id,
            "error_count": len(data.get("error_details", [])),
        },
    )
    # En producción: persistir en almacenamiento (S3, tabla, etc.) para revisión.
    ctx.logger.info("DLQ event logged", {"request_id": request_id})
