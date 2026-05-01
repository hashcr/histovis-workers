from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "histovis"
    rabbitmq_password: str = "histovis123"
    rabbitmq_exchange: str = "analysis.exchange"
    rabbitmq_queue: str = "qwen.queue"
    rabbitmq_routing_key: str = "job.qwen.*"

    analysis_service_url: str = "http://localhost:8082"

    model_path: str = "models/qwen2.5-0.5b-instruct-q5_k_m.gguf"

    @property
    def rabbitmq_url(self) -> str:
        return (
            f"ampq://{self.rabbitmq_user}:{self.rabbitmq_password}"
            f"@{self.rabbitmq_host}:{self.rabbitmq_port}/"
        )

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()

