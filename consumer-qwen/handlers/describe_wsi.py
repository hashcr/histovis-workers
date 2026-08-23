import asyncio
import base64
import logging

import httpx
from llama_cpp import Llama
from llama_cpp.llama_types import ChatCompletionRequestSystemMessage, ChatCompletionRequestUserMessage

from consumer_common.http_client import notify_job_completed, notify_job_failed
from consumer_common.models import JobMessage
from model_loader import get_llm
from settings import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a pathology assistant specialized in analyzing histopathology images.
You provide clear, concise, and clinically relevant descriptions of tissue samples.
Always structure your response with: tissue type, morphological findings, and notable observations."""

def fetch_image_data_uri(image_url: str) -> str:
    internal_url = image_url.replace(settings.minio_public_endpoint, settings.minio_internal_endpoint)
    response = httpx.get(internal_url, timeout=30.0)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "image/jpeg")
    encoded = base64.b64encode(response.content).decode("utf-8")
    return f"data:{content_type};base64,{encoded}"

def run_inference(llm: Llama, image_url: str, args: dict) -> str:
    prompt = args.get("prompt", "Describe the histopathology findings in this image.")
    image_data_uri = fetch_image_data_uri(image_url)

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
            lambda: run_inference(llm, message.imageUrl, message.args),  # type: ignore[arg-type]
        )
        output: str = await future

        logger.info("Inference completed | job_id=%s | ouput_length=%d", message.job_id, len(output))

        await notify_job_completed(settings.analysis_service_url, message.job_id, output)

    except Exception as e:
        logger.error("describe_wsi failed | job_id=%s | error=%s", message.job_id, e)
        await notify_job_failed(settings.analysis_service_url, message.job_id, str(e))
        raise

    logger.info("Job %s completed", message.job_id)
