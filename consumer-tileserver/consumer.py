import asyncio
import json
import logging
from pathlib import Path

import aio_pika
import httpx
from aio_pika.abc import AbstractIncomingMessage

from consumer_common.exceptions import JobProcessingError
from models import ImageProcessMessage
from settings import settings
from slides import register_slide

logger = logging.getLogger(__name__)


async def on_message(message: AbstractIncomingMessage) -> None:
    async with message.process(requeue=False):
        try:
            body = json.loads(message.body)
            msg = ImageProcessMessage(**body)
        except Exception as e:
            logger.error("Invalid message body: %s", e)
            return

        svs_path = Path(settings.slides_dir) / f"{msg.imageId}.svs"
        logger.info("Downloading slide | image_id=%s | url=%s", msg.imageId, msg.imageUrl)

        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("GET", msg.imageUrl) as response:
                    response.raise_for_status()
                    with open(svs_path, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=65536):
                            f.write(chunk)
        except Exception as e:
            logger.error("Download failed | image_id=%s | error=%s", msg.imageId, e)
            raise JobProcessingError(msg.imageId, str(e))

        try:
            register_slide(msg.imageId)
        except Exception as e:
            logger.error("Registration failed | image_id=%s | error=%s", msg.imageId, e)
            raise JobProcessingError(msg.imageId, str(e))

        logger.info("Slide ready | image_id=%s", msg.imageId)


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
