#!/usr/bin/env python3
"""
Patches the Motia runtime so register_function receives metadata (flows, filePath).

Without this patch, the iii-console Flow view does not show flows defined in Python
(see https://github.com/iii-hq/iii/issues/1206). The III SDK already accepts metadata;
Motia was not passing it.

Run after uv sync if the Flow view is empty again:
  uv run python scripts/patch_motia_flow_metadata.py
"""
from pathlib import Path

import motia

# runtime.py is next to the motia package __init__.py
runtime_path = Path(motia.__file__).parent / "runtime.py"
if not runtime_path.exists():
    raise SystemExit(f"Not found: {runtime_path}")

text = runtime_path.read_text(encoding="utf-8")

# The 5 replacements that send metadata when registering functions (api, queue, cron, state, stream)
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
    print("Patch applied: flow metadata will be sent to the III engine.")
else:
    if all(new in text for _, new in replacements):
        print("Motia is already patched (metadata in register_function).")
    else:
        raise SystemExit("Could not apply patch; Motia version may have changed.")
