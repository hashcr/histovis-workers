from consumer_common.settings import BaseConsumerSettings
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseConsumerSettings):
    rabbitmq_queue: str = "stardist.queue"
    rabbitmq_routing_key: str = "job.stardist.*"
    stardist_model: str = "2D_versatile_he"

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()

