#!/usr/bin/env python3
"""
Simulation script: Contract Breach (Data Sentinel).

Run in CI/CD to verify the system is resilient:
  - The validation_gateway rejects data that does not meet the contract.
  - Errors are captured in detail (field, type) for the Repair Agent.
  - The flow is diverted in a controlled way to auto-repair (or DLQ).

Usage: python test_sentinel.py
"""
from datetime import datetime

from pydantic import ValidationError

from contracts.v1.order import OrderEvent


def validation_gateway(raw_data: dict) -> dict:
    """
    The gatekeeper that validates the contract.
    Single responsibility: Does it meet the contract? Yes/No.
    """
    try:
        event = OrderEvent.model_validate(raw_data)
        print(f"✅ [OK] Event {event.payload.order_id} validated successfully.")
        return {"status": "success", "data": event}
    except ValidationError as e:
        order_id = raw_data.get("payload", {}).get("order_id", "Unknown")
        print(f"❌ [ALERT] Schema breach in event: {order_id}")
        return {"status": "failed", "error": e.errors(), "order_id": order_id}


def ai_sentinel_repair(error_details: list, raw_data: dict) -> str:
    """
    Simulates AI intervention to repair the data.
    In production, the LLM analyzes error_details and suggests a fix.
    """
    print("🤖 [SENTINEL] Starting auto-repair protocol...")
    order_id = raw_data.get("payload", {}).get("order_id", "N/A")
    return f"REPAIR_SUGGESTED_FOR_{order_id}"


# --- TEST CASE: INVALID DATA (malformed email) ---
BAD_DATA = {
    "event_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": datetime.utcnow().isoformat(),
    "version": "1.0.0",
    "source": "ecommerce_api",
    "payload": {
        "order_id": "ORD-123",
        "customer_email": "this-is-not-an-email",  # <--- ERROR HERE
        "items": [{"sku": "PROD-1", "quantity": 1, "price": 10.5}],
        "total_amount": 10.5,
        "currency": "USD",
    },
}

# --- TEST CASE: VALID DATA (optional, for contrast) ---
GOOD_DATA = {
    "event_id": "550e8400-e29b-41d4-a716-446655440001",
    "timestamp": datetime.utcnow().isoformat(),
    "version": "1.0.0",
    "source": "ecommerce_api",
    "payload": {
        "order_id": "ORD-456",
        "customer_email": "customer@example.com",
        "items": [{"sku": "PROD-2", "quantity": 2, "price": 25.0}],
        "total_amount": 50.0,
        "currency": "EUR",
    },
}


def main() -> None:
    print("=== Data Sentinel: Contract Breach Simulation ===\n")

    # 1. Invalid case: must fail and trigger repair flow
    print("1. Sending malformed data (invalid email)...")
    result = validation_gateway(BAD_DATA)

    if result["status"] == "failed":
        repair_action = ai_sentinel_repair(result["error"], BAD_DATA)
        print(f"🔧 [REPAIR] {repair_action}")
        print("\nError details (for Agent/LLM):")
        for err in result["error"]:
            print(f"   - {err}")

    # 2. Valid case: must pass without alert
    print("\n2. Sending valid data...")
    validation_gateway(GOOD_DATA)

    print("\n=== End of simulation ===")


if __name__ == "__main__":
    main()
