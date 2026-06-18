import asyncio
import io
import logging
import logging.handlers
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

import aio_pika
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from consumer import start_consumer
from settings import settings
from slides import _slides, register_slide

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
    loop = asyncio.get_event_loop()
    loop.set_default_executor(ThreadPoolExecutor(max_workers=100))

    logger.info("Starting consumer-tileserver")

    slides_dir = Path(settings.slides_dir)
    slides_dir.mkdir(parents=True, exist_ok=True)
    for svs_file in sorted(slides_dir.glob("*.svs")):
        register_slide(svs_file.stem)
    logger.info("Loaded %d slide(s) from %s", len(_slides), slides_dir)

    logger.info("Connecting to RabbitMQ at %s", settings.rabbitmq_host)
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    app.state.rabbitmq = connection
    asyncio.create_task(start_consumer(connection))
    logger.info("RabbitMQ connected — queue: %s", settings.rabbitmq_queue)

    yield

    await connection.close()
    logger.info("Stopping consumer-tileserver")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "up", "slides": list(_slides.keys())}


@app.get("/slides/{image_id}.dzi")
def get_dzi(image_id: str):
    if image_id not in _slides:
        raise HTTPException(status_code=404, detail=f"Slide '{image_id}' not found")
    return Response(content=_slides[image_id].get_dzi("jpeg"), media_type="application/xml")


@app.get("/slides/{image_id}_files/{level}/{tile_name}")
def get_tile(image_id: str, level: int, tile_name: str):
    if image_id not in _slides:
        raise HTTPException(status_code=404, detail=f"Slide '{image_id}' not found")

    try:
        col, row = map(int, tile_name.removesuffix(".jpeg").removesuffix(".jpg").split("_"))
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid tile name: {tile_name}")

    try:
        tile = _slides[image_id].get_tile(level, (col, row))
    except Exception:
        raise HTTPException(status_code=404, detail="Tile not found")

    buf = io.BytesIO()
    tile.save(buf, format="JPEG")
    return Response(content=buf.getvalue(), media_type="image/jpeg")


@app.get("/slides/{image_id}/region")
def get_region(image_id: str, x: int, y: int, width: int, height: int):
    if image_id not in _slides:
        raise HTTPException(status_code=404, detail=f"Slide '{image_id}' not found")
    region = _slides[image_id]._osr.read_region((x, y), 0, (width, height)).convert("RGB")
    buf = io.BytesIO()
    region.save(buf, format="JPEG", quality=90)
    return Response(content=buf.getvalue(), media_type="image/jpeg")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=False)
