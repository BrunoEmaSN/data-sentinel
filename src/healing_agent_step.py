"""
Agente de reparación (Healing Agent): escucha validation_error.
Cache-Aside: 1) Buscar en State (CacheProvider) regla conocida; 2) Si no hay, llamar al LLM.
Al aprender: persiste RepairRule con TTL para que la IA re-evalúe tras expiración.
Separación: orquestador delega a repair_state (cache) o a _call_llm_for_fix (AIProvider).
"""
import json
import os
import re
from typing import Any

from motia import FlowContext, queue
from pydantic import ValidationError

from contracts.v1.repair_rule import RepairRule
from contracts.v1.transaction import TransactionSchema
from repair_state import (
    apply_rule_idempotent,
    build_stored_rule,
    error_signature,
    get_repair_rule,
    set_repair_rule,
)

# Esquema objetivo (mismo que el Validador)
TARGET_SCHEMA_MODEL = TransactionSchema
# TTL en días para reglas nuevas (configurable por env)
REPAIR_RULE_TTL_DAYS_ENV = "REPAIR_RULE_TTL_DAYS"
DEFAULT_TTL_DAYS = 7

# --- PROMPT MAESTRO: estricto, orientado a esquema, sin alucinaciones ---
MASTER_PROMPT = """Role: You are an expert Data Reliability Engineer specialized in automated Schema Drift Repair.

Objective: Fix incoming raw data payloads that fail validation against a defined Pydantic Schema.

Constraint Rules:
1. Zero Hallucination: Only perform structural repairs (renaming keys, casting types, splitting strings). Never invent, infer, or fill in missing business-critical values.
2. Contract Adherence: Ensure the output strictly matches the target JSON schema provided.
3. Format: Output ONLY valid JSON. Do not include markdown code blocks, prose, or explanations.
4. Handling Failures: If the structural repair is ambiguous or requires business logic changes (e.g., calculating a total that is missing), return an empty JSON object with a "reason" field explaining why it is irreparable: {"reason": "description"}.

Input Provided:
- Raw Payload: {raw_payload}
- Validation Errors: {error_details}
- Target Schema (Pydantic Model): {target_schema}

Execution Strategy:
1. Analyze the field mismatches in the Validation Errors.
2. Determine if the error is a naming drift (e.g., user_email vs email) or a type casting issue (e.g., string vs float).
3. Transform the Raw Payload to align with the Target Schema.
4. Return the cleaned object as a single JSON object, or {{"reason": "..."}} if irreparable."""

config = {
    "name": "HealingAgent",
    "description": "Repara datos con error de validación usando reglas cacheadas o LLM",
    "triggers": [queue("validation_error")],
    "enqueues": ["schema_fixed", "validation_unrecoverable"],
    "flows": ["data-sentinel"],
}


def _ttl_days() -> int:
    """TTL en días para reglas nuevas (env REPAIR_RULE_TTL_DAYS)."""
    try:
        return int(os.environ.get(REPAIR_RULE_TTL_DAYS_ENV, DEFAULT_TTL_DAYS))
    except ValueError:
        return DEFAULT_TTL_DAYS


def _extract_json_from_response(content: str) -> dict | None:
    """
    Extrae el primer objeto JSON de la respuesta del LLM.
    Sin markdown, sin prosa: solo JSON. Si encuentra {"reason": "..."} -> irreparable.
    """
    text = (content or "").strip()
    if not text:
        return None
    # Quitar bloques markdown ```json ... ```
    if "```" in text:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            text = match.group(1).strip()
    try:
        obj = json.loads(text)
        if not isinstance(obj, dict):
            return None
        # Irreparable: el modelo devolvió solo reason (regla 4 del prompt)
        if set(obj.keys()) <= {"reason"} and "reason" in obj:
            return None
        return obj
    except json.JSONDecodeError:
        return None


async def _call_llm_for_fix(payload: dict, error_details: list[dict], ctx: FlowContext) -> dict | None:
    """
    Invoca LLM con el prompt maestro (esquema estricto, zero hallucination).
    Devuelve el JSON corregido o None si irreparable o sin API key.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        ctx.logger.warning("OPENAI_API_KEY not set; skipping LLM remediation")
        return None

    target_schema = TARGET_SCHEMA_MODEL.model_json_schema()
    prompt = MASTER_PROMPT.format(
        raw_payload=json.dumps(payload, default=str),
        error_details=json.dumps(error_details, default=str),
        target_schema=json.dumps(target_schema, default=str),
    )

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key)
        response = await client.chat.completions.create(
            model=os.environ.get("OPENAI_REMEDIATION_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": "You output only valid JSON. No markdown, no explanation."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        content = (response.choices[0].message.content or "").strip()
        return _extract_json_from_response(content)
    except Exception as e:
        ctx.logger.warning("LLM remediation failed", {"error": str(e)})
        return None


async def handler(data: dict, ctx: FlowContext) -> None:
    """
    Cache-Aside: 1) Look-up State (regla conocida). 2) Si hay regla, aplicar (idempotente).
    3) Si no, llamar a IA. 4) Learn: persistir RepairRule con TTL para próximas veces.
    """
    request_id = data.get("request_id", "")
    payload = data.get("payload", {})
    error_details = data.get("error_details", [])
    raw_envelope = data.get("raw_envelope", {})

    ctx.logger.info("Healing agent processing validation_error", {"request_id": request_id})

    sig = error_signature(error_details)
    rule = await get_repair_rule(ctx, sig)

    corrected: dict[str, Any] | None = None

    if rule:
        corrected = apply_rule_idempotent(payload, rule)
        ctx.logger.info("Applied cached repair rule", {"request_id": request_id, "rule_key": sig})
    else:
        corrected = await _call_llm_for_fix(payload, error_details, ctx)
        if corrected:
            # Learning loop: extraer mapeo y persistir como RepairRule con TTL
            rules_list: list[RepairRule] = []
            for err in error_details:
                loc = err.get("loc", [])
                if loc and isinstance(loc[0], str) and loc[0] in payload and loc[0] not in corrected:
                    for correct_key in ["amount", "email", "user_id", "currency", "description", "source"]:
                        if correct_key in corrected and correct_key not in payload:
                            rules_list.append(
                                RepairRule(
                                    source_field=loc[0],
                                    target_field=correct_key,
                                    transformation_type="rename",
                                )
                            )
                            break
            if rules_list:
                ttl = _ttl_days()
                stored = build_stored_rule(rules_list, ttl_days=ttl)
                await set_repair_rule(ctx, sig, stored, ttl_days=ttl)
                ctx.logger.info("Persisted repair rule with TTL", {"rule_key": sig, "ttl_days": ttl})

    if corrected is not None:
        try:
            validated = TransactionSchema.model_validate(corrected)
            out = validated.model_dump(mode="json")
            out["request_id"] = request_id
            out["received_at"] = raw_envelope.get("received_at")
            out["repaired"] = True
            await ctx.enqueue({"topic": "schema_fixed", "data": out})
            ctx.logger.info("Data recovered and emitted as schema_fixed", {"request_id": request_id})
            return
        except ValidationError:
            pass

    # Irreparable: enviar a DLQ
    dlq_payload = {
        "request_id": request_id,
        "payload": payload,
        "error_details": error_details,
        "raw_envelope": raw_envelope,
    }
    await ctx.enqueue({"topic": "validation_unrecoverable", "data": dlq_payload})
    ctx.logger.warning("Sent to DLQ (validation_unrecoverable)", {"request_id": request_id})
