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

    #: Where the Postgres-backed tests run. A SEPARATE database, because those tests truncate
    #: both tables around every case — pointed at `database_url` they silently delete real
    #: assessment history, which they did for six weeks before anyone noticed. The test fixture
    #: additionally refuses any URL whose database name does not end in `_test`, so this cannot
    #: be aimed at real data by editing one env var.
    test_database_url: str = (
        "postgresql+psycopg://knowledgeos:knowledgeos@localhost:5432/knowledgeos_test"
    )

    environment: str = "development"


settings = Settings()
