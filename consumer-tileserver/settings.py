from consumer_common.settings import BaseConsumerSettings
from pydantic_settings import SettingsConfigDict


class TileServerSettings(BaseConsumerSettings):
    rabbitmq_queue: str = "tileserver.setup.wsi"
    rabbitmq_routing_key: str = "job.tileserver.setup.wsi"

    tileserver_public_base_url: str
    slides_dir: str = "/app/slides"

    minio_public_endpoint: str = "http://localhost:9000"
    minio_internal_endpoint: str = "http://minio:9000"

    model_config = SettingsConfigDict(env_file=".env")


settings = TileServerSettings()
