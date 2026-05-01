import logging

import httpx

from settings import settings

logger = logging.getLogger(__name__)

async def notify_job_completed(job_id: str, output: str) -> None:
    await _update_job_result(job_id, status="COMPLETED", output=output)

async def notify_job_failed(job_id: str, output: str) -> None:
    await _update_job_result(job_id, status="FAILED", output=output)

async def notify_job_running(job_id: str, output: str) -> None:
    await _update_job_result(job_id, status="RUNNING", output=output)

async def _update_job_result(job_id: str, status: str, output: str) -> None:
    url = f"{settings.analysis_service_url}/api/analysis/jobs/{job_id}/result"

    payload = {
        "status": status,
        "output": output,
    }

    logger.info("Notifying analysis-service | job_id=%s | status=%s", job_id, status)

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.put(url, json=payload)
        response.raise_for_status()

    logger.info("Analysis-service notified | job_id=%s | status=%s", job_id, status)