from consumer_common.settings import BaseConsumerSettings
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseConsumerSettings):
    rabbitmq_queue: str = "qwen.queue"
    rabbitmq_routing_key: str = "job.qwen.*"
    model_path: str = "models/qwen2.5-0.5b-instruct-q5_k_m.gguf"
    minio_s3_endpoint: str = "http://minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin123"
    minio_bucket: str = "histovis-images"
    plugins_dir: str = "/app/plugins"

settings = Settings()

