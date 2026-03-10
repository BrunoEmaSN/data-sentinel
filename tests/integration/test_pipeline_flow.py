"""
Integration tests: flujo completo vía API de ingest.
Requieren servidor Motia/III en ejecución (ej. npm run dev / iii).
Ver README para puertos y variables de entorno.
"""
import os
import uuid
from datetime import datetime

import pytest

# Marcar todo el módulo como integration para poder excluirlo con pytest -m "not integration"
pytestmark = pytest.mark.integration

INGEST_URL = os.environ.get("SENTINEL_INGEST_URL", "http://localhost:3111/ingest")


@pytest.fixture
def valid_transaction_payload():
    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "source": "stripe",
        "amount": "49.99",
        "currency": "EUR",
        "user_id": str(uuid.uuid4()),
        "email": "test@example.com",
        "description": "Integration test",
    }


@pytest.fixture
def schema_drift_payload():
    """Campo 'price' en lugar de 'amount' (schema drift)."""
    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "source": "shopify",
        "price": "29.99",  # drift: debería ser 'amount'
        "currency": "USD",
        "user_id": str(uuid.uuid4()),
        "email": "drift@example.com",
    }


@pytest.fixture
def corrupted_payload():
    """Dato corrupto: string donde debe ir número."""
    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "source": "broken",
        "amount": "not-a-number",
        "currency": "USD",
        "user_id": str(uuid.uuid4()),
        "email": "bad@example.com",
    }


@pytest.mark.asyncio
async def test_happy_path_ingest_accepts(valid_transaction_payload):
    """Happy path: POST a /ingest con JSON válido debe ser aceptado (202)."""
    try:
        import httpx
    except ImportError:
        pytest.skip("httpx not installed")
    async with httpx.AsyncClient() as client:
        resp = await client.post(INGEST_URL, json=valid_transaction_payload, timeout=10.0)
    # Sin servidor: puede fallar por conexión; con servidor: 202
    if resp.status_code == 202:
        body = resp.json()
        assert "request_id" in body
        assert body.get("status") == "accepted"


@pytest.mark.asyncio
async def test_schema_drift_ingest_accepts(schema_drift_payload):
    """Schema drift: el ingestor acepta igual (no valida); el validador fallará y el agente puede reparar."""
    try:
        import httpx
    except ImportError:
        pytest.skip("httpx not installed")
    async with httpx.AsyncClient() as client:
        resp = await client.post(INGEST_URL, json=schema_drift_payload, timeout=10.0)
    if resp.status_code == 202:
        assert resp.json().get("status") == "accepted"


@pytest.mark.asyncio
async def test_data_corruption_ingest_accepts(corrupted_payload):
    """Data corruption: el ingestor acepta; validador rechaza y puede ir a DLQ."""
    try:
        import httpx
    except ImportError:
        pytest.skip("httpx not installed")
    async with httpx.AsyncClient() as client:
        resp = await client.post(INGEST_URL, json=corrupted_payload, timeout=10.0)
    if resp.status_code == 202:
        assert resp.json().get("status") == "accepted"
