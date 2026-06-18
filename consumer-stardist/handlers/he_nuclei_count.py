import asyncio
import logging
import numpy as np
from pathlib import PurePosixPath
from urllib.parse import urlparse

import json
from stardist.models import StarDist2D
from model_loader import get_stardist
from csbdeep.utils import normalize

from consumer_common.http_client import notify_job_completed, notify_job_failed
from consumer_common.models import JobMessage
from consumer_common.tileserver_client import is_svs, fetch_svs_region, fetch_jpeg_region

from settings import settings

logger = logging.getLogger(__name__)

_model: StarDist2D | None = None


def run_analysis(image_id: str, image_url: str, args: dict) -> dict:
    global _model

    region_raw = args.get("region")
    if not region_raw:
        raise ValueError("'region' is required in args — send viewport coordinates from the frontend")
    region = json.loads(region_raw)

    if not image_id:
        image_id = PurePosixPath(urlparse(image_url).path).stem

    if is_svs(image_url):
        logger.info("SVS path | fetching region from tileserver | image_id=%s region=%s", image_id, region)
        image = fetch_svs_region(image_id, region, tileserver_url=settings.tileserver_internal_url)
    else:
        logger.info("JPEG path | downloading and cropping | image_id=%s region=%s", image_id, region)
        image = fetch_jpeg_region(
            image_url, region,
            minio_public_endpoint=settings.minio_public_endpoint,
            minio_internal_endpoint=settings.minio_internal_endpoint,
        )

    logger.info("Analysis patch size: %s", image.shape)

    prob_thresh = float(args.get("prob_thresh") or "0.5")
    nms_thresh = float(args.get("nms_thresh") or "0.4")

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
