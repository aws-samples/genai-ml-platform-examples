from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    aws_default_region: str = "us-east-1"
    bedrock_model_id: str = "us.anthropic.claude-sonnet-4-20250514-v1:0"
    database_path: str = "data/receptionist.db"
    host: str = "0.0.0.0"  # nosec B104 - required for container deployment
    port: int = 8000
    log_level: str = "info"
    cloudwatch_metrics_enabled: bool = False

    # Derived
    @property
    def db_path(self) -> Path:
        p = Path(self.database_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
