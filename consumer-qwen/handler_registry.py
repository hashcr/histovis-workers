import importlib
import logging
from pathlib import Path
from typing import Callable

import yaml

logger = logging.getLogger(__name__)

def load_handlers(config_path: str = "handlers.yaml") -> dict[str, Callable]:
    path = Path(config_path)

    if not path.exists():
        logger.warning(f"handlers.yaml not found at %s - no handlers loaded", config_path)
        return {}

    with open(path, "r") as f:
        config = yaml.safe_load(f)

    handlers = {}

    for plugin_code, dotted_path in config.get("handlers", {}).items():
        try:
            module_path, function_name = dotted_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            handler = getattr(module, function_name)
            handlers[plugin_code] = handler
            logger.info("Registered handler | plugin_code = %s | function = %s", plugin_code, dotted_path)
        except (ImportError, AttributeError) as e:
            logger.error("Failed to load handler | plugin_code = %s | function = %s", plugin_code, dotted_path)

    logger.info("Handler registry loaded - %d handler(s) registered", len(handlers))
    return handlers