"""
Validador (Logic): escucha raw_event, valida con contratos Pydantic.
Emite validated_data si OK, validation_error si falla.
"""
from motia import FlowContext, queue

from contracts.v1.transaction import TransactionSchema
from pydantic import ValidationError

config = {
    "name": "DataValidator",
    "description": "Valida payload con esquema de transacción; emite validated_data o validation_error",
    "triggers": [queue("raw_event")],
    "enqueues": ["validated_data", "validation_error"],
    "flows": ["data-sentinel"],
}


async def handler(data: dict, ctx: FlowContext) -> None:
    """Valida con TransactionSchema; encola validated_data o validation_error."""
    request_id = data.get("request_id", "")
    raw = data.get("raw", {})
    ctx.logger.info("Validating payload", {"request_id": request_id})

    try:
        # Intentar validar contra el contrato de negocio
        validated = TransactionSchema.model_validate(raw)
        payload_out = validated.model_dump(mode="json")
        payload_out["request_id"] = request_id
        payload_out["received_at"] = data.get("received_at")
        await ctx.enqueue({"topic": "validated_data", "data": payload_out})
        ctx.logger.info("Validation passed", {"request_id": request_id})
    except ValidationError as e:
        error_details = e.errors()
        error_payload = {
            "request_id": request_id,
            "payload": raw,
            "error_details": [{"loc": err["loc"], "msg": err["msg"], "type": err["type"]} for err in error_details],
            "raw_envelope": data,
        }
        await ctx.enqueue({"topic": "validation_error", "data": error_payload})
        ctx.logger.warning("Validation failed", {"request_id": request_id, "errors": error_details})
