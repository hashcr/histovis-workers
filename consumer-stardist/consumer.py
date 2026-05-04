import logging

from consumer_common.broker import start_consuming
from settings import settings
from consumer_common.registry import load_handlers

logger = logging.getLogger(__name__)

registry: dict = {}

async def start_consumer() -> None:
    global registry
    registry = load_handlers()
    await start_consuming(settings, registry)





