#!/usr/bin/env python3
"""
Parchea el runtime de Motia para que register_function reciba metadata (flows, filePath).

Sin este parche, la vista Flow del iii-console no muestra flujos definidos en Python
(ver https://github.com/iii-hq/iii/issues/1206). El SDK de III ya acepta metadata;
Motia no lo estaba pasando.

Ejecutar después de uv sync si la vista Flow vuelve a estar vacía:
  uv run python scripts/patch_motia_flow_metadata.py
"""
from pathlib import Path

import motia

# runtime.py está junto a __init__.py del paquete motia
runtime_path = Path(motia.__file__).parent / "runtime.py"
if not runtime_path.exists():
    raise SystemExit(f"No se encontró {runtime_path}")

text = runtime_path.read_text(encoding="utf-8")

# Los 5 reemplazos que envían metadata al registrar funciones (api, queue, cron, state, stream)
replacements = [
    (
        "get_instance().register_function(function_id, api_handler)\n\n        api_path",
        "get_instance().register_function(function_id, api_handler, metadata=metadata)\n\n        api_path",
    ),
    (
        "get_instance().register_function(function_id, queue_handler)\n\n        trigger_config",
        "get_instance().register_function(function_id, queue_handler, metadata=metadata)\n\n        trigger_config",
    ),
    (
        "get_instance().register_function(function_id, cron_handler)\n\n        trigger_config",
        "get_instance().register_function(function_id, cron_handler, metadata=metadata)\n\n        trigger_config",
    ),
    (
        "get_instance().register_function(function_id, state_handler)\n\n        trigger_config",
        "get_instance().register_function(function_id, state_handler, metadata=metadata)\n\n        trigger_config",
    ),
    (
        "get_instance().register_function(function_id, stream_handler)\n\n        trigger_config",
        "get_instance().register_function(function_id, stream_handler, metadata=metadata)\n\n        trigger_config",
    ),
]

changed = False
for old, new in replacements:
    if old in text and new not in text:
        text = text.replace(old, new)
        changed = True

if changed:
    runtime_path.write_text(text, encoding="utf-8")
    print("Parche aplicado: metadata de flows se enviará al motor III.")
else:
    if all(new in text for _, new in replacements):
        print("Motia ya está parcheado (metadata en register_function).")
    else:
        raise SystemExit("No se pudo aplicar el parche; puede que la versión de Motia haya cambiado.")
