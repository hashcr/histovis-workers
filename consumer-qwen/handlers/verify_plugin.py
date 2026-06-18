import asyncio
import json
import logging
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
You are a security reviewer for Python plugin handlers. A handler must ONLY: load an image or data, run it through an AI model, and return a result value. Anything else is UNSAFE.

Decide if the code below is SAFE or UNSAFE. When uncertain, answer UNSAFE.

Mark UNSAFE if the code contains ANY of:
- Network calls (requests, urllib, socket, http, httpx)
- Shell/system execution (os.system, subprocess, popen, eval, exec, compile, __import__)
- File access beyond reading input or writing the result (os.remove, shutil, open() for delete/append to system paths)
- Dangerous imports (ctypes, socket, pickle.loads, sys.exit, importlib)
- Obvious infinite loops (while True without break, recursion without base case)
- Reading secrets/env (os.environ, /etc, ~/.ssh, credentials, keys)
- Obfuscation (base64/hex decode then exec, getattr/setattr on dynamic strings)

Mark SAFE ONLY if the code does nothing but: read the input, call an AI/analysis function, return a value.

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
        max_tokens=100,
        temperature=0.0,
    )
    raw = response["choices"][0]["message"]["content"].strip()
    logger.info("Security review raw response | path=%s | response=%s", script_path, raw)
    try:
        verdict = json.loads(raw)["verdict"]
        return verdict == "SAFE"
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
