# One image, one process: the API serves the built web app on the same origin.
#
#   docker build -t learnify .
#   docker run -p 8000:8000 --env-file backend/.env learnify
#
# Migrations run on every start, so a new deploy upgrades its own database.

# ---- build the web app
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- run
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

# The curriculum is located relative to the repo root (backend/../curriculum_graph.json), so the
# layout is kept: /app/backend, /app/curriculum_graph.json, /app/frontend/dist.
WORKDIR /app
COPY backend/ /app/backend/
COPY curriculum_graph.json curriculum_fixture.json /app/
# Editable, so the package stays at /app/backend and the relative curriculum path still resolves.
RUN pip install -e /app/backend
COPY --from=web /web/dist /app/frontend/dist

RUN useradd --create-home --uid 10001 app && chown -R app /app
USER app
WORKDIR /app/backend

ENV ENVIRONMENT=production \
    FRONTEND_DIST=/app/frontend/dist \
    PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health', timeout=4)"

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn knowledgeos.api.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
