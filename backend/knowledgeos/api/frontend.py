"""Serve the built frontend from the API, so the product is one process on one origin.

The browser app calls `/api/...`; in production there is no dev-server proxy, so the API is also
mounted under `/api` here and everything else falls through to the single-page app.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


class StripApiPrefix:
    """ASGI middleware: `/api/x` is served as `/x`.

    The browser always calls `/api/...` (in development Vite proxies and strips it). In
    production there is no proxy, so the prefix is removed here and the same routes answer.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] in ("http", "websocket"):
            path = scope["path"]
            if path == "/api" or path.startswith("/api/"):
                scope = dict(scope)
                scope["path"] = path[4:] or "/"
                scope["raw_path"] = scope.get("raw_path", b"")[4:] or b"/"
                scope["via_api"] = True
        await self.app(scope, receive, send)


def mount_frontend(app: FastAPI, dist: Path) -> None:
    index = dist / "index.html"
    if not index.is_file():
        raise RuntimeError(
            f"FRONTEND_DIST is set to {dist} but there is no index.html there. "
            "Build the frontend first (npm run build in frontend/)."
        )

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    app.add_middleware(StripApiPrefix)

    # Registered last so it never shadows an API route; unknown paths get the SPA shell and the
    # client router takes over. API paths that do not exist must still 404 rather than be
    # answered with HTML.
    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str, request: Request) -> FileResponse:
        if request.scope.get("via_api"):
            raise HTTPException(404, "No such API route.")
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)
