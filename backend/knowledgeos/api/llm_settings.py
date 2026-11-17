"""Where each user's model credentials live.

Keys are encrypted with the server's `Vault` before they reach storage and are decrypted only at
the moment of a model call. They are never returned by any endpoint - the API reports only the
provider, the model and the last four characters, enough to recognise which key is saved.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Engine, delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from knowledgeos.llm import Vault
from knowledgeos.state.tables import user_llm_settings


@dataclass(frozen=True, slots=True)
class LlmSetting:
    provider: str
    model: str
    api_key: str

    @property
    def key_hint(self) -> str:
        return f"…{self.api_key[-4:]}" if len(self.api_key) >= 8 else "…"


class LlmSettingsStore:
    """Postgres-backed when given an engine, otherwise in memory (local use and tests)."""

    def __init__(self, vault: Vault, engine: Engine | None = None) -> None:
        self._vault = vault
        self._engine = engine
        self._memory: dict[str, tuple[str, str, str]] = {}

    @classmethod
    def in_memory(cls) -> LlmSettingsStore:
        return cls(Vault.ephemeral())

    def get(self, user_id: str) -> LlmSetting | None:
        if self._engine is None:
            row = self._memory.get(user_id)
            return None if row is None else self._build(*row)
        with self._engine.connect() as connection:
            row = connection.execute(
                select(user_llm_settings).where(user_llm_settings.c.user_id == user_id)
            ).mappings().first()
        if row is None:
            return None
        return self._build(row["provider"], row["model"], row["encrypted_key"])

    def put(self, user_id: str, provider: str, model: str, api_key: str) -> None:
        encrypted = self._vault.encrypt(api_key)
        if self._engine is None:
            self._memory[user_id] = (provider, model, encrypted)
            return
        row = {
            "user_id": user_id,
            "provider": provider,
            "model": model,
            "encrypted_key": encrypted,
            "created_at": datetime.now(UTC),
        }
        statement = pg_insert(user_llm_settings).values(row)
        statement = statement.on_conflict_do_update(
            index_elements=[user_llm_settings.c.user_id],
            set_={k: statement.excluded[k] for k in row if k != "user_id"},
        )
        with self._engine.begin() as connection:
            connection.execute(statement)

    def delete(self, user_id: str) -> None:
        if self._engine is None:
            self._memory.pop(user_id, None)
            return
        with self._engine.begin() as connection:
            connection.execute(
                delete(user_llm_settings).where(user_llm_settings.c.user_id == user_id)
            )

    def _build(self, provider: str, model: str, encrypted: str) -> LlmSetting:
        return LlmSetting(provider, model, self._vault.decrypt(encrypted))
