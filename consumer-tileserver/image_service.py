import logging

import httpx

from consumer_common.exceptions import JobProcessingError
from settings import settings

logger = logging.getLogger(__name__)


async def update_image_urls(image_id: str, viewable_url: str, preview_url: str) -> None:
    logger.info("Updating image URLs | image_id=%s", image_id)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.patch(
                f"{settings.image_service_url}/api/images/{image_id}/urls",
                json={"viewableImageUrl": viewable_url, "previewImageUrl": preview_url},
            )
        if response.status_code in (400, 404):
            raise JobProcessingError(
                image_id, f"PATCH failed {response.status_code}: {response.text}"
            )
        response.raise_for_status()
        logger.info("Image URLs updated | image_id=%s", image_id)
    except JobProcessingError:
        raise
    except Exception as e:
        logger.error("Image service PATCH failed | image_id=%s | error=%s", image_id, e)
        raise JobProcessingError(image_id, str(e))
