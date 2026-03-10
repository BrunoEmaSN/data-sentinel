"""
Validador optimizado (Cache-Aside): escucha raw_event, valida con Pydantic.
Look-up -> Decide -> Learn: si falla, busca regla en State y re-valida antes de emitir error.
Emite validated_data, schema_fixed (reparación por cache) o validation_error.
"""
from motia import FlowContext, queue

from contracts.v1.transaction import TransactionSchema
from pydantic import ValidationError

from repair_state import apply_rule_idempotent, error_signature, get_repair_rule

config = {
    "name": "DataValidator",
    "description": "Valida payload; si falla, aplica regla en cache (Cache-Aside) o emite validation_error",
    "triggers": [queue("raw_event")],
    "enqueues": ["validated_data", "schema_fixed", "validation_error"],
    "flows": ["data-sentinel"],
}


async def handler(data: dict, ctx: FlowContext) -> None:
    """
    Flujo: 1) Validar. 2) Si falla, buscar en State (CacheProvider). 3) Si hay regla, aplicar
    (idempotente) y re-validar. 4) Solo si no hay regla o sigue fallando, emitir validation_error.
    """
    request_id = data.get("request_id", "")
    raw = data.get("raw", {})
    ctx.logger.info("Validating payload", {"request_id": request_id})

    try:
        validated = TransactionSchema.model_validate(raw)
        payload_out = validated.model_dump(mode="json")
        payload_out["request_id"] = request_id
        payload_out["received_at"] = data.get("received_at")
        await ctx.enqueue({"topic": "validated_data", "data": payload_out})
        ctx.logger.info("Validation passed", {"request_id": request_id})
        return
    except ValidationError as e:
        error_details = e.errors()

    # Cache-Aside: ¿ya conocemos este error?
    sig = error_signature([{"loc": err["loc"], "type": err["type"]} for err in error_details])
    rule = await get_repair_rule(ctx, sig)

    if rule:
        fixed = apply_rule_idempotent(raw, rule)
        try:
            validated = TransactionSchema.model_validate(fixed)
            out = validated.model_dump(mode="json")
            out["request_id"] = request_id
            out["received_at"] = data.get("received_at")
            out["repaired"] = True
            await ctx.enqueue({"topic": "schema_fixed", "data": out})
            ctx.logger.info("Repaired via cached rule", {"request_id": request_id, "rule_key": sig})
            return
        except ValidationError:
            pass

    # Sin regla o regla no aplicable: delegar al Healing Agent (AI)
    error_payload = {
        "request_id": request_id,
        "payload": raw,
        "error_details": [{"loc": err["loc"], "msg": err["msg"], "type": err["type"]} for err in error_details],
        "raw_envelope": data,
    }
    await ctx.enqueue({"topic": "validation_error", "data": error_payload})
    ctx.logger.warning("Validation failed", {"request_id": request_id, "errors": error_details})
