import logging
import shutil
from pathlib import Path

from pydantic import ValidationError

import consumer
from consumer_common.http_client import update_plugin_status
from consumer_common.models import InstallPluginMessage
from consumer_common.registry import load_handlers, load_dynamic_handlers

from settings import settings

logger = logging.getLogger(__name__)


async def handle_install(body: dict) -> None:
    try:
        message = InstallPluginMessage(**body)
    except ValidationError as e:
        logger.error("Invalid InstallPluginMessage | error=%s", e)
        return

    plugin_code = message.pluginCode
    src = Path(message.localScriptPath)
    dest = Path(settings.plugins_installed_dir) / f"{plugin_code}.py"

    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        logger.info("Moved plugin script | from=%s | to=%s", src, dest)

        consumer.registry.clear()
        consumer.registry.update(load_handlers())
        consumer.registry.update(load_dynamic_handlers(settings.plugins_installed_dir))
        logger.info("Handler registry reloaded | plugin_code=%s now active", plugin_code)

        await update_plugin_status(settings.analysis_service_url, message.plugin_id, "INSTALLED")
        logger.info("Plugin installed | plugin_id=%s | plugin_code=%s", message.plugin_id, plugin_code)

    except Exception as e:
        logger.error("install_plugin failed | plugin_id=%s | error=%s", message.plugin_id, e)
        await update_plugin_status(settings.analysis_service_url, message.plugin_id, "FAILED")
        raise
