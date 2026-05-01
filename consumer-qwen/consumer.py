import asyncio
import logging
import json

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

from settings import settings
from handler_registry import load_handlers

logger = logging.getLogger(__name__)

async def start_consumer():
    global HANDLERS
    HANDLERS = load_handlers()

    logger.info("Connecting to RabbitMQ at %s", settings.rabbitmq_host)

    connection = await aio_pika.connect_robust(settings.rabbitmq_url)

    async with connection:
        channel = await connection.channel()

        await channel.set_qos(prefetch_count=1)

        exchange = await channel.declare_exchange(
            settings.rabbitmq_exchange,
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )

        queue = await channel.declare_queue(
            settings.rabbitmq_queue,
            durable=True,
        )

        await queue.bind(exchange, routing_key=settings.rabbitmq_routing_key)

        logger.info(
            "Listening on queue '%s' with routing key '%s'",
            settings.rabbitmq_queue,
            settings.rabbitmq_routing_key,
        )

        await queue.consume(on_message)
        await asyncio.Future()

async def on_message(message: AbstractIncomingMessage) -> None:
    async with message.process(requeue=False):
        try:
            body = json.loads(message.body)
            routing_key = message.routing_key
            plugin_code = routing_key.split(".")[-1]

            logger.info(
                "Received message | routing_key=%s | body=%s",
                routing_key,
                body,
            )

            handler = HANDLERS.get(plugin_code)

            if handler is None:
                logger.error("No handler suitable for plugin code: '%s'", plugin_code)
                return

            await handler(body)


        except Exception as e:
            logger.error("Failed to process message:  %s", e)
            raise







