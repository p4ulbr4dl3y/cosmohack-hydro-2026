# Multi-stage production Dockerfile using Python 3.13-slim and uv
FROM python:3.13-slim

# Install uv from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Working directory
WORKDIR /app

# Install basic runtime dependencies (curl for container healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Environment settings
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# Copy dependency manifests
COPY pyproject.toml uv.lock ./

# Install dependencies using uv sync
RUN uv sync --frozen --no-install-project

# Copy application source and data
COPY src/ ./src/
COPY hydrowatch_amur/ ./hydrowatch_amur/
COPY README.md ./

# Expose HTTP port
EXPOSE 8000

# Run FastAPI service
CMD ["uv", "run", "uvicorn", "src.service.app:app", "--host", "0.0.0.0", "--port", "8000"]
