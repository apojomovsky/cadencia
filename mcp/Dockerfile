# Build context is the repo root (set in docker-compose.yml) so we can
# access both app/ and mcp/ source trees.

# Stage 1: install dependencies
FROM python:3.12.3-slim-bookworm AS builder
WORKDIR /build

COPY --from=ghcr.io/astral-sh/uv:0.5.25 /uv /bin/uv

# Install the cadencia package (shared service layer)
COPY app/pyproject.toml /tmp/cadencia/pyproject.toml
COPY app/src/ /tmp/cadencia/src/
RUN uv pip install --system --no-cache /tmp/cadencia

# Install mcp package and its dependencies
COPY mcp/pyproject.toml ./
RUN mkdir -p src/cadencia_mcp && touch src/cadencia_mcp/__init__.py
RUN uv pip install --system --no-cache .

COPY mcp/src/ ./src/
RUN uv pip install --system --no-cache --no-deps --reinstall .

# Stage 2: runtime image
FROM python:3.12.3-slim-bookworm AS runtime
WORKDIR /app

RUN useradd --create-home --shell /bin/bash --uid 1000 app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

RUN mkdir -p /data && chown app:app /data

USER app
EXPOSE 8081
CMD ["uvicorn", "cadencia_mcp.server:app", "--host", "0.0.0.0", "--port", "8081"]
