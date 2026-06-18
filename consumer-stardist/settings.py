from consumer_common.settings import BaseConsumerSettings
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseConsumerSettings):
    rabbitmq_queue: str = "stardist.queue"
    rabbitmq_routing_key: str = "job.stardist.*"
    stardist_model: str = "2D_versatile_he"
    minio_public_endpoint: str = "http://localhost:9000"
    minio_internal_endpoint: str = "http://minio:9000"
    tileserver_internal_url: str = "http://consumer-tileserver:8002"

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()

