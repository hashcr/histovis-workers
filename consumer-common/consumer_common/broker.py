import asyncio
import logging
import json
from collections.abc import Callable

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

from consumer_common.settings import BaseConsumerSettings

logger = logging.getLogger(__name__)


class MessageConsumer:
    def __init__(self, registry: dict[str, Callable]):
        self.registry = registry

    async def on_message(self, message: AbstractIncomingMessage) -> None:
        async with message.process(requeue=False):
            try:
                body = json.loads(message.body)
                routing_key = message.routing_key
                plugin_code = routing_key.split(".")[-1]

                logger.info(
                    "Received message | routing_key=%s | jobId=%s | plugin_code=%s",
                    routing_key,
                    body.get("jobId"),
                    plugin_code,
                )

                handler = self.registry.get(plugin_code)

                if handler is None:
                    logger.error("No handler suitable for plugin code: '%s'", plugin_code)
                    return

                await handler(body)

            except Exception as e:
                logger.error("Failed to process message:  %s", e)
                raise


async def publish_message(
    routing_key: str,
    body: dict,
    *,
    settings: BaseConsumerSettings,
) -> None:
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange(
            settings.rabbitmq_exchange,
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )
        await exchange.publish(
            aio_pika.Message(
                body=json.dumps(body).encode(),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=routing_key,
        )
    logger.info("Published message | routing_key=%s", routing_key)


async def start_consuming(
        settings: BaseConsumerSettings,
        registry: dict[str, Callable]
) -> None:
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

        consumer = MessageConsumer(registry)
        await queue.consume(consumer.on_message)
        await asyncio.Future()







