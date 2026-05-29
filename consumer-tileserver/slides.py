import logging
from pathlib import Path

from openslide import OpenSlide
from openslide.deepzoom import DeepZoomGenerator

from settings import settings

logger = logging.getLogger(__name__)

_slides: dict[str, DeepZoomGenerator] = {}


def register_slide(image_id: str) -> None:
    """Open an .svs from slides_dir and make it available for tile serving."""
    svs_path = Path(settings.slides_dir) / f"{image_id}.svs"
    if not svs_path.exists():
        raise FileNotFoundError(svs_path)
    _slides[image_id] = DeepZoomGenerator(OpenSlide(str(svs_path)))
    logger.info("Registered slide | image_id=%s", image_id)
