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

- **Contratos**: `contracts/v1/` — esquemas Pydantic versionados (BaseEvent, EventEnvelope, TransactionSchema, OrderEvent).
- **Envelope + Payload**: órdenes usan `EventEnvelope` (sobre con `version`, `source`) + `OrderPayload`; el Validador puede inspeccionar el sobre antes del payload.
- **Steps** (Motia): `src/*_step.py` — Ingestor, Validador, Healing Agent, Loader, DLQ, process_order_payment.
- **Cache-Aside (Memoización)**: El Validador consulta primero el State (reglas de reparación). Si hay regla conocida, aplica y re-valida; si no, emite `validation_error` y el Healing Agent llama al LLM. Las soluciones se persisten como `RepairRule` con TTL.
- **State**: Reglas en Motia Stream (`repair_rules`); ver `src/repair_state.py` (CacheProvider) y `contracts/v1/repair_rule.py` (RepairRule, StoredRepairRule).

## Requisitos

- Python 3.10+
- [III Engine](https://iii.dev/) (runtime de Motia)
- Opcional: [uv](https://docs.astral.sh/uv/) para ejecutar los steps (recomendado; el proyecto usa `uv run` en `iii-config.yaml`)
- Opcional: `OPENAI_API_KEY` para que el Agente de reparación use el LLM (si no hay regla en cache).

## Instalación

### 1. Instalar el runtime III (Motor de Motia)

El III Engine es el runtime que ejecuta Motia. Instálalo en tu sistema:

```bash
curl -fsSL https://install.iii.dev/iii/main/install.sh | sh
```

Comprueba la instalación:

```bash
iii -v
```

### 2. Dependencias del proyecto (Python)

Clona el repo (si aplica) y, desde la raíz del proyecto:

**Con uv (recomendado):**

```bash
uv sync
# Con dependencias de desarrollo: uv sync --extra dev
```

**Con pip y venv:**

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
# o: pip install motia pydantic openai pytest pytest-asyncio httpx python-dotenv
```

### 3. Variables de entorno (datos sensibles en .env)

Las claves y configuraciones sensibles van en un archivo `.env` en la raíz del proyecto (no se sube al repo).

1. Copia la plantilla: `cp .env.example .env`
2. Edita `.env` y rellena los valores (p. ej. `OPENAI_API_KEY=sk-...`).
3. El Healing Agent (y el resto del pipeline) cargan `.env` automáticamente al arrancar (`python-dotenv` + `src/config.py`).

Ver `.env.example` para la lista de variables. El archivo `.env` está en `.gitignore`.

## Estructura del proyecto

```
├── contracts/v1/          # Schema Registry (Pydantic)
│   ├── event.py           # BaseEvent, EventEnvelope (sobre con version)
│   ├── transaction.py     # TransactionSchema
│   ├── order.py           # OrderItem, OrderPayload, OrderEvent (Envelope+Payload)
│   ├── repair_rule.py     # RepairRule, StoredRepairRule (reglas con TTL)
│   └── schema_factory.py  # Factory por versión (OrderEvent v1/v2, Transaction)
├── .env.example            # Plantilla de variables (copiar a .env, no subir .env)
├── src/                    # Steps Motia (auto-descubiertos)
│   ├── config.py           # Carga .env (datos sensibles)
│   ├── repair_state.py     # CacheProvider: get/set reglas, apply idempotente, TTL
│   ├── ingestor_step.py    # POST /ingest → raw_event
│   ├── validator_step.py  # raw_event → validated_data | schema_fixed (cache) | validation_error
│   ├── healing_agent_step.py  # validation_error → schema_fixed | DLQ
│   ├── loader_step.py     # validated_data + schema_fixed → DWH
│   ├── order_payment_step.py  # order_event → OrderEvent validado → order_payment_processed
│   └── dlq_step.py        # validation_unrecoverable → log
├── test_sentinel.py       # Simulación ruptura del contrato (CI/CD)
├── tests/
│   ├── unit/              # Modelos Pydantic
│   ├── integration/      # Flujo vía API (requiere servidor)
│   └── scenarios/         # Happy path, schema drift, data corruption
├── pyproject.toml
└── README.md
```

## Uso

### Levantar el backend (Motia/III)

Desde la raíz del proyecto, arranca el motor III con la configuración del repo. Esto levanta la API, colas, state y el proceso que ejecuta los steps de Motia (`src/*_step.py`):

```bash
iii -c iii-config.yaml
```

- El endpoint de ingest queda en **`POST http://localhost:3111/ingest`** (puerto definido en `iii-config.yaml`).
- Los steps se descubren automáticamente desde `src/`; el módulo `ExecModule` ejecuta `uv run motia run --dir src`. Si no usas uv, edita `iii-config.yaml` y cambia a `python -m motia run --dir src`.

### Levantar el Workbench de Motia

El [Workbench](https://www.motia.dev/docs/concepts/workbench) es la consola visual para ver flujos, logs y probar endpoints. Con el backend ya en marcha (`iii -c iii-config.yaml`), en **otra terminal** ejecuta:

```bash
iii-console --enable-flow
```

Luego abre en el navegador:

- **Workbench:** [http://localhost:3113/](http://localhost:3113/)

Ahí puedes ver el grafo de eventos (Flow View), logs de cada step y probar el ingest desde la interfaz. Los cambios en `src/**/*.py` recargan solos gracias al modo watch del `ExecModule`.

### Contrato Envelope + Payload (órdenes)

Para eventos de orden se usa la estructura **Sobre + Cuerpo**:

- **EventEnvelope** (`contracts/v1/event.py`): `event_id`, `timestamp`, `version`, `source`. El Validador puede inspeccionar `version` antes de parsear el payload (p. ej. soportar v1 y v2 en paralelo).
- **OrderEvent** (`contracts/v1/order.py`): hereda del Envelope y añade `payload: OrderPayload` (order_id, customer_email, items, total_amount, currency). Toda ingestión de órdenes debe validarse con `OrderEvent`; si falla, etiquetar como UNPROCESSED_DLQ.

En un step, validar en la entrada para no procesar datos inválidos:

```python
from contracts.v1.order import OrderEvent

async def handler(event_data: dict, ctx: FlowContext) -> None:
    order = OrderEvent.model_validate(event_data)  # falla aquí si el contrato no se cumple
    # ... usar order.payload.order_id, order.payload.customer_email, etc.
```

El step `process_order_payment` escucha la cola `order_event` y hace esta validación antes de procesar.

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

### Simulación: Ruptura del contrato (Data Sentinel en acción)

Para que el equipo vea la resiliencia del sistema, ejecutad el script que simula un dato malformado:

```bash
python test_sentinel.py
```

El script envía un evento con `customer_email` inválido; el **validation_gateway** lo rechaza, se capturan los errores con `e.errors()` (campo y tipo) y se simula el flujo de auto-reparación. Idóneo para ejecutar en CI/CD y verificar que el Sentinel atrapa y etiqueta los fallos correctamente.

- **Aislamiento**: el gateway solo responde "¿Cumple el contrato? Sí/No".
- **Captura de errores**: los detalles de Pydantic sirven al Agente de IA para reparar o enviar a DLQ.
- **Encadenamiento**: el flujo no cae; se desvía de forma controlada hacia reparación o DLQ.

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

Los escenarios incluyen **ruptura del contrato OrderEvent** (`test_sentinel_order_event_contract_rupture_invalid_email`); corredlos en CI para validar resiliencia.

## Escenarios de prueba

| Escenario        | Descripción                    | Comprobación                                              |
|------------------|--------------------------------|-----------------------------------------------------------|
| **Happy path**   | JSON válido                    | Ingestor → Validador → validated_data → Loader            |
| **Schema drift** | Campo renombrado (ej. price→amount) | validation_error → Healing Agent → schema_fixed (o DLQ) |
| **Data corruption** | Dato inválido (ej. string en amount) | validation_error → DLQ si irreparable                   |

## Configuración del Agente de IA

Pon estas variables en tu `.env` (no en el código):

- `OPENAI_API_KEY`: necesario para que el Healing Agent invoque el LLM cuando no haya regla en cache.
- `OPENAI_REMEDIATION_MODEL`: modelo a usar (por defecto `gpt-4o-mini`).

### Prompt maestro (zero hallucination)

El AI Step usa un **system prompt estricto** orientado a esquemas y solo a reparaciones estructurales:

- **Zero Hallucination**: solo reparaciones estructurales (renombrar claves, castear tipos, dividir strings). Nunca inventar ni rellenar valores de negocio.
- **Contract Adherence**: la salida debe coincidir con el JSON schema objetivo (Pydantic) que se le pasa.
- **Formato**: la IA devuelve **solo JSON válido**; sin markdown, sin prosa. Así el pipeline puede hacer `json.loads()` directamente.
- **Irreparable**: si la reparación es ambigua o requiere lógica de negocio (p. ej. calcular un total faltante), la IA devuelve `{"reason": "..."}` y el Sentinel envía el evento a DLQ en lugar de inventar datos.

El prompt recibe: `raw_payload`, `error_details` (de Pydantic) y `target_schema` (de `TransactionSchema.model_json_schema()`), de modo que el modelo sabe exactamente qué estructura debe devolver. Definición completa en `src/healing_agent_step.py` (constante `MASTER_PROMPT`).

### Cache-Aside (Memoización) y ciclo de aprendizaje

**Look-up → Decide → Learn.** Llamar al LLM por cada evento es insostenible; el State convierte reparación (lenta/cara) en lectura en memoria (rápida/barata).

1. **Look-up**: Al fallar la validación, el Validador calcula una firma del error y consulta el State (`repair_rules`). Si existe regla y no está expirada, aplica.
2. **Decide**: Si hay regla → aplicar (idempotente) y re-validar → emitir `schema_fixed`. Si no → emitir `validation_error` al Healing Agent.
3. **Learn**: Cuando la IA repara con éxito, el Agente persiste una o más `RepairRule` (source_field, target_field, transformation_type) en State con **TTL**. A partir de entonces, ese mismo error se resuelve en milisegundos sin gastar tokens.

**Buenas prácticas:**

- **TTL (Time To Live)**: Las reglas tienen `expires_at`. Variable de entorno `REPAIR_RULE_TTL_DAYS` (por defecto 7). Tras la expiración, la IA puede re-evaluar (las APIs de terceros pueden haber cambiado de nuevo).
- **Idempotencia**: Al aplicar una regla, si el campo destino ya existe en el payload no se sobrescribe. No aplicar dos veces la misma transformación al mismo objeto.
- **Separación de responsabilidades**: El Validador orquesta; delega a `repair_state` (CacheProvider) o al Healing Agent (AIProvider). No mezclar lógica de “reparación conocida” con “descubrimiento vía IA”.

## Observabilidad

- **Workbench III**: Grafo de eventos y logs de cada step.
- **Feedback loop**: Revisar periódicamente la DLQ y los logs del Agente para ajustar contratos en `contracts/v1` y reglas de reparación.

## Mejoras para producción / portafolio (sugerencias senior)

- **Idempotencia del pipeline**: El Loader es idempotente: usa el `event_id` del Envelope para comprobar en State si el evento ya fue procesado. En reintentos por fallo de red no se duplican registros en el DWH. Clave en State: `loader_processed` por `event_id` (o `request_id` si no hay `event_id`).
- **Validación del JSON reparado**: En el Healing Agent, el JSON devuelto por la IA se re-valida siempre con el esquema objetivo (`model_validate`) antes de emitir `schema_fixed`. Si la re-validación falla, se registra en log y el evento va a DLQ; no se emite dato inválido.
- **Evolución del contrato (Schema Factory)**: El campo `version` del Envelope permite soportar varias versiones del contrato. En `contracts/v1/schema_factory.py`: `get_order_event_model(version)` y `get_transaction_model(version)` devuelven la clase correcta (p. ej. `OrderEvent` para `"1.0.0"`; al añadir `OrderEventV2` para `"2.0.0"`, se registra en `ORDER_EVENT_REGISTRY` y el Validador/Healing Agent pueden instanciar la clase adecuada sin cambiar la lógica del pipeline).

## Recomendaciones para ingeniería

- **DLQ (Dead Letter Queue)**: Si la IA falla 3 veces (o N configurado) al reparar un dato, mover ese mensaje a una base o cola de "errores humanos". No borrar datos que fallaron; permiten auditoría y mejora de contratos.
- **Logging estructurado**: Guardar logs en formato legible por Datadog, ELK o el Workbench de Motia. Poder filtrar por `status: "failed"` para ver qué fuentes son inestables.
- **Testing de regresión**: Cada cambio en el contrato (p. ej. `OrderEvent`) debe ir acompañado de la ejecución de `test_sentinel.py` y de los escenarios con el JSON anterior, para comprobar retrocompatibilidad o planificar la migración.

## Despliegue

- Despliega el proyecto en la infraestructura donde corre Motia/III (según tu pipeline CI/CD).
- Los steps se descubren desde `src/*_step.py`; no es necesario registrar manualmente el orquestador.
- Configura colas y reintentos en el `iii-config.yaml` de III si aplica.

## Licencia

Apache-2.0 (o la que definas para el repo).
