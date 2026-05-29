import asyncio
import json
import logging
from pathlib import Path

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

from consumer_common.exceptions import JobProcessingError
from image_service import update_image_urls
from image_utils import download_slide, upload_thumbnail
from models import ImageProcessMessage
from settings import settings
from slides import register_slide

logger = logging.getLogger(__name__)


def _parse(message: AbstractIncomingMessage) -> ImageProcessMessage | None:
    try:
        body = json.loads(message.body)
        return ImageProcessMessage(**body)
    except Exception as e:
        logger.error("Invalid message body: %s", e)
        return None


async def _register(image_id: str) -> None:
    try:
        register_slide(image_id)
        logger.info("Slide ready | image_id=%s", image_id)
    except Exception as e:
        logger.error("Registration failed | image_id=%s | error=%s", image_id, e)
        raise JobProcessingError(image_id, str(e))


async def on_message(message: AbstractIncomingMessage) -> None:
    async with message.process(requeue=False):
        msg = _parse(message)
        if msg is None:
            return

        svs_path = Path(settings.slides_dir) / f"{msg.imageId}.svs"
        viewable_url = f"{settings.tileserver_public_base_url}/slides/{msg.imageId}.dzi"

        await download_slide(msg.imageId, msg.imageUrl, svs_path)
        await _register(msg.imageId)
        preview_url = await upload_thumbnail(msg.imageId, svs_path)
        await update_image_urls(msg.imageId, viewable_url, preview_url)


async def start_consumer(connection: aio_pika.RobustConnection) -> None:
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)
    exchange = await channel.declare_exchange(
        settings.rabbitmq_exchange, aio_pika.ExchangeType.TOPIC, durable=True
    )
    queue = await channel.declare_queue(settings.rabbitmq_queue, durable=True)
    await queue.bind(exchange, routing_key=settings.rabbitmq_routing_key)
    logger.info(
        "Listening on queue '%s' with routing key '%s'",
        settings.rabbitmq_queue,
        settings.rabbitmq_routing_key,
    )
    await queue.consume(on_message)
    await asyncio.Future()
