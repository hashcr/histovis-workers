from __future__ import annotations

from io import BytesIO
from pathlib import PurePosixPath
from urllib.parse import urlparse

import httpx


def is_svs(image_url: str) -> bool:
    return PurePosixPath(urlparse(image_url).path).suffix.lower() == ".svs"


def fetch_svs_region(
    image_id: str,
    region: dict,
    *,
    tileserver_url: str,
) -> "np.ndarray":
    import numpy as np
    from PIL import Image

    url = (
        f"{tileserver_url}/slides/{image_id}/region"
        f"?x={region['x']}&y={region['y']}&width={region['width']}&height={region['height']}"
    )
    resp = httpx.get(url, timeout=30.0)
    resp.raise_for_status()
    return np.array(Image.open(BytesIO(resp.content)).convert("RGB"))


def fetch_jpeg_region(
    image_url: str,
    region: dict,
    *,
    minio_public_endpoint: str,
    minio_internal_endpoint: str,
) -> "np.ndarray":
    import numpy as np
    from PIL import Image

    image_url = image_url.replace(minio_public_endpoint, minio_internal_endpoint)
    Image.MAX_IMAGE_PIXELS = None  # trusted internal source
    resp = httpx.get(image_url, timeout=60.0)
    resp.raise_for_status()
    img = Image.open(BytesIO(resp.content)).convert("RGB")
    x, y, w, h = region["x"], region["y"], region["width"], region["height"]
    return np.array(img.crop((x, y, x + w, y + h)))
