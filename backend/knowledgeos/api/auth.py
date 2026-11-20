"""Who is calling.

Hosted deployments sit behind Supabase Auth: the browser signs in with supabase-js and sends the
resulting access token as `Authorization: Bearer ...`. This module verifies that token and
returns the user id (`sub`), which every repository is then scoped to.

Verification is local - a signature check against Supabase's published keys - so a request
costs no network round trip once the keys are cached. Both signing schemes Supabase uses are
supported: asymmetric keys via the project's JWKS endpoint (current projects) and the legacy
shared HS256 secret.

Without any Supabase configuration the application is single-user and every request is the
user `LOCAL_USER`. A production deployment REFUSES to start in that state (see `main.py`), so
forgetting to configure auth can never silently publish one shared account to the internet.
"""

from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from jwt import PyJWKClient

from knowledgeos.config import Settings, settings
from knowledgeos.state.tables import LOCAL_USER

AUDIENCE = "authenticated"


class Authenticator:
    """Verifies Supabase access tokens."""

    def __init__(self, config: Settings = settings) -> None:
        self._secret = config.supabase_jwt_secret
        self._jwks = (
            PyJWKClient(
                f"{config.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json",
                cache_keys=True,
            )
            if config.supabase_url
            else None
        )

    def user_id(self, token: str) -> str:
        """The verified user id, or `jwt.PyJWTError`."""
        header = jwt.get_unverified_header(token)
        algorithm = header.get("alg", "")
        if algorithm == "HS256":
            # Only honoured when a legacy secret is configured; never trust the token's own
            # claim about how it should be verified.
            if not self._secret:
                raise jwt.InvalidAlgorithmError("HS256 tokens are not accepted here")
            key, algorithms = self._secret, ["HS256"]
        else:
            if self._jwks is None:
                raise jwt.InvalidAlgorithmError("asymmetric tokens are not accepted here")
            key = self._jwks.get_signing_key_from_jwt(token).key
            algorithms = ["ES256", "RS256"]
        claims = jwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience=AUDIENCE,
            options={"require": ["sub", "exp"]},
        )
        return str(claims["sub"])


def get_authenticator(request: Request) -> Authenticator | None:
    return request.app.state.authenticator


def get_user_id(
    authenticator: Annotated[Authenticator | None, Depends(get_authenticator)],
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    if authenticator is None:
        return LOCAL_USER
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Sign in to continue.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return authenticator.user_id(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Your session has expired or is invalid. Sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


UserId = Annotated[str, Depends(get_user_id)]
