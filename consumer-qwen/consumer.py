import logging

from consumer_common.broker import start_consuming
from settings import settings
from consumer_common.registry import load_handlers, load_dynamic_handlers

logger = logging.getLogger(__name__)

registry: dict = {}

async def start_consumer() -> None:
    global registry
    registry = load_handlers()
    registry.update(load_dynamic_handlers(settings.plugins_installed_dir))
    await start_consuming(settings, registry)





