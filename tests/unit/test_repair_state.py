"""
Tests for repair_state: apply_rule_idempotent, is_rule_expired, error_signature.
"""
from datetime import datetime, timezone, timedelta

import pytest

from contracts.v1.repair_rule import RepairRule
from repair_state import (
    apply_rule_idempotent,
    build_stored_rule,
    error_signature,
    is_rule_expired,
)


class TestErrorSignature:
    def test_same_errors_same_signature(self):
        errs = [{"loc": ("amount",), "type": "missing"}]
        assert error_signature(errs) == error_signature(errs)

    def test_different_errors_different_signature(self):
        a = error_signature([{"loc": ("amount",), "type": "missing"}])
        b = error_signature([{"loc": ("email",), "type": "value_error"}])
        assert a != b


class TestApplyRuleIdempotent:
    def test_rename_legacy_field_mapping(self):
        payload = {"price": "99.99", "currency": "USD"}
        rule = {"field_mapping": {"price": "amount"}}
        out = apply_rule_idempotent(payload, rule)
        assert out == {"amount": "99.99", "currency": "USD"}

    def test_idempotent_dest_already_exists(self):
        payload = {"price": "10", "amount": 20}
        rule = {"field_mapping": {"price": "amount"}}
        out = apply_rule_idempotent(payload, rule)
        # Do not overwrite existing amount
        assert out.get("amount") == 20
        assert "price" in out  # rename not applied so we don't overwrite

    def test_rules_format_rename(self):
        payload = {"user_email": "a@b.com"}
        rule = {
            "rules": [
                {"source_field": "user_email", "target_field": "email", "transformation_type": "rename"}
            ],
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        }
        out = apply_rule_idempotent(payload, rule)
        assert out == {"email": "a@b.com"}


class TestIsRuleExpired:
    def test_no_expires_at_not_expired(self):
        assert is_rule_expired({"field_mapping": {"x": "y"}}) is False

    def test_future_expires_at_not_expired(self):
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        assert is_rule_expired({"expires_at": future}) is False

    def test_past_expires_at_expired(self):
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        assert is_rule_expired({"expires_at": past}) is True


class TestBuildStoredRule:
    def test_includes_expires_at(self):
        rules = [RepairRule(source_field="price", target_field="amount", transformation_type="rename")]
        stored = build_stored_rule(rules, ttl_days=7)
        assert "expires_at" in stored
        assert "rules" in stored
        assert len(stored["rules"]) == 1
