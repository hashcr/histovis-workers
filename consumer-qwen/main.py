import asyncio
import logging
import logging.handlers
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI

from consumer import start_consumer
from model_loader import load_model_async
import model_loader
from settings import Settings

# create logs directory if it doesn't exist
Path("logs").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),                        # ← console (what you have now)
        logging.handlers.RotatingFileHandler(
            filename="logs/consumer-qwen.log",
            maxBytes=5 * 1024 * 1024,                  # 5 MB per file
            backupCount=3,                              # keep 3 rotated files
            encoding="utf-8",
        )
    ]
)

logger = logging.getLogger(__name__)

settings = Settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("Starting consumer-qwen")
    load_model_async()
    asyncio.create_task(start_consumer())
    logger.info("Lifespan yield reached")
    yield
    logger.info("Stopping consumer-qwen")

app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health():
    return {
        "status": "up",
        "model_ready": model_loader.model_ready,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)




