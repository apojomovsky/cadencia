# Build context is the repo root (set in docker-compose.yml) so we can
# access both app/ and mcp/ source trees.

# Stage 1: install dependencies
FROM python:3.12.3-slim-bookworm AS builder
WORKDIR /build

RUN pip install --no-cache-dir uv

# Install the em_journal package (shared service layer)
COPY app/pyproject.toml /tmp/em_journal/pyproject.toml
COPY app/src/ /tmp/em_journal/src/
RUN uv pip install --system --no-cache /tmp/em_journal

# Install mcp package and its dependencies
COPY mcp/pyproject.toml ./
RUN mkdir -p src/em_journal_mcp && touch src/em_journal_mcp/__init__.py
RUN uv pip install --system --no-cache .

COPY mcp/src/ ./src/
RUN uv pip install --system --no-cache --no-deps .

# Stage 2: runtime image
FROM python:3.12.3-slim-bookworm AS runtime
WORKDIR /app

RUN useradd --create-home --shell /bin/bash --uid 1001 app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

RUN mkdir -p /data && chown app:app /data

USER app
EXPOSE 8081
CMD ["uvicorn", "em_journal_mcp.server:app", "--host", "0.0.0.0", "--port", "8081"]
