import asyncio
import logging
import numpy as np
from io import BytesIO

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


def fetch_image(imge_url: str) -> np.ndarray:
    get_image_response = httpx.get(imge_url, timeout=30.0)
    get_image_response.raise_for_status()
    image = Image.open(BytesIO(get_image_response.content)).convert("RGB")
    return np.array(image)

def run_analysis(image_url: str, args: dict) -> dict:
    global _model

    image = fetch_image(image_url)

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
        "image_shape": image.shape,
    }

async def handle_he_nuclei_count(message: JobMessage) -> None:
    global _model
    logger.info("Handling H&E analysis | job_id: %s", message.job_id)

    try:
        _model = get_stardist()

        logger.info("Running StarDist inference | job_id=%s", message.job_id)

        result: str = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: run_analysis(message.imageUrl, message.args),  # type: ignore[arg-type]
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