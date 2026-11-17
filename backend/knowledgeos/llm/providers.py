"""Provider adapters: one `complete()` over Anthropic, OpenAI, Gemini and OpenRouter.

Plain HTTPS through the standard library - no SDKs - so there is nothing extra to install and
the same few dozen lines audit every request that carries a user's key. The network call is the
single function `_post_json`, which tests replace.

Errors are translated into `LlmError` with a message safe to show the user. The key itself is
never included in an exception, a log line or a response.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Literal, TypedDict

TIMEOUT_SECONDS = 120


class Message(TypedDict):
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True, slots=True)
class Provider:
    id: str
    label: str
    default_model: str
    key_help_url: str
    #: Can the user connect an account instead of pasting a key?
    oauth: bool = False


PROVIDERS: dict[str, Provider] = {
    p.id: p
    for p in (
        Provider(
            "openrouter",
            "OpenRouter (connect your account)",
            "anthropic/claude-sonnet-4.5",
            "https://openrouter.ai/keys",
            oauth=True,
        ),
        Provider(
            "anthropic", "Anthropic (Claude)", "claude-sonnet-5-5",
            "https://console.anthropic.com/settings/keys",
        ),
        Provider("openai", "OpenAI", "gpt-4o", "https://platform.openai.com/api-keys"),
        Provider(
            "gemini", "Google Gemini", "gemini-2.0-flash", "https://aistudio.google.com/apikey"
        ),
    )
}


class LlmError(Exception):
    """A failed model call. `status` is the HTTP status to surface to our own client."""

    def __init__(self, message: str, status: int = 502) -> None:
        super().__init__(message)
        self.status = status


def _post_json(url: str, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        detail = _error_detail(exc)
        if exc.code in (401, 403):
            raise LlmError(
                "The provider rejected your API key. Check it in Settings.", 401
            ) from None
        if exc.code == 402:
            raise LlmError("Your provider account is out of credit.", 402) from None
        if exc.code == 429:
            raise LlmError(
                "The provider is rate-limiting this key. Wait a moment and try again.", 429
            ) from None
        raise LlmError(f"The provider returned an error ({exc.code}): {detail}") from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise LlmError(f"Could not reach the provider ({type(exc).__name__}).") from None


def _error_detail(exc: urllib.error.HTTPError) -> str:
    try:
        body = json.loads(exc.read())
    except Exception:  # noqa: BLE001 - best-effort detail only
        return exc.reason or "unknown error"
    error = body.get("error", body) if isinstance(body, dict) else body
    if isinstance(error, dict):
        return str(error.get("message") or error.get("type") or "unknown error")[:300]
    return str(error)[:300]


def complete(
    provider: str,
    api_key: str,
    model: str,
    *,
    system: str,
    messages: list[Message],
    max_tokens: int = 4096,
) -> str:
    """One model turn: the assistant's reply text."""
    if provider not in PROVIDERS:
        raise LlmError(f"Unknown provider: {provider}", 400)
    if not messages:
        raise LlmError("There is nothing to send.", 400)

    if provider == "anthropic":
        data = _post_json(
            "https://api.anthropic.com/v1/messages",
            {"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            {"model": model, "max_tokens": max_tokens, "system": system, "messages": messages},
        )
        text = "".join(
            block.get("text", "")
            for block in data.get("content", [])
            if block.get("type") == "text"
        )
    elif provider in ("openai", "openrouter"):
        base = (
            "https://api.openai.com/v1" if provider == "openai" else "https://openrouter.ai/api/v1"
        )
        data = _post_json(
            f"{base}/chat/completions",
            {"Authorization": f"Bearer {api_key}"},
            {
                "model": model,
                "max_tokens": max_tokens,
                "messages": [{"role": "system", "content": system}, *messages],
            },
        )
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            raise LlmError("The provider returned an unexpected response.") from None
    else:  # gemini
        data = _post_json(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            {"x-goog-api-key": api_key},
            {
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [
                    {
                        "role": "user" if m["role"] == "user" else "model",
                        "parts": [{"text": m["content"]}],
                    }
                    for m in messages
                ],
                "generationConfig": {"maxOutputTokens": max_tokens},
            },
        )
        try:
            text = "".join(
                part.get("text", "") for part in data["candidates"][0]["content"]["parts"]
            )
        except (KeyError, IndexError, TypeError):
            raise LlmError("The provider returned an unexpected response.") from None

    if not text.strip():
        raise LlmError("The model returned an empty reply. Try again.")
    return text


def exchange_openrouter_code(code: str, code_verifier: str) -> str:
    """Trade the one-time code from OpenRouter's "connect" redirect for a user-scoped API key.

    The key belongs to the user's own OpenRouter account and spends their own credit; it is
    stored exactly like a key they pasted.
    """
    data = _post_json(
        "https://openrouter.ai/api/v1/auth/keys",
        {},
        {"code": code, "code_verifier": code_verifier, "code_challenge_method": "S256"},
    )
    key = data.get("key")
    if not isinstance(key, str) or not key:
        raise LlmError("OpenRouter did not return a key. Start the connection again.")
    return key
