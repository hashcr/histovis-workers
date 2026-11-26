import asyncio
import json
import logging
import re
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse
from pydantic import ValidationError

from consumer_common.broker import publish_message
from consumer_common.http_client import update_plugin_status
from consumer_common.models import InstallPluginMessage, VerifyPluginMessage
from consumer_common.r2_client import download_bytes
from model_loader import get_llm

from settings import settings

logger = logging.getLogger(__name__)

_SECURITY_PROMPT = """\
You are a security reviewer for HistoVis Python plugin handlers.
A valid plugin defines `async def handle(body: dict)` which:
1. Parses `JobMessage` and arguments (`json`, `urllib.parse`, `PurePosixPath` are SAFE).
2. Loads the input image region via `consumer_common.tileserver_client` (`is_svs`, `fetch_svs_region`, `fetch_jpeg_region`).
3. Runs AI or image analysis using `model_loader` (`get_stardist`, `get_llm`) and scientific/image libraries (`numpy`, `PIL`, `skimage`, `csbdeep`, `stardist`, `llama_cpp`).
4. Reports job status/results ONLY to the `analysis-service` API via `consumer_common.http_client` (`notify_job_completed`, `notify_job_failed`, `notify_job_running`) or `settings.analysis_service_url`.

Decide if the code below is SAFE or UNSAFE. When uncertain, answer UNSAFE.

Mark UNSAFE if the code contains ANY of:
- Network/HTTP calls to anything OTHER than the `analysis-service` API or `consumer_common` image/job helpers (`requests`, `urllib.request`, `socket`, or `httpx`/`http` to external/arbitrary URLs are UNSAFE; `consumer_common.http_client`, `consumer_common.tileserver_client`, and `urllib.parse` are SAFE)
- Shell/system execution (`os.system`, `subprocess`, `popen`, `eval`, `exec`, `compile`, `__import__`)
- File system modification or arbitrary file access (`os.remove`, `shutil`, `open()` on host/system paths)
- Dangerous imports (`ctypes`, `socket`, `pickle`, `sys.exit`, `importlib`)
- Obvious infinite loops (`while True` without break, unbounded recursion)
- Reading secrets or environment variables (`os.environ`, `/etc`, `~/.ssh`, credentials, keys — passing `settings` endpoints to `consumer_common` helpers is SAFE)
- Obfuscation (`base64`/`hex` decode into `exec`/`eval`, dynamic `getattr`/`setattr`; encoding images to `base64` data URIs is SAFE)

Output rules:
- Respond with EXACTLY ONE line of JSON and nothing before or after.
- Use this exact format: {{"verdict":"SAFE","reason":"..."}} or {{"verdict":"UNSAFE","reason":"..."}}
- The reason must be one short sentence, max 12 words.
- Do not explain, do not add markdown, do not repeat the code.

CODE:
---
{handler_code}
---\
"""


def validate(script_path: str) -> bool:
    code = Path(script_path).read_text(encoding="utf-8")
    llm = get_llm()
    response = llm.create_chat_completion(
        messages=[{"role": "user", "content": _SECURITY_PROMPT.format(handler_code=code)}],
        max_tokens=150,
        temperature=0.0,
    )
    raw = response["choices"][0]["message"]["content"].strip()
    logger.info("Security review raw response | path=%s | response=%s", script_path, raw)
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.IGNORECASE)
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    try:
        payload = json.loads(match.group(0) if match else cleaned)
        return payload.get("verdict") == "SAFE"
    except Exception:
        logger.warning("Could not parse security review response | path=%s | raw=%s", script_path, raw)
        return False


async def handle_verify_plugin(body: dict) -> None:
    try:
        message = VerifyPluginMessage(**body)
    except ValidationError as e:
        logger.error("Invalid VerifyPluginMessage | error=%s", e)
        return

    await update_plugin_status(settings.analysis_service_url, message.plugin_id, "VERIFYING")
    logger.info("Plugin status set to VERIFYING | plugin_id=%s", message.plugin_id)

    logger.info("Handling verify_plugin | plugin_id=%s | plugin_code=%s",
                message.plugin_id, message.pluginCode)

    key = urlparse(message.scriptUrl).path.lstrip("/").split("/", 1)[1]
    suffix = PurePosixPath(key).suffix
    local_path = Path(settings.plugins_dir) / f"{message.plugin_id}{suffix}"

    try:
        content = download_bytes(
            key,
            s3_endpoint=settings.minio_s3_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            bucket=settings.minio_bucket,
        )
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(content)
        logger.info("Script downloaded | plugin_id=%s | path=%s", message.plugin_id, local_path)

        is_valid = await asyncio.get_running_loop().run_in_executor(
            None, lambda: validate(str(local_path))
        )
        if not is_valid:
            logger.warning("Script validation failed | plugin_id=%s", message.plugin_id)
            await update_plugin_status(settings.analysis_service_url, message.plugin_id, "FAILED")
            return

        install_message = InstallPluginMessage(
            pluginId=message.pluginId,
            pluginCode=message.pluginCode,
            localScriptPath=str(local_path),
            installationTopicRoute=message.installationTopicRoute,
        )
        install_route = message.installationTopicRoute.rsplit(".", 1)[0] + ".install"
        await publish_message(
            install_route,
            install_message.model_dump(mode="json"),
            settings=settings,
        )
        logger.info("InstallPluginMessage published | plugin_id=%s | route=%s",
                    message.plugin_id, install_route)

    except Exception as e:
        logger.error("verify_plugin failed | plugin_id=%s | error=%s", message.plugin_id, e)
        await update_plugin_status(settings.analysis_service_url, message.plugin_id, "FAILED")
        raise
