"""Calling a language model on the user's behalf, with the user's own credentials.

The product never pays for inference and never holds a platform-wide key: each user supplies
their own API key (or connects an OpenRouter account), and every call here is made with that
key. Depends on nothing else in the application - it knows nothing about assessments - so the
boundary between "what to ask" (owned by `assessment`) and "how to ask it" stays clean.
"""

from .crypto import Vault, VaultError
from .providers import PROVIDERS, LlmError, Message, Provider, complete, exchange_openrouter_code

__all__ = [
    "PROVIDERS",
    "LlmError",
    "Message",
    "Provider",
    "Vault",
    "VaultError",
    "complete",
    "exchange_openrouter_code",
]
