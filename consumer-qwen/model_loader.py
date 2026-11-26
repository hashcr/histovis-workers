import logging
from threading import Thread

from llama_cpp import Llama
from llama_cpp.llama_chat_format import MTMDChatHandler

from settings import settings

logger = logging.getLogger(__name__)

llm: Llama | None = None
model_ready: bool = False

def load_model() -> None:
    global llm, model_ready

    logger.info("Loading model from %s (mmproj: %s)", settings.model_path, settings.mmproj_path)

    chat_handler = MTMDChatHandler(clip_model_path=settings.mmproj_path)

    llm = Llama(
        model_path = settings.model_path,
        chat_handler = chat_handler,
        n_ctx= 4096,
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
        raise RuntimeError("Model not ready yet.")
    return llm
