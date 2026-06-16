import asyncio
import logging
import numpy as np
from io import BytesIO
from pathlib import PurePosixPath
from urllib.parse import urlparse

import httpx
import json
from PIL import Image
from stardist.models import StarDist2D
from model_loader import get_stardist
from csbdeep.utils import normalize

from consumer_common.http_client import notify_job_completed, notify_job_failed
from consumer_common.models import JobMessage

from settings import settings

logger = logging.getLogger(__name__)

_model: StarDist2D | None = None

def _is_svs(image_url: str) -> bool:
    return PurePosixPath(urlparse(image_url).path).suffix.lower() == ".svs"


def fetch_svs_region(image_id: str, region: dict) -> np.ndarray:
    url = (
        f"{settings.tileserver_internal_url}/slides/{image_id}/region"
        f"?x={region['x']}&y={region['y']}&width={region['width']}&height={region['height']}"
    )
    resp = httpx.get(url, timeout=30.0)
    resp.raise_for_status()
    return np.array(Image.open(BytesIO(resp.content)).convert("RGB"))


def fetch_jpeg_region(image_url: str, region: dict) -> np.ndarray:
    image_url = image_url.replace(settings.minio_public_endpoint, settings.minio_internal_endpoint)
    Image.MAX_IMAGE_PIXELS = None  # trusted internal source
    resp = httpx.get(image_url, timeout=60.0)
    resp.raise_for_status()
    img = Image.open(BytesIO(resp.content)).convert("RGB")
    x, y, w, h = region["x"], region["y"], region["width"], region["height"]
    return np.array(img.crop((x, y, x + w, y + h)))


def run_analysis(image_id: str, image_url: str, args: dict) -> dict:
    global _model

    region_raw = args.get("region")
    if not region_raw:
        raise ValueError("'region' is required in args — send viewport coordinates from the frontend")
    region = json.loads(region_raw)

    if not image_id:
        image_id = PurePosixPath(urlparse(image_url).path).stem

    if _is_svs(image_url):
        logger.info("SVS path | fetching region from tileserver | image_id=%s region=%s", image_id, region)
        image = fetch_svs_region(image_id, region)
    else:
        logger.info("JPEG path | downloading and cropping | image_id=%s region=%s", image_id, region)
        image = fetch_jpeg_region(image_url, region)

    logger.info("Analysis patch size: %s", image.shape)

    prob_thresh = float(args.get("prob_thresh", "0.5"))
    nms_thresh = float(args.get("nms_thresh", "0.4"))

    image_normalized = normalize(image, 1, 99.8, axis=(0, 1))

    labels, details = _model.predict_instances(
        image_normalized,
        prob_thresh=prob_thresh,
        nms_thresh=nms_thresh,
    )

    nucleus_count = int(np.max(labels))
    mean_prob = float(np.mean(details["prob"]))

    return {
        "nucleus_count": nucleus_count,
        "mean_confidence": round(mean_prob, 4),
        "prob_thresh": prob_thresh,
        "nms_thresh": nms_thresh,
        "image_shape": list(image.shape),
    }


async def handle_he_nuclei_count(message: JobMessage) -> None:
    global _model
    logger.info("Handling H&E analysis | job_id: %s", message.job_id)

    try:
        _model = get_stardist()

        logger.info("Running StarDist inference | job_id=%s", message.job_id)

        result: str = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: run_analysis(message.imageId, message.imageUrl, message.args),  # type: ignore[arg-type]
        )

        logger.info("StarDist Inference completed | job_id=%s | nuclei=%d | confidence=%.4f",
                    message.job_id, result["nucleus_count"], result["mean_confidence"])

        output = json.dumps(result)
        await notify_job_completed(settings.analysis_service_url, message.job_id, output)

    except Exception as e:
        logger.error("he_nuclei_count failed | job_id=%s | error=%s", message.job_id, e)
        await notify_job_failed(settings.analysis_service_url, message.job_id, str(e))
        raise

    logger.info("Job %s completed", message.job_id)
