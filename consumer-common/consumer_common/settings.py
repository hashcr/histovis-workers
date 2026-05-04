from pydantic_settings import BaseSettings, SettingsConfigDict

class BaseConsumerSettings(BaseSettings):
    rabbitmq_host: str = "rabbitmq"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "histovis"
    rabbitmq_password: str = "histovis123"
    rabbitmq_exchange: str = "analysis.exchange"
    rabbitmq_queue: str = "qwen.queue"
    rabbitmq_routing_key: str = "job.qwen.*"

    analysis_service_url: str = "http://analysis-service:8082"

    @property
    def rabbitmq_url(self) -> str:
        return (
            f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}"
            f"@{self.rabbitmq_host}:{self.rabbitmq_port}/"
        )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")