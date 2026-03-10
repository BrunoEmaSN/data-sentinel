"""
Agente de reparación (Healing Agent): escucha validation_error.
Consulta State por regla conocida; si no hay, llama al LLM. Emite schema_fixed o DLQ.
"""
import hashlib
import json
import os
from typing import Any

from motia import FlowContext, queue
from pydantic import ValidationError

from contracts.v1.transaction import TransactionSchema

# Clave para reglas de reparación en State (Motia Stream o fallback en memoria)
REPAIR_RULES_GROUP = "sentinel"
REPAIR_RULES_STREAM = "repair_rules"

config = {
    "name": "HealingAgent",
    "description": "Repara datos con error de validación usando reglas cacheadas o LLM",
    "triggers": [queue("validation_error")],
    "enqueues": ["schema_fixed", "validation_unrecoverable"],
    "flows": ["data-sentinel"],
}


def _error_signature(error_details: list[dict]) -> str:
    """Clave derivada del tipo de error para cache de reglas."""
    parts = []
    for err in error_details:
        loc = err.get("loc", [])
        typ = err.get("type", "")
        parts.append(f"{':'.join(str(x) for x in loc)}:{typ}")
    raw = "|".join(sorted(parts))
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _apply_rule(payload: dict, rule: dict) -> dict:
    """Aplica una regla de mapeo (ej. {'price': 'amount'}) al payload."""
    out = dict(payload)
    for wrong_key, correct_key in rule.get("field_mapping", {}).items():
        if wrong_key in out:
            out[correct_key] = out.pop(wrong_key)
    return out


async def _get_repair_rule(ctx: FlowContext, key: str) -> dict | None:
    """Obtiene regla de reparación desde State (Stream) si está disponible."""
    try:
        from motia import Stream
        stream = Stream[dict](REPAIR_RULES_STREAM)
        rule = await stream.get(REPAIR_RULES_GROUP, key)
        return rule
    except Exception:
        return None


async def _set_repair_rule(ctx: FlowContext, key: str, rule: dict) -> None:
    """Guarda regla de reparación en State."""
    try:
        from motia import Stream
        stream = Stream[dict](REPAIR_RULES_STREAM)
        await stream.set(REPAIR_RULES_GROUP, key, rule)
    except Exception as e:
        ctx.logger.warning("Could not persist repair rule", {"key": key, "error": str(e)})


async def _call_llm_for_fix(payload: dict, error_details: list[dict], ctx: FlowContext) -> dict | None:
    """
    Invoca LLM (OpenAI) para proponer corrección.
    Devuelve el JSON corregido o None si irreparable.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        ctx.logger.warning("OPENAI_API_KEY not set; skipping LLM remediation")
        return None

    schema_hint = (
        "Esquema esperado: event_id (UUID), timestamp (datetime), source (str), "
        "amount (Decimal > 0), currency (3 chars), user_id (UUID), email (email), description (opcional)."
    )
    prompt = (
        "Dados estos datos que fallaron la validación y este esquema esperado, "
        "encuentra si un campo cambió de nombre o tipo y devuelve el JSON corregido. "
        f"{schema_hint}\n\n"
        f"Datos que fallaron: {json.dumps(payload, default=str)}\n"
        f"Errores: {json.dumps(error_details, default=str)}\n\n"
        "Responde ÚNICAMENTE con un objeto JSON válido corregido, o la palabra null si es irreparable."
    )

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key)
        response = await client.chat.completions.create(
            model=os.environ.get("OPENAI_REMEDIATION_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        content = (response.choices[0].message.content or "").strip()
        if content.lower() == "null":
            return None
        # Intentar extraer JSON (por si el modelo envuelve en markdown)
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1]) if len(lines) > 2 else content
        return json.loads(content)
    except Exception as e:
        ctx.logger.warning("LLM remediation failed", {"error": str(e)})
        return None


async def handler(data: dict, ctx: FlowContext) -> None:
    """Procesa validation_error: State -> LLM -> schema_fixed o DLQ."""
    request_id = data.get("request_id", "")
    payload = data.get("payload", {})
    error_details = data.get("error_details", [])
    raw_envelope = data.get("raw_envelope", {})

    ctx.logger.info("Healing agent processing validation_error", {"request_id": request_id})

    sig = _error_signature(error_details)
    rule = await _get_repair_rule(ctx, sig)

    corrected: dict[str, Any] | None = None

    if rule:
        corrected = _apply_rule(payload, rule)
        ctx.logger.info("Applied cached repair rule", {"request_id": request_id, "rule_key": sig})
    else:
        corrected = await _call_llm_for_fix(payload, error_details, ctx)
        if corrected:
            # Detectar mapeo de campos para guardar como regla (ej. price -> amount)
            field_mapping = {}
            for err in error_details:
                loc = err.get("loc", [])
                if loc and isinstance(loc[0], str) and loc[0] in payload and loc[0] not in corrected:
                    for correct_key in ["amount", "email", "user_id", "currency", "description", "source"]:
                        if correct_key in corrected and correct_key not in payload:
                            field_mapping[loc[0]] = correct_key
                            break
            if field_mapping:
                await _set_repair_rule(ctx, sig, {"field_mapping": field_mapping})

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
