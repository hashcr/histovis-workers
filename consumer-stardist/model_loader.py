import logging
from threading import Thread

from stardist.models import StarDist2D

logger = logging.getLogger(__name__)


model_ready: bool = False
stardist: StarDist2D | None = None

def load_model() -> None:
    global stardist, model_ready
    logger.info("Loading StarDist model 2D_versatile_he...")
    stardist = StarDist2D.from_pretrained("2D_versatile_he")
    logger.info("StarDist model loaded successfully")
    model_ready = True

def load_model_async() -> None:
    thread = Thread(target=load_model, daemon=True)
    thread.start()

def get_stardist() -> StarDist2D:
    if stardist is None:
        raise RuntimeError("Stardist2D Model not ready yet.")
    return stardist