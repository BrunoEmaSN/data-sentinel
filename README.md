<div align="center">
  <br />
    <a href="https://youtu.be/0fYi8SGA20k?feature=shared" target="_blank">
      <img width="1888" height="544" alt="banner" src="https://github.com/user-attachments/assets/6466e56c-3bc4-4152-900e-9ccb6fc55013" />
    </a>
  <br />

  <div>
    <img src="https://img.shields.io/badge/-Python-black?style=for-the-badge&color=0183f0" alt="python" />
    <img src="https://img.shields.io/badge/-Motia-black?style=for-the-badge&color=000000" alt="motia" />
    <img src="https://img.shields.io/badge/-Openai-black?style=for-the-badge&color=0ea47e" alt="open-ai" />
  </div>

  <h3 align="center">DATA SENTINEL</h3>
</div>

Event-driven pipeline with **Motia** that ingests raw data, validates against **Pydantic** contracts, auto-repairs with an AI agent (and rule cache), and loads to destination. Unrecoverable events go to a **Dead Letter Queue** for human inspection.


## Flows

<img width="1692" height="985" alt="image" src="https://github.com/user-attachments/assets/0cd10016-6318-45c5-b522-6d54aee5bbb4" />


- **Contracts**: `contracts/v1/` — versioned Pydantic schemas (BaseEvent, EventEnvelope, TransactionSchema, OrderEvent).
- **Envelope + Payload**: orders use `EventEnvelope` (envelope with `version`, `source`) + `OrderPayload`; the Validator can inspect the envelope before the payload.
- **Steps** (Motia): `src/*_step.py` — Ingestor, Validator, Healing Agent, Loader, DLQ, process_order_payment.
- **Cache-Aside (Memoization)**: The Validator first queries State (repair rules). If a known rule exists, it applies and re-validates; otherwise it emits `validation_error` and the Healing Agent calls the LLM. Solutions are persisted as `RepairRule` with TTL.
- **State**: Rules in Motia Stream (`repair_rules`); see `src/repair_state.py` (CacheProvider) and `contracts/v1/repair_rule.py` (RepairRule, StoredRepairRule).

## Requirements

- Python 3.10+
- [III Engine](https://iii.dev/) (Motia runtime)
- Optional: [uv](https://docs.astral.sh/uv/) to run the steps (recommended; the project uses `uv run` in `iii-config.yaml`)
- Optional: `OPENAI_API_KEY` for the Repair Agent to use the LLM (when no rule is in cache).

## Installation

### 1. Install the III runtime (Motia engine)

The III Engine is the runtime that executes Motia. Install it on your system:

```bash
curl -fsSL https://install.iii.dev/iii/main/install.sh | sh
```

Verify the installation:

```bash
iii -v
```

### 2. Project dependencies (Python)

Clone the repo (if applicable) and from the project root:

**With uv (recommended):**

```bash
uv sync
# With dev dependencies: uv sync --extra dev
```

**With pip and venv:**

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
# or: pip install motia pydantic openai pytest pytest-asyncio httpx python-dotenv
```

### 3. Environment variables (sensitive data in .env)

Sensitive keys and configuration go in a `.env` file at the project root (not committed to the repo).

1. Copy the template: `cp .env.example .env`
2. Edit `.env` and fill in the values (e.g. `OPENAI_API_KEY=sk-...`).
3. The Healing Agent (and the rest of the pipeline) load `.env` automatically on startup (`python-dotenv` + `src/config.py`).

See `.env.example` for the list of variables. The `.env` file is in `.gitignore`.

## Project structure

```
├── contracts/v1/          # Schema Registry (Pydantic)
│   ├── event.py           # BaseEvent, EventEnvelope (envelope with version)
│   ├── transaction.py     # TransactionSchema
│   ├── order.py           # OrderItem, OrderPayload, OrderEvent (Envelope+Payload)
│   ├── repair_rule.py     # RepairRule, StoredRepairRule (rules with TTL)
│   └── schema_factory.py  # Factory by version (OrderEvent v1/v2, Transaction)
├── .env.example            # Variable template (copy to .env; do not commit .env)
├── src/                    # Motia steps (auto-discovered)
│   ├── config.py           # Loads .env (sensitive data)
│   ├── repair_state.py     # CacheProvider: get/set rules, idempotent apply, TTL
│   ├── ingestor_step.py    # POST /ingest → raw_event
│   ├── validator_step.py  # raw_event → validated_data | schema_fixed (cache) | validation_error
│   ├── healing_agent_step.py  # validation_error → schema_fixed | DLQ
│   ├── loader_step.py     # validated_data + schema_fixed → DWH
│   ├── order_payment_step.py  # order_event → validated OrderEvent → order_payment_processed
│   └── dlq_step.py        # validation_unrecoverable → log
├── test_sentinel.py       # Contract breach simulation (CI/CD)
├── tests/
│   ├── unit/              # Pydantic models
│   ├── integration/      # Flow via API (requires server)
│   └── scenarios/         # Happy path, schema drift, data corruption
├── pyproject.toml
└── README.md
```

## Usage

### Start the backend (Motia/III)

From the project root, start the III engine with the repo config. This brings up the API, queues, state, and the process that runs the Motia steps (`src/*_step.py`):

```bash
iii -c iii-config.yaml
```

- The ingest endpoint is at **`POST http://localhost:3111/ingest`** (port defined in `iii-config.yaml`).
- Steps are auto-discovered from `src/`; the `ExecModule` runs `uv run motia run --dir src`. If you don't use uv, edit `iii-config.yaml` and change to `python -m motia run --dir src`.

### Start the Motia Workbench

The [Workbench](https://www.motia.dev/docs/concepts/workbench) is the visual console to view flows, logs, and test endpoints. With the backend already running (`iii -c iii-config.yaml`), in **another terminal** run:

```bash
iii-console --enable-flow
```

Then open in your browser:

- **Workbench:** [http://localhost:3113/](http://localhost:3113/)

There you can see the event graph (Flow View), logs for each step, and test ingest from the UI. Changes in `src/**/*.py` reload automatically thanks to the `ExecModule` watch mode.

**Flow View:** For the `data-sentinel` flow to appear in the Flow tab, this project patches the Motia runtime (the Python SDK does not send flow metadata to the engine; see [iii-hq/iii#1206](https://github.com/iii-hq/iii/issues/1206)). If the Flow view is empty or after a `uv sync` you no longer see the flow, run:

```bash
uv run python scripts/patch_motia_flow_metadata.py
```

### Envelope + Payload contract (orders)

For order events the **Envelope + Body** structure is used:

- **EventEnvelope** (`contracts/v1/event.py`): `event_id`, `timestamp`, `version`, `source`. The Validator can inspect `version` before parsing the payload (e.g. support v1 and v2 in parallel).
- **OrderEvent** (`contracts/v1/order.py`): extends the Envelope and adds `payload: OrderPayload` (order_id, customer_email, items, total_amount, currency). All order ingestion must validate with `OrderEvent`; on failure, tag as UNPROCESSED_DLQ.

In a step, validate at the input to avoid processing invalid data:

```python
from contracts.v1.order import OrderEvent

async def handler(event_data: dict, ctx: FlowContext) -> None:
    order = OrderEvent.model_validate(event_data)  # fails here if the contract is not met
    # ... use order.payload.order_id, order.payload.customer_email, etc.
```

The `process_order_payment` step listens to the `order_event` queue and performs this validation before processing.

### Test ingest

```bash
curl -X POST http://localhost:3111/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "source": "stripe",
    "amount": "99.99",
    "currency": "USD",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "description": "Test"
  }'
```

Add `event_id` and `timestamp` if your contract requires them in the body; otherwise the Validator can use those injected by the Ingestor in the envelope.

### Simulation: Contract breach (Data Sentinel in action)

To show the team the system's resilience, run the script that simulates malformed data:

```bash
python test_sentinel.py
```

The script sends an event with invalid `customer_email`; the **validation_gateway** rejects it, errors are captured with `e.errors()` (field and type), and the auto-repair flow is simulated. Ideal for CI/CD to verify that the Sentinel catches and labels failures correctly.

- **Isolation**: the gateway only answers "Does it meet the contract? Yes/No".
- **Error capture**: Pydantic error details feed the AI Agent for repair or DLQ.
- **Chaining**: the flow does not crash; it is diverted in a controlled way to repair or DLQ.

### Tests

```bash
# Unit + scenarios only (no server required)
pytest -m "not integration" -v

# With coverage
pytest -m "not integration" --cov=contracts -v

# Integration (Motia/III server running)
export SENTINEL_INGEST_URL=http://localhost:3111/ingest
pytest -m integration -v
```

Scenarios include **OrderEvent contract breach** (`test_sentinel_order_event_contract_rupture_invalid_email`); run them in CI to validate resilience.

## Test scenarios

| Scenario         | Description                    | Check                                                       |
|------------------|--------------------------------|-------------------------------------------------------------|
| **Happy path**   | Valid JSON                     | Ingestor → Validator → validated_data → Loader             |
| **Schema drift** | Renamed field (e.g. price→amount) | validation_error → Healing Agent → schema_fixed (or DLQ) |
| **Data corruption** | Invalid data (e.g. string in amount) | validation_error → DLQ if unrecoverable                 |

## AI Agent configuration

Put these variables in your `.env` (not in code):

- `OPENAI_API_KEY`: required for the Healing Agent to call the LLM when there is no rule in cache.
- `OPENAI_REMEDIATION_MODEL`: model to use (default `gpt-4o-mini`).

### Master prompt (zero hallucination)

The AI Step uses a **strict system prompt** focused on schemas and structural repairs only:

- **Zero Hallucination**: only structural repairs (rename keys, cast types, split strings). Never invent or fill business values.
- **Contract Adherence**: output must match the target JSON schema (Pydantic) passed to it.
- **Format**: the AI returns **valid JSON only**; no markdown, no prose. So the pipeline can call `json.loads()` directly.
- **Unrecoverable**: if repair is ambiguous or requires business logic (e.g. computing a missing total), the AI returns `{"reason": "..."}` and the Sentinel sends the event to DLQ instead of inventing data.

The prompt receives: `raw_payload`, `error_details` (from Pydantic), and `target_schema` (from `TransactionSchema.model_json_schema()`), so the model knows exactly what structure to return. Full definition in `src/healing_agent_step.py` (constant `MASTER_PROMPT`).

### Cache-Aside (Memoization) and learning cycle

**Look-up → Decide → Learn.** Calling the LLM for every event is unsustainable; State turns repair (slow/expensive) into in-memory read (fast/cheap).

1. **Look-up**: On validation failure, the Validator computes an error signature and queries State (`repair_rules`). If a rule exists and is not expired, it applies it.
2. **Decide**: If rule exists → apply (idempotent) and re-validate → emit `schema_fixed`. If not → emit `validation_error` to the Healing Agent.
3. **Learn**: When the AI repairs successfully, the Agent persists one or more `RepairRule` (source_field, target_field, transformation_type) in State with **TTL**. From then on, the same error is resolved in milliseconds without spending tokens.

**Best practices:**

- **TTL (Time To Live)**: Rules have `expires_at`. Environment variable `REPAIR_RULE_TTL_DAYS` (default 7). After expiry, the AI can re-evaluate (third-party APIs may have changed again).
- **Idempotency**: When applying a rule, if the target field already exists in the payload it is not overwritten. Do not apply the same transformation twice to the same object.
- **Separation of concerns**: The Validator orchestrates; it delegates to `repair_state` (CacheProvider) or the Healing Agent (AIProvider). Do not mix "known repair" logic with "discovery via AI".

## Observability

- **III Workbench**: Event graph and logs per step.
- **Feedback loop**: Periodically review the DLQ and Agent logs to adjust contracts in `contracts/v1` and repair rules.

## Production / portfolio improvements (senior suggestions)

- **Pipeline idempotency**: The Loader is idempotent: it uses the Envelope's `event_id` to check in State whether the event was already processed. On retries due to network failure, records are not duplicated in the DWH. State key: `loader_processed` by `event_id` (or `request_id` if no `event_id`).
- **Repaired JSON validation**: In the Healing Agent, the JSON returned by the AI is always re-validated against the target schema (`model_validate`) before emitting `schema_fixed`. If re-validation fails, it is logged and the event goes to DLQ; invalid data is not emitted.
- **Contract evolution (Schema Factory)**: The Envelope's `version` field allows supporting multiple contract versions. In `contracts/v1/schema_factory.py`: `get_order_event_model(version)` and `get_transaction_model(version)` return the correct class (e.g. `OrderEvent` for `"1.0.0"`; when adding `OrderEventV2` for `"2.0.0"`, register it in `ORDER_EVENT_REGISTRY` and the Validator/Healing Agent can instantiate the right class without changing pipeline logic).

## Engineering recommendations

- **DLQ (Dead Letter Queue)**: If the AI fails 3 times (or N as configured) to repair data, move that message to a "human errors" store or queue. Do not delete failed data; it allows auditing and contract improvement.
- **Structured logging**: Store logs in a format consumable by Datadog, ELK, or the Motia Workbench. Be able to filter by `status: "failed"` to see which sources are unstable.
- **Regression testing**: Every contract change (e.g. `OrderEvent`) should be accompanied by running `test_sentinel.py` and the scenarios with the previous JSON, to verify backward compatibility or plan migration.

## Deployment

- Deploy the project on the infrastructure where Motia/III runs (according to your CI/CD pipeline).
- Steps are discovered from `src/*_step.py`; no need to register them manually with the orchestrator.
- Configure queues and retries in III's `iii-config.yaml` if applicable.

## License

Apache-2.0 (or whatever you define for the repo).
