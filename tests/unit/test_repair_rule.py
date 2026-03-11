"""
Tests for RepairRule and StoredRepairRule (Cache-Aside).
"""
from datetime import datetime, timedelta

import pytest

from contracts.v1.repair_rule import RepairRule, StoredRepairRule


class TestRepairRule:
    def test_rename_rule(self):
        r = RepairRule(source_field="price", target_field="amount", transformation_type="rename")
        assert r.source_field == "price"
        assert r.target_field == "amount"
        assert r.transformation_type == "rename"
        assert r.value_map is None

    def test_cast_rule(self):
        r = RepairRule(source_field="amount", target_field="amount", transformation_type="cast_to_float")
        assert r.transformation_type == "cast_to_float"

    def test_map_value_rule(self):
        r = RepairRule(
            source_field="active",
            target_field="active",
            transformation_type="map_value",
            value_map={"yes": True, "no": False},
        )
        assert r.value_map == {"yes": True, "no": False}


class TestStoredRepairRule:
    def test_with_expires_at(self):
        expires = datetime.utcnow() + timedelta(days=7)
        stored = StoredRepairRule(
            rules=[RepairRule(source_field="price", target_field="amount", transformation_type="rename")],
            expires_at=expires,
        )
        assert len(stored.rules) == 1
        assert stored.expires_at == expires

    def test_legacy_field_mapping(self):
        stored = StoredRepairRule(expires_at=datetime.utcnow(), field_mapping={"price": "amount"})
        assert stored.field_mapping == {"price": "amount"}
