import asyncio
import logging
import numpy as np
from pathlib import PurePosixPath
from urllib.parse import urlparse

import json
from stardist.models import StarDist2D
from model_loader import get_stardist
from csbdeep.utils import normalize
from skimage.color import rgb2hed
from skimage.filters import threshold_otsu

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

    thresh_weak = float(args.get("thresh_weak") or "0.2")
    thresh_moderate = float(args.get("thresh_moderate") or "0.4")
    thresh_strong = float(args.get("thresh_strong") or "0.6")

    image_normalized = normalize(image, 1, 99.8, axis=(0, 1))
    labels, _ = _model.predict_instances(image_normalized)

    dab_channel = rgb2hed(image)[:, :, 2]

    total_nuclei = int(np.max(labels))

    if total_nuclei == 0:
        return {
            "total_nuclei": 0,
            "positive_nuclei": 0,
            "negative_nuclei": 0,
            "positivity_index": 0.0,
            "dab_threshold": 0.05,
            "image_shape": list(image.shape),
            "intensity_breakdown": {"negative": 0, "weak": 0, "moderate": 0, "strong": 0},
        }

    dab_means = np.array([
        float(dab_channel[labels == i].mean()) for i in range(1, total_nuclei + 1)
    ])

    if args.get("dab_threshold"):
        dab_threshold = float(args["dab_threshold"])
    elif total_nuclei > 1:
        dab_threshold = float(threshold_otsu(dab_means))
    else:
        dab_threshold = 0.05

    logger.info("DAB threshold (auto=%s) = %.4f", "dab_threshold" not in args, dab_threshold)

    positive_mask = dab_means >= dab_threshold
    positive_nuclei = int(positive_mask.sum())
    negative_nuclei = total_nuclei - positive_nuclei

    weak     = int(((dab_means >= thresh_weak)     & (dab_means < thresh_moderate) & positive_mask).sum())
    moderate = int(((dab_means >= thresh_moderate) & (dab_means < thresh_strong)   & positive_mask).sum())
    strong   = int((dab_means >= thresh_strong).sum())

    positivity_index = round(positive_nuclei / total_nuclei, 4)

    return {
        "total_nuclei": total_nuclei,
        "positive_nuclei": positive_nuclei,
        "negative_nuclei": negative_nuclei,
        "positivity_index": positivity_index,
        "dab_threshold": dab_threshold,
        "image_shape": list(image.shape),
        "intensity_breakdown": {
            "negative": negative_nuclei,
            "weak": weak,
            "moderate": moderate,
            "strong": strong,
        },
    }


async def handle_ihc_positive_cells(message: JobMessage) -> None:
    global _model
    logger.info("Handling IHC analysis | job_id: %s", message.job_id)

    try:
        _model = get_stardist()

        logger.info("Running StarDist + DAB scoring | job_id=%s", message.job_id)

        result: dict = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: run_analysis(message.imageId, message.imageUrl, message.args),
        )

        logger.info(
            "IHC scoring completed | job_id=%s | total=%d | positive=%d | index=%.4f",
            message.job_id, result["total_nuclei"], result["positive_nuclei"], result["positivity_index"],
        )

        output = json.dumps(result)
        await notify_job_completed(settings.analysis_service_url, message.job_id, output)

    except Exception as e:
        logger.error("ihc_positive_cells failed | job_id=%s | error=%s", message.job_id, e)
        await notify_job_failed(settings.analysis_service_url, message.job_id, str(e))
        raise

    logger.info("Job %s completed", message.job_id)
