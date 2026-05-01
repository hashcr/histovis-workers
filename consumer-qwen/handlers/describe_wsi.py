import logging

from http_client import notify_job_completed, notify_job_failed

logger = logging.getLogger(__name__)

async def handle_describe_wsi(body: dict) -> None:
    job_id = body.get("jobId")
    image_url = body.get("imageUrl")
    args = body.get("args", {})

    logger.info("Handling describe_wsi | job_id: %s | image_url: %s", job_id, image_url)

    try:
        output = f"Hello World! for job {job_id}"

        await notify_job_completed(job_id, output)

    except Exception as e:
        logger.error("describe_wsi failed | job_id=%s | error=%s", job_id, e)
        await notify_job_failed(job_id, str(e))
        raise


    #model inference placeholder
    logger.info("Job %s completed", job_id)