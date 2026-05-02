from consumer_common.settings import BaseConsumerSettings
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseConsumerSettings):
    rabbitmq_queue: str = "qwen.queue"
    rabbitmq_routing_key: str = "job.qwen.*"
    model_path: str = "models/qwen2.5-0.5b-instruct-q5_k_m.gguf"

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()

