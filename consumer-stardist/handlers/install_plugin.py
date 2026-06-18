import logging
import shutil
from pathlib import Path

import yaml
from pydantic import ValidationError

import consumer
from consumer_common.http_client import update_plugin_status
from consumer_common.models import InstallPluginMessage
from consumer_common.registry import load_handlers

from settings import settings

logger = logging.getLogger(__name__)

_HANDLERS_DIR = Path(__file__).parent
_HANDLERS_YAML = Path(__file__).parent.parent / "handlers.yaml"


async def handle_install(body: dict) -> None:
    try:
        message = InstallPluginMessage(**body)
    except ValidationError as e:
        logger.error("Invalid InstallPluginMessage | error=%s", e)
        return

    plugin_code = message.pluginCode
    src = Path(message.localScriptPath)
    dest = _HANDLERS_DIR / f"{plugin_code}.py"

    try:
        shutil.move(str(src), str(dest))
        logger.info("Moved plugin script | from=%s | to=%s", src, dest)

        with open(_HANDLERS_YAML, "r") as f:
            config = yaml.safe_load(f) or {"handlers": {}}
        config["handlers"][plugin_code] = f"handlers.{plugin_code}.handle"
        with open(_HANDLERS_YAML, "w") as f:
            yaml.dump(config, f, default_flow_style=False)
        logger.info("Updated handlers.yaml | plugin_code=%s", plugin_code)

        consumer.registry.clear()
        consumer.registry.update(load_handlers())
        logger.info("Handler registry reloaded | plugin_code=%s now active", plugin_code)

        await update_plugin_status(settings.analysis_service_url, message.plugin_id, "INSTALLED")
        logger.info("Plugin installed | plugin_id=%s | plugin_code=%s", message.plugin_id, plugin_code)

    except Exception as e:
        logger.error("install_plugin failed | plugin_id=%s | error=%s", message.plugin_id, e)
        await update_plugin_status(settings.analysis_service_url, message.plugin_id, "FAILED")
        raise
