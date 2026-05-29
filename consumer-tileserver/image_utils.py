import asyncio
import functools
import io
from pathlib import Path

import httpx
import openslide

from consumer_common.exceptions import JobProcessingError
from consumer_common import r2_client
from settings import settings

logger = __import__("logging").getLogger(__name__)


def make_thumbnail(svs_path: Path, size: tuple[int, int] = (512, 512)) -> bytes:
    slide = openslide.OpenSlide(str(svs_path))
    thumbnail = slide.get_thumbnail(size).convert("RGB")
    slide.close()
    buf = io.BytesIO()
    thumbnail.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


async def download_slide(image_id: str, image_url: str, svs_path: Path) -> None:
    image_url = image_url.replace(settings.minio_public_endpoint, settings.minio_internal_endpoint)
    logger.info("Downloading slide | image_id=%s | url=%s", image_id, image_url)
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", image_url) as response:
                response.raise_for_status()
                with open(svs_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=65536):
                        f.write(chunk)
    except Exception as e:
        logger.error("Download failed | image_id=%s | error=%s", image_id, e)
        raise JobProcessingError(image_id, str(e))


async def upload_thumbnail(image_id: str, svs_path: Path) -> str:
    logger.info("Generating thumbnail | image_id=%s", image_id)
    try:
        loop = asyncio.get_running_loop()
        jpeg_bytes = await loop.run_in_executor(None, make_thumbnail, svs_path)

        key = f"previews/{image_id}.jpg"
        upload = functools.partial(
            r2_client.upload_bytes,
            jpeg_bytes,
            key,
            internal_endpoint=settings.minio_s3_endpoint,
            public_endpoint=settings.minio_public_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            bucket=settings.minio_bucket,
            content_type="image/jpeg",
        )
        preview_url = await loop.run_in_executor(None, upload)
        logger.info("Thumbnail uploaded | image_id=%s | url=%s", image_id, preview_url)
        return preview_url
    except Exception as e:
        logger.error("Thumbnail/upload failed | image_id=%s | error=%s", image_id, e)
        raise JobProcessingError(image_id, str(e))
