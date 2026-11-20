"""Encryption of users' API keys at rest."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class VaultError(RuntimeError):
    pass


class Vault:
    """Fernet (AES-128-CBC + HMAC) with a key held only in the server's environment.

    A database leak alone therefore exposes nothing usable: the ciphertext is worthless
    without `SECRETS_ENCRYPTION_KEY`, which never touches the database.
    """

    def __init__(self, key: str) -> None:
        try:
            self._fernet = Fernet(key.encode())
        except (ValueError, TypeError) as exc:
            raise VaultError(
                "SECRETS_ENCRYPTION_KEY is not a valid Fernet key. Generate one with: "
                "python -c \"from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())\""
            ) from exc

    @classmethod
    def ephemeral(cls) -> Vault:
        """A throwaway key, for in-memory use where nothing outlives the process anyway."""
        return cls(Fernet.generate_key().decode())

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise VaultError(
                "A stored key could not be decrypted (the encryption key changed?). "
                "Ask the user to enter their API key again."
            ) from exc
