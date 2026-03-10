"""
Pytest configuration: asyncio mode and integration marker.
Carga .env desde la raíz del proyecto para tests (p. ej. SENTINEL_INGEST_URL).
"""
from pathlib import Path

import pytest

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: marks tests that require Motia/III server (deselect with -m 'not integration')")
