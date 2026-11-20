"""Run the assessment inside the app, with the user's own model credentials.

The paste loop (`/sessions/open/{id}/prompt` -> external chat -> `/sessions/ingest`) is unchanged
and still available. This router is the same loop with the copy-paste removed:

    GET/PUT/DELETE /llm/settings      which provider and key to use
    POST /sessions/open/{id}/chat     one conversational turn (study or assess)
    POST /sessions/open/{id}/finish   ask for the Schema B and ingest it

The division of labour is the architecture's, not weakened by convenience. The application still
owns every prompt and the Schema B contract; the model still only produces observations; and the
Schema B it returns goes through exactly the same strict validator and engine as a pasted one.
The server holds no conversation - the browser sends the transcript each turn - so a restart
mid-session costs nothing.
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from knowledgeos.api.auth import UserId
from knowledgeos.api.dependencies import Context
from knowledgeos.api.llm_settings import LlmSetting, LlmSettingsStore
from knowledgeos.api.routers.sessions import ingest_response
from knowledgeos.api.schemas import IngestResponse
from knowledgeos.assessment import UnknownSessionError, prompts
from knowledgeos.llm import (
    PROVIDERS,
    Message,
    VaultError,
    complete,
    exchange_openrouter_code,
)

router = APIRouter(tags=["llm"])

#: Bounds on what a browser may make the server forward to a paid API.
MAX_MESSAGES = 80
MAX_MESSAGE_CHARS = 12_000


# ------------------------------------------------------------------ settings


class ProviderOut(BaseModel):
    id: str
    label: str
    default_model: str
    key_help_url: str
    oauth: bool


class SettingsOut(BaseModel):
    configured: bool
    provider: str | None = None
    model: str | None = None
    key_hint: str | None = None


class SettingsIn(BaseModel):
    provider: str
    api_key: str = Field(min_length=8, max_length=512)
    model: str | None = Field(default=None, max_length=120)
    #: Make one tiny call first, so a mistyped key is caught here rather than mid-session.
    verify: bool = True


class OpenRouterExchange(BaseModel):
    code: str = Field(min_length=1, max_length=512)
    code_verifier: str = Field(min_length=1, max_length=512)


def _store(request: Request) -> LlmSettingsStore:
    return request.app.state.llm_settings


def _out(setting: LlmSetting | None) -> SettingsOut:
    if setting is None:
        return SettingsOut(configured=False)
    return SettingsOut(
        configured=True,
        provider=setting.provider,
        model=setting.model,
        key_hint=setting.key_hint,
    )


def _verify(provider: str, api_key: str, model: str) -> None:
    complete(
        provider, api_key, model,
        system="Reply with the single word: ok",
        messages=[{"role": "user", "content": "ping"}],
        max_tokens=8,
    )


@router.get("/llm/providers", response_model=tuple[ProviderOut, ...])
def list_providers() -> tuple[ProviderOut, ...]:
    return tuple(
        ProviderOut(
            id=p.id, label=p.label, default_model=p.default_model,
            key_help_url=p.key_help_url, oauth=p.oauth,
        )
        for p in PROVIDERS.values()
    )


@router.get("/llm/settings", response_model=SettingsOut)
def get_settings(request: Request, user_id: UserId) -> SettingsOut:
    try:
        return _out(_store(request).get(user_id))
    except VaultError:
        # Saved under a key we no longer hold: report as not configured so the user re-enters it.
        return SettingsOut(configured=False)


@router.put("/llm/settings", response_model=SettingsOut)
def put_settings(body: SettingsIn, request: Request, user_id: UserId) -> SettingsOut:
    provider = PROVIDERS.get(body.provider)
    if provider is None:
        raise HTTPException(422, "Unknown provider.")
    model = (body.model or provider.default_model).strip()
    api_key = body.api_key.strip()
    if body.verify:
        _verify(provider.id, api_key, model)
    store = _store(request)
    store.put(user_id, provider.id, model, api_key)
    return _out(store.get(user_id))


@router.delete("/llm/settings", status_code=status.HTTP_204_NO_CONTENT)
def delete_settings(request: Request, user_id: UserId) -> None:
    _store(request).delete(user_id)


@router.post("/llm/openrouter/exchange", response_model=SettingsOut)
def openrouter_exchange(
    body: OpenRouterExchange, request: Request, user_id: UserId
) -> SettingsOut:
    key = exchange_openrouter_code(body.code, body.code_verifier)
    store = _store(request)
    store.put(user_id, "openrouter", PROVIDERS["openrouter"].default_model, key)
    return _out(store.get(user_id))


# ------------------------------------------------------------------ the in-app session


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=MAX_MESSAGE_CHARS)


class ChatIn(BaseModel):
    phase: Literal["study", "assess"]
    messages: list[Turn] = Field(max_length=MAX_MESSAGES)


class ChatOut(BaseModel):
    reply: str


class FinishIn(BaseModel):
    messages: list[Turn] = Field(min_length=2, max_length=MAX_MESSAGES)


def _require_setting(request: Request, user_id: str) -> LlmSetting:
    try:
        setting = _store(request).get(user_id)
    except VaultError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    if setting is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Add an AI provider key in Settings to run sessions in the app.",
        )
    return setting


def _normalise(turns: list[Turn]) -> list[Message]:
    """The transcript as the providers need it: starts with the user, strictly alternating."""
    messages: list[Message] = []
    for turn in turns:
        if messages and messages[-1]["role"] == turn.role:
            messages[-1]["content"] += "\n\n" + turn.content
        else:
            messages.append({"role": turn.role, "content": turn.content})
    if not messages or messages[0]["role"] != "user":
        messages.insert(0, {"role": "user", "content": "Let's begin."})
    return messages


@router.post("/sessions/open/{session_id}/chat", response_model=ChatOut)
def chat(
    session_id: UUID, body: ChatIn, request: Request, user_id: UserId, context: Context
) -> ChatOut | JSONResponse:
    schema_a = context.service.pending.peek(session_id)
    if schema_a is None:
        raise UnknownSessionError(session_id)
    setting = _require_setting(request, user_id)

    system = prompts.study(schema_a) if body.phase == "study" else prompts.assessment(schema_a)
    reply = complete(
        setting.provider, setting.api_key, setting.model,
        system=system, messages=_normalise(body.messages),
    )
    return ChatOut(reply=reply)


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def extract_json(text: str) -> dict[str, Any]:
    """The JSON object in a model reply, tolerating code fences and stray prose around it."""
    cleaned = _FENCE.sub("", text.strip())
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found")
    value = json.loads(cleaned[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


@router.post("/sessions/open/{session_id}/finish", response_model=IngestResponse)
def finish(
    session_id: UUID, body: FinishIn, request: Request, user_id: UserId, context: Context
) -> IngestResponse | JSONResponse:
    """Ask the model for the Schema B, then ingest it exactly as a pasted one would be.

    A reply that is not valid JSON is a 422 and leaves the session open: the learner can finish
    again without losing the transcript. A reply that is JSON but breaks the contract is
    reported by the same validator as a bad paste, every problem at once.
    """
    schema_a = context.service.pending.peek(session_id)
    if schema_a is None:
        raise UnknownSessionError(session_id)
    setting = _require_setting(request, user_id)

    messages = _normalise(body.messages)
    wrapup = prompts.wrapup(schema_a, completed_at=context.now)
    if messages[-1]["role"] == "user":
        messages[-1]["content"] += "\n\n---\n\n" + wrapup
    else:
        messages.append({"role": "user", "content": wrapup})

    reply = complete(
        setting.provider, setting.api_key, setting.model,
        system=prompts.assessment(schema_a), messages=messages, max_tokens=8192,
    )

    try:
        payload = extract_json(reply)
    except ValueError:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "type": "ModelOutputError",
                    "message": "The model's reply was not valid JSON. Press Finish to try again.",
                }
            },
        )
    return ingest_response(context.service.ingest(payload, now=context.now))
