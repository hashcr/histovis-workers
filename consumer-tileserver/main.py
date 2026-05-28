import asyncio
import logging
import logging.handlers
from contextlib import asynccontextmanager
from pathlib import Path

import aio_pika
from fastapi import FastAPI

from settings import settings

Path("logs").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(
            filename="logs/consumer-tileserver.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        ),
    ],
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting consumer-tileserver")
    logger.info("Connecting to RabbitMQ at %s", settings.rabbitmq_host)
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    app.state.rabbitmq = connection
    logger.info("RabbitMQ connected — queue: %s", settings.rabbitmq_queue)
    yield
    await connection.close()
    logger.info("Stopping consumer-tileserver")


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "up"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8100, reload=False)
