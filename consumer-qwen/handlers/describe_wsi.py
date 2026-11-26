import asyncio
import base64
import json
import logging
from io import BytesIO
from pathlib import PurePosixPath
from urllib.parse import urlparse

import numpy as np
from PIL import Image
from llama_cpp import Llama
from llama_cpp.llama_types import ChatCompletionRequestSystemMessage, ChatCompletionRequestUserMessage

from consumer_common.http_client import notify_job_completed, notify_job_failed
from consumer_common.models import JobMessage
from consumer_common.tileserver_client import is_svs, fetch_svs_region, fetch_jpeg_region
from model_loader import get_llm
from settings import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a pathology assistant specialized in analyzing histopathology images.
You provide clear, concise, and clinically relevant descriptions of tissue samples.
Always structure your response with: tissue type, morphological findings, and notable observations."""

def get_region_image(image_id: str, image_url: str, args: dict) -> np.ndarray:
    region_raw = args.get("region")
    if not region_raw:
        raise ValueError("'region' is required in args — send viewport coordinates from the frontend")
    region = json.loads(region_raw)

    if not image_id:
        image_id = PurePosixPath(urlparse(image_url).path).stem

    if is_svs(image_url):
        logger.info("SVS path | fetching region from tileserver | image_id=%s region=%s", image_id, region)
        return fetch_svs_region(image_id, region, tileserver_url=settings.tileserver_internal_url)
    else:
        logger.info("JPEG path | downloading and cropping | image_id=%s region=%s", image_id, region)
        return fetch_jpeg_region(
            image_url, region,
            minio_public_endpoint=settings.minio_public_endpoint,
            minio_internal_endpoint=settings.minio_internal_endpoint,
        )

MAX_IMAGE_DIMENSION = 1024

def image_to_data_uri(image: np.ndarray) -> str:
    pil_image = Image.fromarray(image)
    if max(pil_image.size) > MAX_IMAGE_DIMENSION:
        original_size = pil_image.size
        pil_image.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.LANCZOS)
        logger.info("Resized region for inference | %s -> %s", original_size, pil_image.size)

    buf = BytesIO()
    pil_image.save(buf, format="JPEG")
    encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded}"

def run_inference(llm: Llama, image_id: str, image_url: str, args: dict) -> str:
    prompt = args.get("prompt", "Describe the histopathology findings in this image.")
    region_image = get_region_image(image_id, image_url, args)
    image_data_uri = image_to_data_uri(region_image)

    messages = [
        ChatCompletionRequestSystemMessage(role="system", content=SYSTEM_PROMPT),
        ChatCompletionRequestUserMessage(
            role="user",
            content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_data_uri}},
            ],
        ),
    ]

    response = llm.create_chat_completion(
        messages=messages,
        max_tokens=512,
        temperature=0.3,
        top_p=0.95,
    )

    return response["choices"][0]["message"]["content"]

async def handle_describe_wsi(body: dict) -> None:
    message = JobMessage(**body)
    logger.info("Handling describe_wsi | job_id: %s", message.job_id)

    try:
        llm = get_llm()

        logger.info("Running QWEN inference | job_id=%s", message.job_id)

        future: asyncio.Future = asyncio.get_running_loop().run_in_executor(
            None,
            lambda: run_inference(llm, message.imageId, message.imageUrl, message.args),  # type: ignore[arg-type]
        )
        output: str = await future

        logger.info("Inference completed | job_id=%s | ouput_length=%d", message.job_id, len(output))

        await notify_job_completed(settings.analysis_service_url, message.job_id, output)

    except Exception as e:
        logger.error("describe_wsi failed | job_id=%s | error=%s", message.job_id, e)
        await notify_job_failed(settings.analysis_service_url, message.job_id, str(e))
        raise

    logger.info("Job %s completed", message.job_id)
