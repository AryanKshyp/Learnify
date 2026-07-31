"""Application settings.

Infrastructure configuration only — database URL, environment. Engine tuning parameters do
NOT belong here; they live in `knowledgeos.engine.config` so that Layer 3 stays free of any
dependency on application wiring.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "postgresql+psycopg://knowledgeos:knowledgeos@localhost:5432/knowledgeos"
    environment: str = "development"


settings = Settings()
