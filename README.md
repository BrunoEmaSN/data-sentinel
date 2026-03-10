# Self-Healing Data Sentinel (Motia + EDA/DDD)

Pipeline orientado a eventos con **Motia** que ingesta datos crudos, valida contra contratos **Pydantic**, repara automáticamente con un agente de IA (y cache de reglas) y carga en destino. Los eventos irreparables van a una **Dead Letter Queue** para inspección humana.

## Arquitectura

```
Ingestor (API)  →  raw_event  →  Validador  →  validated_data  →  Loader
                                    ↓
                            validation_error  →  Healing Agent  →  schema_fixed  →  Loader
                                    ↓                                    ↓
                            validation_unrecoverable  →  DLQ
```

- **Contratos**: `contracts/v1/` — esquemas Pydantic versionados (BaseEvent, TransactionSchema).
- **Steps** (Motia): `src/*_step.py` — Ingestor, Validador, Healing Agent, Loader, DLQ.
- **State**: El Healing Agent usa reglas de reparación cacheadas (Motia Stream) para no llamar al LLM en errores ya conocidos.

## Requisitos

- Python 3.10+
- [III Engine](https://iii.dev/) (runtime de Motia)
- Opcional: `OPENAI_API_KEY` para que el Agente de reparación use el LLM (si no hay regla en cache).

## Instalación

```bash
# Entorno virtual
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Dependencias
pip install -e ".[dev]"
# o: pip install motia pydantic openai pytest pytest-asyncio httpx
```

## Estructura del proyecto

```
├── contracts/v1/          # Schema Registry (Pydantic)
│   ├── event.py           # BaseEvent
│   └── transaction.py     # TransactionSchema
├── src/                   # Steps Motia (auto-descubiertos)
│   ├── ingestor_step.py   # POST /ingest → raw_event
│   ├── validator_step.py  # raw_event → validated_data | validation_error
│   ├── healing_agent_step.py  # validation_error → schema_fixed | DLQ
│   ├── loader_step.py     # validated_data + schema_fixed → DWH
│   └── dlq_step.py        # validation_unrecoverable → log
├── tests/
│   ├── unit/              # Modelos Pydantic
│   ├── integration/      # Flujo vía API (requiere servidor)
│   └── scenarios/         # Happy path, schema drift, data corruption
├── pyproject.toml
└── README.md
```

## Uso

### Ejecutar con Motia/III

1. Instala el runtime III: `curl -fsSL https://install.iii.dev/iii/main/install.sh | sh`
2. Desde la raíz del proyecto (donde Motia espera `src/`), arranca el servidor según la guía de [Motia](https://motia.dev/docs/getting-started/quick-start) (por ejemplo `npx motia@latest create` en un proyecto Node que referencie este código, o el comando que use tu equipo para Python).
3. El endpoint de ingest será algo como `POST http://localhost:3111/ingest` (puerto según tu `config.yaml` de III).

### Probar el ingest

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

Añade `event_id` y `timestamp` si tu contrato los exige en el body; si no, el Validador puede usar los que inyecte el Ingestor en el sobre.

### Tests

```bash
# Solo unit + escenarios (no requieren servidor)
pytest -m "not integration" -v

# Con cobertura
pytest -m "not integration" --cov=contracts -v

# Integración (servidor Motia/III en marcha)
export SENTINEL_INGEST_URL=http://localhost:3111/ingest
pytest -m integration -v
```

## Escenarios de prueba

| Escenario        | Descripción                    | Comprobación                                              |
|------------------|--------------------------------|-----------------------------------------------------------|
| **Happy path**   | JSON válido                    | Ingestor → Validador → validated_data → Loader            |
| **Schema drift** | Campo renombrado (ej. price→amount) | validation_error → Healing Agent → schema_fixed (o DLQ) |
| **Data corruption** | Dato inválido (ej. string en amount) | validation_error → DLQ si irreparable                   |

## Configuración del Agente de IA

- `OPENAI_API_KEY`: necesario para que el Healing Agent invoque el LLM cuando no haya regla en cache.
- `OPENAI_REMEDIATION_MODEL`: modelo a usar (por defecto `gpt-4o-mini`).

## Observabilidad

- **Workbench III**: Grafo de eventos y logs de cada step.
- **Feedback loop**: Revisar periódicamente la DLQ y los logs del Agente para ajustar contratos en `contracts/v1` y reglas de reparación.

## Despliegue

- Despliega el proyecto en la infraestructura donde corre Motia/III (según tu pipeline CI/CD).
- Los steps se descubren desde `src/*_step.py`; no es necesario registrar manualmente el orquestador.
- Configura colas y reintentos en el `config.yaml` de III si aplica.

## Licencia

Apache-2.0 (o la que definas para el repo).
