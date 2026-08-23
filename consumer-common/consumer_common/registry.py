import importlib
import logging
from pathlib import Path
from collections.abc import Callable

import yaml

logger = logging.getLogger(__name__)


def load_dynamic_handlers(plugins_dir: str) -> dict[str, Callable]:
    path = Path(plugins_dir)
    if not path.exists():
        return {}
    handlers = {}
    for py_file in sorted(path.glob("*.py")):
        plugin_code = py_file.stem
        try:
            module = importlib.import_module(plugin_code)
            handlers[plugin_code] = getattr(module, "handle")
            logger.info("Registered dynamic handler | plugin_code=%s", plugin_code)
        except (ImportError, AttributeError) as e:
            logger.error("Failed to load dynamic handler | plugin_code=%s | error=%s", plugin_code, e)
    return handlers


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