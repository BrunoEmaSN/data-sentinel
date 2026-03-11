"""
Cache-Aside: state provider for repair rules.

Separation of concerns: the Validator and Healing Agent use this
module as CacheProvider (State). Do not mix "known repair" logic
with "discovery via AI"; the Validator orchestrates and delegates here.
"""
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from contracts.v1.repair_rule import RepairRule, StoredRepairRule

from settings import settings

# Keys for State (Motia Stream) — from configuration
REPAIR_RULES_GROUP = settings.state.repair_rules_group
REPAIR_RULES_STREAM = settings.state.repair_rules_stream
DEFAULT_TTL_DAYS = settings.state.repair_rule_ttl_days


def error_signature(error_details: list[dict]) -> str:
    """Key derived from error type for rule cache (same error -> same rule)."""
    parts = []
    for err in error_details:
        loc = err.get("loc", [])
        typ = err.get("type", "")
        parts.append(f"{':'.join(str(x) for x in loc)}:{typ}")
    raw = "|".join(sorted(parts))
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def apply_rule_idempotent(payload: dict, stored: dict) -> dict:
    """
    Applies the stored rule to the payload idempotently.
    Does not apply twice: if target_field already exists, does not overwrite (avoids garbage).
    """
    out = dict(payload)

    # New format: rules + expires_at
    rules = stored.get("rules")
    if rules:
        for r in rules:
            rule = r if isinstance(r, RepairRule) else RepairRule.model_validate(r)
            _apply_single_rule_idempotent(out, rule)
        return out

    # Legacy: field_mapping
    field_mapping = stored.get("field_mapping") or {}
    for wrong_key, correct_key in field_mapping.items():
        if wrong_key in out and correct_key not in out:
            out[correct_key] = out.pop(wrong_key)
    return out


def _apply_single_rule_idempotent(payload: dict, rule: RepairRule) -> None:
    """Applies a RepairRule idempotently (modifies payload in-place)."""
    src = rule.source_field
    tgt = rule.target_field
    if src not in payload:
        return
    # Idempotency: if target already exists and differs from source, do not overwrite
    if tgt in payload and tgt != src:
        return

    value = payload[src]
    if rule.transformation_type == "rename":
        if tgt not in payload:
            payload[tgt] = payload.pop(src)
    elif rule.transformation_type == "cast_to_float":
        if isinstance(value, str):
            try:
                payload[src] = float(value)
                if tgt != src:
                    payload[tgt] = payload.pop(src)
            except (ValueError, TypeError):
                pass
    elif rule.transformation_type == "cast_to_int":
        if isinstance(value, str):
            try:
                payload[src] = int(value)
                if tgt != src:
                    payload[tgt] = payload.pop(src)
            except (ValueError, TypeError):
                pass
    elif rule.transformation_type == "map_value" and rule.value_map is not None:
        payload[tgt] = rule.value_map.get(value, value)
        if tgt != src:
            del payload[src]
    else:
        if tgt not in payload:
            payload[tgt] = payload.pop(src)


def is_rule_expired(stored: dict) -> bool:
    """True if the rule has expires_at and the date has passed."""
    exp = stored.get("expires_at")
    if exp is None:
        return False
    if isinstance(exp, str):
        try:
            exp = datetime.fromisoformat(exp.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return True
    now = datetime.now(timezone.utc)
    exp_utc = exp.astimezone(timezone.utc) if getattr(exp, "tzinfo", None) else exp
    return now >= exp_utc


def build_stored_rule(rules: list[RepairRule] | list[dict], ttl_days: int = DEFAULT_TTL_DAYS) -> dict:
    """Builds the dict to persist in State (with expires_at)."""
    now = datetime.utcnow()
    expires_at = now + timedelta(days=ttl_days)
    rule_list = [r.model_dump() if isinstance(r, RepairRule) else r for r in rules]
    return {"rules": rule_list, "expires_at": expires_at.isoformat()}


async def get_repair_rule(ctx: Any, key: str) -> dict | None:
    """Gets rule from State; returns None if it does not exist or is expired."""
    try:
        from motia import Stream
        stream = Stream[dict](REPAIR_RULES_STREAM)
        rule = await stream.get(REPAIR_RULES_GROUP, key)
        if rule and is_rule_expired(rule):
            return None
        return rule
    except Exception:
        return None


async def set_repair_rule(ctx: Any, key: str, rule: dict, ttl_days: int | None = None) -> None:
    """Saves rule in State with TTL. If rule already has expires_at, it is respected; otherwise ttl_days is used."""
    ttl = ttl_days if ttl_days is not None else DEFAULT_TTL_DAYS
    if "expires_at" not in rule:
        now = datetime.utcnow()
        rule = dict(rule)
        rule["expires_at"] = (now + timedelta(days=ttl)).isoformat()
    try:
        from motia import Stream
        stream = Stream[dict](REPAIR_RULES_STREAM)
        await stream.set(REPAIR_RULES_GROUP, key, rule)
    except Exception as e:
        if hasattr(ctx, "logger"):
            ctx.logger.warning("Could not persist repair rule", {"key": key, "error": str(e)})
