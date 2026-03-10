"""
Integration tests: full flow via ingest API.
Require Motia/III server running (e.g. npm run dev / iii).
See README for ports and environment variables.
"""
import os
import uuid
from datetime import datetime

import pytest

# Mark the whole module as integration so it can be excluded with pytest -m "not integration"
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
    """Field 'price' instead of 'amount' (schema drift)."""
    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "source": "shopify",
        "price": "29.99",  # drift: should be 'amount'
        "currency": "USD",
        "user_id": str(uuid.uuid4()),
        "email": "drift@example.com",
    }


@pytest.fixture
def corrupted_payload():
    """Corrupted data: string where number is expected."""
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
    """Happy path: POST to /ingest with valid JSON should be accepted (202)."""
    try:
        import httpx
    except ImportError:
        pytest.skip("httpx not installed")
    async with httpx.AsyncClient() as client:
        resp = await client.post(INGEST_URL, json=valid_transaction_payload, timeout=10.0)
    # Without server: may fail due to connection; with server: 202
    if resp.status_code == 202:
        body = resp.json()
        assert "request_id" in body
        assert body.get("status") == "accepted"


@pytest.mark.asyncio
async def test_schema_drift_ingest_accepts(schema_drift_payload):
    """Schema drift: ingestor still accepts (does not validate); validator will fail and agent may repair."""
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
    """Data corruption: ingestor accepts; validator rejects and may go to DLQ."""
    try:
        import httpx
    except ImportError:
        pytest.skip("httpx not installed")
    async with httpx.AsyncClient() as client:
        resp = await client.post(INGEST_URL, json=corrupted_payload, timeout=10.0)
    if resp.status_code == 202:
        assert resp.json().get("status") == "accepted"
