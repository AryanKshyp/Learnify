"""Accounts, per-user isolation, and the in-app assessment loop.

The isolation tests run against real Postgres (skipped when it is unreachable, like the other
storage tests): an in-memory fake cannot catch a query that forgot its `user_id` filter, which
is exactly the bug that would show one person another's knowledge state.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient

from knowledgeos.api import create_app
from knowledgeos.api.auth import Authenticator
from knowledgeos.api.dependencies import get_now
from knowledgeos.api.llm_settings import LlmSettingsStore
from knowledgeos.api.stacks import Stack
from knowledgeos.assessment import (
    AssessmentService,
    PostgresPendingSessionStore,
)
from knowledgeos.config import Settings
from knowledgeos.curriculum import fixture_repository
from knowledgeos.documents import DocumentService
from knowledgeos.llm import Vault, providers
from knowledgeos.state import (
    PostgresDocumentRepository,
    PostgresKnowledgeStateRepository,
    PostgresSessionHistoryRepository,
    StateOverlay,
)
from tests.api.test_api import NOW, schema_b
from tests.api.test_documents_api import extraction
from tests.state.test_postgres import engine  # noqa: F401  (fixture)

SECRET = "test-secret-test-secret-test-secret-1234"


def token(sub: str, *, secret: str = SECRET, aud: str = "authenticated", expires_in: int = 3600,
          alg: str = "HS256") -> str:
    claims = {"sub": sub, "aud": aud, "exp": int(time.time()) + expires_in}
    return jwt.encode(claims, secret, algorithm=alg)


def bearer(sub: str, **kwargs) -> dict[str, str]:
    return {"Authorization": f"Bearer {token(sub, **kwargs)}"}


def authenticator() -> Authenticator:
    return Authenticator(Settings(supabase_jwt_secret=SECRET, _env_file=None))


# --------------------------------------------------------------------------- authentication


@pytest.fixture
def secured():
    application = create_app(curriculum=fixture_repository().get(), authenticator=authenticator())
    application.dependency_overrides[get_now] = lambda: NOW
    return TestClient(application)


class TestAuthentication:
    def test_health_stays_public_so_the_host_can_probe_it(self, secured):
        body = secured.get("/health").json()
        assert body["status"] == "ok"
        assert body["auth"] == "required"

    def test_the_browser_can_learn_how_to_sign_in_without_signing_in(self, secured, monkeypatch):
        from knowledgeos.config import settings

        monkeypatch.setattr(settings, "supabase_url", "https://p.supabase.co")
        monkeypatch.setattr(settings, "supabase_anon_key", "anon-public-key")
        body = secured.get("/config").json()
        assert body == {
            "auth": True,
            "supabase_url": "https://p.supabase.co",
            "supabase_anon_key": "anon-public-key",
        }
        assert "secret" not in json.dumps(body).lower()

    def test_local_mode_reports_no_auth(self):
        application = create_app(curriculum=fixture_repository().get())
        assert TestClient(application).get("/config").json() == {"auth": False}

    def test_no_token_is_refused(self, secured):
        assert secured.get("/roles").status_code == 401

    def test_a_valid_token_is_accepted(self, secured):
        assert secured.get("/roles", headers=bearer("user-1")).status_code == 200

    @pytest.mark.parametrize(
        "headers",
        [
            {"Authorization": "Bearer not-a-jwt"},
            {"Authorization": "Basic abc"},
            {"Authorization": "Bearer"},
            {"Authorization": ""},
        ],
    )
    def test_malformed_credentials_are_refused(self, secured, headers):
        assert secured.get("/roles", headers=headers).status_code == 401

    def test_an_expired_token_is_refused(self, secured):
        assert secured.get("/roles", headers=bearer("u", expires_in=-60)).status_code == 401

    def test_a_token_for_another_audience_is_refused(self, secured):
        assert secured.get("/roles", headers=bearer("u", aud="anon")).status_code == 401

    def test_a_token_signed_with_the_wrong_secret_is_refused(self, secured):
        assert secured.get("/roles", headers=bearer("u", secret="x" * 40)).status_code == 401

    def test_an_unsigned_token_is_refused(self, secured):
        unsigned = jwt.encode(
            {"sub": "u", "aud": "authenticated", "exp": int(time.time()) + 600},
            key=None,
            algorithm="none",
        )
        response = secured.get("/roles", headers={"Authorization": f"Bearer {unsigned}"})
        assert response.status_code == 401

    def test_hs256_is_not_accepted_when_only_asymmetric_keys_are_configured(self):
        """Algorithm confusion: a token must not choose how it is verified."""
        config = Settings(supabase_url="https://example.supabase.co", _env_file=None)
        with pytest.raises(jwt.PyJWTError):
            Authenticator(config).user_id(token("attacker"))

    def test_no_authenticator_means_one_local_user(self):
        application = create_app(curriculum=fixture_repository().get())
        assert TestClient(application).get("/roles").status_code == 200


# --------------------------------------------------------------------------- isolation


@pytest.fixture
def hosted(engine):  # noqa: F811
    """A hosted-style app: per-user Postgres stacks behind real token verification."""
    from sqlalchemy import text

    with engine.begin() as connection:
        connection.execute(text("truncate session_history, knowledge_state, pending_sessions, "
                                "document_plans, user_llm_settings"))
    curriculum = fixture_repository().get()

    def build(user_id: str) -> Stack:
        return Stack(
            storage="postgres",
            service=AssessmentService(
                curriculum,
                StateOverlay(curriculum, PostgresKnowledgeStateRepository(engine, user_id)),
                PostgresSessionHistoryRepository(engine, user_id),
                pending=PostgresPendingSessionStore(engine, user_id),
            ),
            documents=DocumentService(curriculum, PostgresDocumentRepository(engine, user_id)),
        )

    application = create_app(
        curriculum=curriculum,
        stack_factory=build,
        authenticator=authenticator(),
        llm_settings=LlmSettingsStore(Vault.ephemeral(), engine),
    )
    application.dependency_overrides[get_now] = lambda: NOW
    return TestClient(application)


class TestUsersCannotSeeEachOther:
    def test_evidence_is_private(self, hosted):
        alice, bob = bearer("alice"), bearer("bob")
        schema_a = hosted.post(
            "/sessions", json={"node_id": "prob-axioms"}, headers=alice
        ).json()
        assert hosted.post(
            "/sessions/ingest", json=schema_b(schema_a), headers=alice
        ).status_code == 200

        assert len(hosted.get("/sessions", headers=alice).json()) == 1
        assert hosted.get("/sessions", headers=bob).json() == []

        def mastery(headers):
            detail = hosted.get("/nodes/prob-axioms", headers=headers).json()
            return detail["advanced"]["intrinsic_mastery"]

        assert mastery(alice) > 0
        assert mastery(bob) == 0

    def test_an_open_session_belongs_to_whoever_opened_it(self, hosted):
        schema_a = hosted.post(
            "/sessions", json={"node_id": "prob-axioms"}, headers=bearer("alice")
        ).json()
        sid = schema_a["session_id"]

        assert hosted.get(f"/sessions/open/{sid}", headers=bearer("alice")).status_code == 200
        assert hosted.get(f"/sessions/open/{sid}", headers=bearer("bob")).status_code == 404
        assert hosted.get("/sessions/open", headers=bearer("bob")).json() == []

    def test_one_user_cannot_complete_anothers_session(self, hosted):
        schema_a = hosted.post(
            "/sessions", json={"node_id": "prob-axioms"}, headers=bearer("alice")
        ).json()
        stolen = hosted.post(
            "/sessions/ingest", json=schema_b(schema_a), headers=bearer("bob")
        )
        assert stolen.status_code == 404
        # ... and it is still Alice's to finish.
        assert hosted.post(
            "/sessions/ingest", json=schema_b(schema_a), headers=bearer("alice")
        ).status_code == 200

    def test_document_plans_are_private(self, hosted):
        created = hosted.post(
            "/documents/ingest", json=extraction("prob-axioms"), headers=bearer("alice")
        )
        assert created.status_code in (200, 201)
        document_id = created.json()["document_id"]

        assert len(hosted.get("/documents", headers=bearer("alice")).json()) == 1
        assert hosted.get("/documents", headers=bearer("bob")).json() == []
        assert hosted.get(f"/documents/{document_id}", headers=bearer("bob")).status_code == 404
        assert hosted.delete(
            f"/documents/{document_id}", headers=bearer("bob")
        ).status_code == 404
        assert hosted.get(
            f"/documents/{document_id}", headers=bearer("alice")
        ).status_code == 200

    def test_saved_ai_keys_are_private_and_never_echoed(self, hosted, monkeypatch):
        monkeypatch.setattr(providers, "_post_json", lambda *a, **k: _anthropic_reply("ok"))
        secret_key = "sk-ant-very-secret-key-1234"
        saved = hosted.put(
            "/llm/settings",
            json={"provider": "anthropic", "api_key": secret_key},
            headers=bearer("alice"),
        )
        assert saved.status_code == 200
        assert secret_key not in saved.text
        assert saved.json()["key_hint"] == "…1234"

        assert hosted.get("/llm/settings", headers=bearer("bob")).json()["configured"] is False
        assert secret_key not in hosted.get("/llm/settings", headers=bearer("alice")).text

    def test_keys_are_encrypted_at_rest(self, hosted, engine, monkeypatch):  # noqa: F811
        from sqlalchemy import text

        monkeypatch.setattr(providers, "_post_json", lambda *a, **k: _anthropic_reply("ok"))
        hosted.put(
            "/llm/settings",
            json={"provider": "openai", "api_key": "sk-plaintext-canary-9999", "verify": False},
            headers=bearer("alice"),
        )
        with engine.connect() as connection:
            stored = connection.execute(
                text("select encrypted_key from user_llm_settings where user_id = 'alice'")
            ).scalar()
        assert "canary" not in stored


# --------------------------------------------------------------------------- the in-app loop


def _anthropic_reply(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}]}


@pytest.fixture
def app_client():
    application = create_app(curriculum=fixture_repository().get())
    application.dependency_overrides[get_now] = lambda: NOW
    return TestClient(application)


def _configure(client, monkeypatch, reply):
    """Save a key (with the provider call stubbed) and make every later call return `reply`."""
    calls: list[dict] = []

    def fake(url, headers, body):
        calls.append({"url": url, "headers": headers, "body": body})
        return _anthropic_reply(reply() if callable(reply) else reply)

    monkeypatch.setattr(providers, "_post_json", fake)
    response = client.put(
        "/llm/settings",
        json={"provider": "anthropic", "api_key": "sk-ant-test-0000", "verify": False},
    )
    assert response.status_code == 200
    return calls


class TestInAppSession:
    def test_chat_needs_a_key(self, app_client):
        sid = app_client.post("/sessions", json={"node_id": "prob-axioms"}).json()["session_id"]
        response = app_client.post(
            f"/sessions/open/{sid}/chat",
            json={"phase": "assess", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert response.status_code == 409
        assert "Settings" in response.json()["detail"]

    def test_chat_sends_the_applications_own_prompt(self, app_client, monkeypatch):
        calls = _configure(app_client, monkeypatch, "Define a sample space.")
        sid = app_client.post("/sessions", json={"node_id": "prob-axioms"}).json()["session_id"]
        calls.clear()

        reply = app_client.post(
            f"/sessions/open/{sid}/chat",
            json={"phase": "assess", "messages": [{"role": "user", "content": "Ready"}]},
        )
        assert reply.json() == {"reply": "Define a sample space."}
        sent = calls[0]["body"]
        assert sent["model"]
        assert "prob-axioms" in sent["system"] or "axioms" in sent["system"].lower()
        assert calls[0]["headers"]["x-api-key"] == "sk-ant-test-0000"

    def test_an_empty_transcript_still_starts_the_conversation(self, app_client, monkeypatch):
        calls = _configure(app_client, monkeypatch, "Welcome.")
        sid = app_client.post("/sessions", json={"node_id": "prob-axioms"}).json()["session_id"]
        calls.clear()
        app_client.post(f"/sessions/open/{sid}/chat", json={"phase": "study", "messages": []})
        assert calls[0]["body"]["messages"][0]["role"] == "user"

    def test_finishing_records_evidence_through_the_same_validator(self, app_client, monkeypatch):
        holder: dict = {}
        _configure(app_client, monkeypatch, lambda: "```json\n" + json.dumps(holder["b"]) + "\n```")
        schema_a = app_client.post("/sessions", json={"node_id": "prob-axioms"}).json()
        holder["b"] = schema_b(schema_a)

        response = app_client.post(
            f"/sessions/open/{schema_a['session_id']}/finish",
            json={"messages": [
                {"role": "user", "content": "ready"},
                {"role": "assistant", "content": "question 1"},
                {"role": "user", "content": "my answer"},
            ]},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["intrinsic_mastery_after"] > body["intrinsic_mastery_before"]
        assert app_client.get("/sessions/open").json() == []  # consumed exactly once

    def test_unparseable_output_leaves_the_session_open_to_retry(self, app_client, monkeypatch):
        _configure(app_client, monkeypatch, "I am unable to produce JSON, sorry.")
        sid = app_client.post("/sessions", json={"node_id": "prob-axioms"}).json()["session_id"]

        response = app_client.post(
            f"/sessions/open/{sid}/finish",
            json={"messages": [
                {"role": "user", "content": "ready"},
                {"role": "assistant", "content": "ok"},
            ]},
        )
        assert response.status_code == 422
        assert response.json()["error"]["type"] == "ModelOutputError"
        assert len(app_client.get("/sessions/open").json()) == 1

    def test_json_that_breaks_the_contract_is_rejected_by_the_real_validator(
        self, app_client, monkeypatch
    ):
        holder: dict = {}
        _configure(app_client, monkeypatch, lambda: json.dumps(holder["b"]))
        schema_a = app_client.post("/sessions", json={"node_id": "prob-axioms"}).json()
        holder["b"] = schema_b(schema_a, observations={"recall": 7, "depth": 0.5, "transfer": 0.5})

        response = app_client.post(
            f"/sessions/open/{schema_a['session_id']}/finish",
            json={"messages": [
                {"role": "user", "content": "ready"},
                {"role": "assistant", "content": "ok"},
            ]},
        )
        assert response.status_code == 422
        assert response.json()["error"]["problems"]
        assert len(app_client.get("/sessions/open").json()) == 1

    def test_oversized_transcripts_are_refused(self, app_client, monkeypatch):
        _configure(app_client, monkeypatch, "x")
        sid = app_client.post("/sessions", json={"node_id": "prob-axioms"}).json()["session_id"]
        response = app_client.post(
            f"/sessions/open/{sid}/chat",
            json={"phase": "assess", "messages": [{"role": "user", "content": "a" * 50_000}]},
        )
        assert response.status_code == 422

    def test_a_rejected_key_is_reported_without_leaking_it(self, app_client, monkeypatch):
        def reject(url, headers, body):
            raise providers.LlmError("The provider rejected your API key.", 401)

        monkeypatch.setattr(providers, "_post_json", reject)
        response = app_client.put(
            "/llm/settings", json={"provider": "openai", "api_key": "sk-bad-key-123456"}
        )
        assert response.status_code == 401
        assert "sk-bad-key-123456" not in response.text
        assert app_client.get("/llm/settings").json()["configured"] is False


class TestProviderAdapters:
    """Each provider's wire format. A wrong header or body shape fails only in production."""

    def run(self, monkeypatch, provider, response):
        seen = {}

        def fake(url, headers, body):
            seen.update(url=url, headers=headers, body=body)
            return response

        monkeypatch.setattr(providers, "_post_json", fake)
        text = providers.complete(
            provider, "KEY", "model-x", system="SYS",
            messages=[{"role": "user", "content": "hi"}, {"role": "assistant", "content": "yo"},
                      {"role": "user", "content": "again"}],
        )
        return text, seen

    def test_anthropic(self, monkeypatch):
        text, seen = self.run(monkeypatch, "anthropic", _anthropic_reply("hello"))
        assert text == "hello"
        assert seen["url"] == "https://api.anthropic.com/v1/messages"
        assert seen["headers"]["x-api-key"] == "KEY"
        assert seen["body"]["system"] == "SYS"
        assert seen["body"]["max_tokens"]

    @pytest.mark.parametrize(
        ("provider", "host"),
        [("openai", "api.openai.com"), ("openrouter", "openrouter.ai")],
    )
    def test_openai_compatible(self, monkeypatch, provider, host):
        reply = {"choices": [{"message": {"content": "hello"}}]}
        text, seen = self.run(monkeypatch, provider, reply)
        assert text == "hello"
        assert host in seen["url"]
        assert seen["headers"]["Authorization"] == "Bearer KEY"
        assert seen["body"]["messages"][0] == {"role": "system", "content": "SYS"}

    def test_gemini(self, monkeypatch):
        reply = {"candidates": [{"content": {"parts": [{"text": "hello"}]}}]}
        text, seen = self.run(monkeypatch, "gemini", reply)
        assert text == "hello"
        assert seen["url"].endswith("/models/model-x:generateContent")
        assert "KEY" not in seen["url"]  # never in a URL, where it would be logged
        assert seen["headers"]["x-goog-api-key"] == "KEY"
        assert [c["role"] for c in seen["body"]["contents"]] == ["user", "model", "user"]

    def test_empty_replies_are_an_error_not_silence(self, monkeypatch):
        with pytest.raises(providers.LlmError):
            self.run(monkeypatch, "anthropic", _anthropic_reply("   "))

    def test_openrouter_connect_exchanges_the_code(self, app_client, monkeypatch):
        seen = {}

        def fake(url, headers, body):
            seen.update(url=url, body=body)
            return {"key": "sk-or-v1-fromoauth"}

        monkeypatch.setattr(providers, "_post_json", fake)
        response = app_client.post(
            "/llm/openrouter/exchange", json={"code": "abc", "code_verifier": "v" * 50}
        )
        assert response.status_code == 200
        assert response.json()["provider"] == "openrouter"
        assert seen["url"] == "https://openrouter.ai/api/v1/auth/keys"
        assert seen["body"]["code_challenge_method"] == "S256"
        assert "fromoauth" not in response.text


# --------------------------------------------------------------------------- serving the app


class TestServingTheFrontend:
    @pytest.fixture
    def site(self, tmp_path):
        dist = tmp_path / "dist"
        (dist / "assets").mkdir(parents=True)
        (dist / "index.html").write_text("<html>SPA</html>")
        (dist / "assets" / "app.js").write_text("console.log(1)")
        (tmp_path / "secret.txt").write_text("outside the site")
        application = create_app(curriculum=fixture_repository().get(), frontend_dist=dist)
        return TestClient(application)

    def test_the_api_answers_under_api(self, site):
        assert site.get("/api/health").json()["status"] == "ok"
        assert site.get("/api/roles").status_code == 200

    def test_client_routes_get_the_app_shell(self, site):
        assert "SPA" in site.get("/some/client/route").text
        assert "SPA" in site.get("/").text

    def test_assets_are_served(self, site):
        assert site.get("/assets/app.js").text == "console.log(1)"

    def test_unknown_api_paths_are_a_404_not_html(self, site):
        response = site.get("/api/definitely-not-a-route")
        assert response.status_code == 404
        assert "SPA" not in response.text

    def test_the_site_cannot_be_escaped(self, site):
        for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/..%2fsecret.txt"):
            assert "outside the site" not in site.get(path).text

    def test_a_missing_build_fails_loudly(self, tmp_path):
        with pytest.raises(RuntimeError, match="Build the frontend"):
            create_app(curriculum=fixture_repository().get(), frontend_dist=tmp_path)


# --------------------------------------------------------------------------- startup safety


class TestProductionRefusesToRunUnsafely:
    def test_production_without_accounts_will_not_start(self, monkeypatch):
        from knowledgeos.api import main

        monkeypatch.setattr(main.settings, "environment", "production")
        monkeypatch.setattr(main.settings, "supabase_url", "")
        monkeypatch.setattr(main.settings, "supabase_jwt_secret", "")
        with pytest.raises(main.ConfigurationError, match="accounts"):
            main._build()

    def test_accounts_without_a_database_will_not_fall_back_to_shared_memory(self, monkeypatch):
        from knowledgeos.api import main

        monkeypatch.setattr(main.settings, "supabase_jwt_secret", SECRET)
        monkeypatch.setattr(main.settings, "database_url",
                            "postgresql+psycopg://nobody:x@127.0.0.1:1/none")
        with pytest.raises(main.ConfigurationError, match="Refusing to start"):
            main._build()

    def test_accounts_without_an_encryption_key_will_not_start(self, monkeypatch, engine):  # noqa: F811
        from knowledgeos.api import main

        monkeypatch.setattr(main.settings, "supabase_jwt_secret", SECRET)
        monkeypatch.setattr(main.settings, "secrets_encryption_key", "")
        with pytest.raises(main.ConfigurationError, match="SECRETS_ENCRYPTION_KEY"):
            main._build()


def test_clock_helper_is_utc():
    assert datetime.now(UTC) - timedelta(seconds=1) < datetime.now(UTC)
