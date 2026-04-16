# Stage 1: install dependencies
FROM python:3.12.3-slim-bookworm AS builder
WORKDIR /build

COPY --from=ghcr.io/astral-sh/uv:0.5.25 /uv /bin/uv

COPY pyproject.toml ./
# Minimal package stub so uv can resolve the package itself
RUN mkdir -p src/cadencia && touch src/cadencia/__init__.py
RUN uv pip install --system --no-cache ".[dev]"

# Install source properly now that deps are cached
COPY src/ ./src/
RUN uv pip install --system --no-cache --no-deps --reinstall .

# Stage 2: runtime image
FROM python:3.12.3-slim-bookworm AS runtime
WORKDIR /app

RUN useradd --create-home --shell /bin/bash --uid 1000 app

# Copy installed packages and runtime binaries from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

# Create mount points with correct ownership before switching user
RUN mkdir -p /data /backup-status && chown app:app /data /backup-status

# pyproject.toml for pytest config; tests for running inside the container
COPY pyproject.toml ./
COPY tests/ ./tests/

USER app
EXPOSE 8080
CMD ["uvicorn", "cadencia.main:app", "--host", "0.0.0.0", "--port", "8080"]
