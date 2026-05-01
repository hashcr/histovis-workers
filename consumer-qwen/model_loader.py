import logging
from threading import Thread

from llama_cpp import Llama

from settings import settings

logger = logging.getLogger(__name__)

llm: Llama | None = None
model_ready: bool = False

def load_model() -> None:
    global llm, model_ready

    logger.info("Loading model from %s", settings.model_path)

    llm = Llama(
        model_path = settings.model_path,
        n_ctx= 2048,
        n_threads= 4,
        verbose = False,
    )

    model_ready = True
    logger.info("Model loaded successfully")

def load_model_async() -> None:
    thread = Thread(target=load_model, daemon=True)
    thread.start()

def get_llm() -> Llama:
    if llm is None:
        raise RuntimeError("Gwen 0.5B Model not ready yet.")
    return llm
