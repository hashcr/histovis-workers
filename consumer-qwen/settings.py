from consumer_common.settings import BaseConsumerSettings
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseConsumerSettings):
    rabbitmq_queue: str = "qwen.queue"
    rabbitmq_routing_key: str = "job.qwen.*"
    model_path: str = "models/Qwen3VL-2B-Instruct-Q4_K_M.gguf"
    mmproj_path: str = "models/mmproj-Qwen3VL-2B-Instruct-Q8_0.gguf"
    minio_s3_endpoint: str = "http://minio:9000"
    minio_public_endpoint: str = "http://localhost:9000"
    minio_internal_endpoint: str = "http://minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin123"
    minio_bucket: str = "histovis-images"
    plugins_dir: str = "/app/plugins"

settings = Settings()
