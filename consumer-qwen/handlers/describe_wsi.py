import asyncio
from concurrent.futures import Future as ConcurrentFuture

import logging

from llama_cpp import Llama
from llama_cpp.llama_types import ChatCompletionRequestSystemMessage, ChatCompletionRequestUserMessage

from http_client import notify_job_completed, notify_job_failed
from model_loader import get_llm

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a pathology assistant specialized in analyzing histopathology images.
You provide clear, concise, and clinically relevant descriptions of tissue samples.
Always structure your response with: tissue type, morphological findings, and notable observations."""

def run_inference(llm: Llama, image_url: str, args: dict) -> str:
    prompt = args.get("prompt", "Describe the histopathology findings in this image.")

    messages = [
        ChatCompletionRequestSystemMessage(role="system", content=SYSTEM_PROMPT),
        ChatCompletionRequestUserMessage(role="user", content=f"{prompt}\n\nImage URL: {image_url}"),
    ]

    response = llm.create_chat_completion(
        messages=messages,
        max_tokens=512,
        temperature=0.3,
        top_p=0.95,
    )

    return response["choices"][0]["message"]["content"]

async def handle_describe_wsi(body: dict) -> None:
    job_id = body.get("jobId")
    image_url = body.get("imageUrl")
    args = body.get("args", {})

    logger.info("Handling describe_wsi | job_id: %s | image_url: %s", job_id, image_url)

    try:
        llm = get_llm()

        logger.info("Running inference | job_id=%s", job_id)

        future: asyncio.Future = asyncio.get_running_loop().run_in_executor(
            None,
            lambda: run_inference(llm, image_url, args),  # type: ignore[arg-type]
        )
        output: str = await future

        logger.info("Inference completed | job_id=%s | ouput_length=%d", job_id, len(output))

        await notify_job_completed(job_id, output)

    except Exception as e:
        logger.error("describe_wsi failed | job_id=%s | error=%s", job_id, e)
        await notify_job_failed(job_id, str(e))
        raise


    #model inference placeholder
    logger.info("Job %s completed", job_id)