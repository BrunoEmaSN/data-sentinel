"""
Load and validate configuration from sentinel-config.yaml and environment variables.

Secrets (OPENAI_API_KEY, etc.) are read from .env; the rest of the behaviour
is defined in the YAML. When this module is imported, config is validated and `settings` is exposed.
"""
from pathlib import Path

from pydantic import BaseModel, Field

# Load .env before reading os.environ (same as config.py)
try:
    from dotenv import load_dotenv
    for parent in [Path(__file__).resolve().parent.parent, Path.cwd()]:
        env_file = parent / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            break
    else:
        load_dotenv()
except ImportError:
    pass


class StateConfig(BaseModel):
    """State/Stream: group and stream names for repair rules and loader."""
    repair_rules_group: str = Field(default="sentinel", description="State group for repair rules")
    repair_rules_stream: str = Field(default="repair_rules", description="State stream for repair rules")
    repair_rule_ttl_days: int = Field(default=7, ge=1, le=365, description="TTL in days for cached rules")
    loader_processed_group: str = Field(default="loader", description="Group for loader idempotency")
    loader_processed_stream: str = Field(default="loader_processed", description="Stream for already-loaded events")


class HealingAgentConfig(BaseModel):
    """Healing Agent: LLM model, temperature and target schema fields."""
    openai_remediation_model: str = Field(default="gpt-4o-mini", description="OpenAI model for remediation")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0, description="LLM temperature")
    target_fields: list[str] = Field(
        default_factory=lambda: ["amount", "email", "user_id", "currency", "description", "source"],
        description="Valid schema fields used to infer rename rules",
    )


class SentinelSettings(BaseModel):
    """Main Sentinel configuration (YAML + overrides from env)."""
    state: StateConfig = Field(default_factory=StateConfig)
    healing_agent: HealingAgentConfig = Field(default_factory=HealingAgentConfig)

    @property
    def openai_api_key(self) -> str:
        """Secret: always read from environment variable."""
        import os
        return (os.environ.get("OPENAI_API_KEY") or "").strip()


def _find_config_path() -> Path:
    """Path to sentinel-config.yaml: SENTINEL_CONFIG_PATH or search from project root."""
    import os
    explicit = os.environ.get("SENTINEL_CONFIG_PATH")
    if explicit:
        p = Path(explicit)
        if p.exists():
            return p
    for parent in [Path(__file__).resolve().parent.parent, Path.cwd()]:
        candidate = parent / "sentinel-config.yaml"
        if candidate.exists():
            return candidate
    return parent / "sentinel-config.yaml"  # may not exist; defaults are used


def _load_yaml(path: Path) -> dict:
    """Load YAML; returns {} if the file does not exist or is empty."""
    if not path.exists():
        return {}
    import yaml
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def load_settings() -> SentinelSettings:
    """Load .env (already done on import), read YAML and validate. Some values can be overridden by env."""
    import os
    path = _find_config_path()
    raw = _load_yaml(path)
    s = SentinelSettings.model_validate(raw)
    # Overrides from environment variables (optional)
    if "REPAIR_RULE_TTL_DAYS" in os.environ:
        try:
            s.state.repair_rule_ttl_days = int(os.environ["REPAIR_RULE_TTL_DAYS"])
        except ValueError:
            pass
    if "OPENAI_REMEDIATION_MODEL" in os.environ:
        s.healing_agent.openai_remediation_model = os.environ["OPENAI_REMEDIATION_MODEL"].strip()
    return s


# Global instance validated when the module is imported
settings = load_settings()
