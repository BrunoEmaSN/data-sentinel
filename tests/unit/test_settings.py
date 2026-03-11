"""
Tests for configuration: loading sentinel-config.yaml and validation with Pydantic.
"""
import os
from pathlib import Path

import pytest

# pythonpath includes "src", so the module is "settings"
from settings import (
    SentinelSettings,
    StateConfig,
    HealingAgentConfig,
    load_settings,
    _load_yaml,
)


class TestStateConfig:
    def test_defaults(self):
        c = StateConfig()
        assert c.repair_rules_group == "sentinel"
        assert c.repair_rules_stream == "repair_rules"
        assert c.repair_rule_ttl_days == 7
        assert c.loader_processed_group == "loader"
        assert c.loader_processed_stream == "loader_processed"

    def test_custom_values(self):
        c = StateConfig(
            repair_rules_group="custom",
            repair_rule_ttl_days=14,
        )
        assert c.repair_rules_group == "custom"
        assert c.repair_rule_ttl_days == 14


class TestHealingAgentConfig:
    def test_default_target_fields(self):
        c = HealingAgentConfig()
        assert "amount" in c.target_fields
        assert "email" in c.target_fields

    def test_custom_target_fields(self):
        c = HealingAgentConfig(target_fields=["a", "b"])
        assert c.target_fields == ["a", "b"]


class TestSentinelSettings:
    def test_validate_empty_dict(self):
        s = SentinelSettings.model_validate({})
        assert s.state.repair_rules_group == "sentinel"
        assert s.healing_agent.openai_remediation_model == "gpt-4o-mini"

    def test_validate_partial_yaml(self):
        raw = {
            "state": {"repair_rule_ttl_days": 14},
            "healing_agent": {"temperature": 0.2},
        }
        s = SentinelSettings.model_validate(raw)
        assert s.state.repair_rule_ttl_days == 14
        assert s.healing_agent.temperature == 0.2
        assert s.state.repair_rules_stream == "repair_rules"


class TestLoadYaml:
    def test_nonexistent_returns_empty(self):
        assert _load_yaml(Path("/nonexistent/sentinel-config.yaml")) == {}

    def test_existing_project_config(self):
        # sentinel-config.yaml at project root
        root = Path(__file__).resolve().parent.parent.parent
        path = root / "sentinel-config.yaml"
        if path.exists():
            data = _load_yaml(path)
            assert isinstance(data, dict)
            assert "state" in data or data == {}  # may have state
            if data:
                s = SentinelSettings.model_validate(data)
                assert s.state.repair_rule_ttl_days >= 1


class TestLoadSettings:
    def test_load_settings_returns_instance(self):
        s = load_settings()
        assert isinstance(s, SentinelSettings)

    def test_env_override_repair_rule_ttl(self, monkeypatch):
        monkeypatch.setenv("REPAIR_RULE_TTL_DAYS", "21")
        s = load_settings()
        assert s.state.repair_rule_ttl_days == 21
        monkeypatch.delenv("REPAIR_RULE_TTL_DAYS", raising=False)

    def test_env_override_openai_model(self, monkeypatch):
        monkeypatch.setenv("OPENAI_REMEDIATION_MODEL", "gpt-4o")
        s = load_settings()
        assert s.healing_agent.openai_remediation_model == "gpt-4o"
        monkeypatch.delenv("OPENAI_REMEDIATION_MODEL", raising=False)
