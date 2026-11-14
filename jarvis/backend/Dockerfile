# Build context: the jarvis/ directory (see docker-compose.yml).
FROM python:3.13-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/src ./src
RUN uv sync --frozen --no-dev
COPY config /app/config
RUN useradd --system --uid 10001 jarvis
USER jarvis
ENV PATH="/app/backend/.venv/bin:$PATH" JARVIS_CONFIG=/app/config/default.yaml
EXPOSE 8000
ENTRYPOINT ["python", "-m", "jarvis.service"]
