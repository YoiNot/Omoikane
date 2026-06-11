from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "OMOIKANE_"}

    database_url: str = "postgresql+asyncpg://omoikane:omoikane@localhost:5432/omoikane"
    database_url_sync: str = "postgresql://omoikane:omoikane@localhost:5432/omoikane"

    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    github_token: str = ""
    slack_token: str = ""
    notion_token: str = ""

    api_host: str = "0.0.0.0"
    api_port: int = 8420

    project_data_dir: str = ".omoikane"


settings = Settings()
