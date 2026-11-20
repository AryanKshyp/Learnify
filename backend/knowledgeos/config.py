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

    # --- accounts (hosted deployment) -------------------------------------------------------
    #: Supabase project URL, e.g. https://abcd.supabase.co. Access tokens are verified against
    #: its published signing keys (JWKS), so no secret is needed for current projects.
    supabase_url: str = ""
    #: The project's public "anon" key. Public by design - it identifies the project to the
    #: browser's sign-in client and grants nothing the database's own rules do not allow.
    supabase_anon_key: str = ""
    #: Only for older Supabase projects that still sign tokens with a shared HS256 secret.
    supabase_jwt_secret: str = ""

    #: Fernet key used to encrypt users' LLM API keys at rest. Generate with
    #: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
    secrets_encryption_key: str = ""

    #: Directory holding the built frontend (`frontend/dist`). When set, the API serves it, so
    #: the whole product is one container on one origin.
    frontend_dist: str = ""

    @property
    def auth_enabled(self) -> bool:
        return bool(self.supabase_url or self.supabase_jwt_secret)

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


settings = Settings()
