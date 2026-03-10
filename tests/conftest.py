"""
Pytest configuration: asyncio mode and integration marker.
"""
import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: marks tests that require Motia/III server (deselect with -m 'not integration')")
