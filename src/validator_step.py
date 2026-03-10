"""
Optimized Validator (Cache-Aside): listens to raw_event, validates with Pydantic.
Look-up -> Decide -> Learn: on failure, looks up rule in State and re-validates before emitting error.
Emits validated_data, schema_fixed (cache repair) or validation_error.
"""
from motia import FlowContext, queue

from contracts.v1.schema_factory import get_transaction_model
from pydantic import ValidationError

from repair_state import apply_rule_idempotent, error_signature, get_repair_rule

config = {
    "name": "DataValidator",
    "description": "Validates payload; on failure, applies cached rule (Cache-Aside) or emits validation_error",
    "triggers": [queue("raw_event")],
    "enqueues": ["validated_data", "schema_fixed", "validation_error"],
    "flows": ["data-sentinel"],
}


async def handler(data: dict, ctx: FlowContext) -> None:
    """
    Flow: 1) Validate. 2) On failure, look up State (CacheProvider). 3) If rule exists, apply
    (idempotent) and re-validate. 4) Only if no rule or still failing, emit validation_error.
    """
    request_id = data.get("request_id", "")
    raw = data.get("raw", {})
    ctx.logger.info("Validating payload", {"request_id": request_id})

    schema_cls = get_transaction_model(raw.get("version", "1.0.0"))

    try:
        validated = schema_cls.model_validate(raw)
        payload_out = validated.model_dump(mode="json")
        payload_out["request_id"] = request_id
        payload_out["received_at"] = data.get("received_at")
        await ctx.enqueue({"topic": "validated_data", "data": payload_out})
        ctx.logger.info("Validation passed", {"request_id": request_id})
        return
    except ValidationError as e:
        error_details = e.errors()

    # Cache-Aside: do we already know this error?
    sig = error_signature([{"loc": err["loc"], "type": err["type"]} for err in error_details])
    rule = await get_repair_rule(ctx, sig)

    if rule:
        fixed = apply_rule_idempotent(raw, rule)
        try:
            validated = schema_cls.model_validate(fixed)
            out = validated.model_dump(mode="json")
            out["request_id"] = request_id
            out["received_at"] = data.get("received_at")
            out["repaired"] = True
            await ctx.enqueue({"topic": "schema_fixed", "data": out})
            ctx.logger.info("Repaired via cached rule", {"request_id": request_id, "rule_key": sig})
            return
        except ValidationError:
            pass

    # No rule or rule not applicable: delegate to Healing Agent (AI)
    error_payload = {
        "request_id": request_id,
        "payload": raw,
        "error_details": [{"loc": err["loc"], "msg": err["msg"], "type": err["type"]} for err in error_details],
        "raw_envelope": data,
    }
    await ctx.enqueue({"topic": "validation_error", "data": error_payload})
    ctx.logger.warning("Validation failed", {"request_id": request_id, "errors": error_details})
