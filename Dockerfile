FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# Working directory
WORKDIR /app

# Install basic runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libexpat1 \
    libgomp1 \
    fonts-dejavu-core \
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
COPY config.yaml ./
COPY submission.csv ./
COPY predictions/ ./predictions/
COPY README.md ./

# Expose HTTP port
EXPOSE 8000

# Run FastAPI service
CMD ["uv", "run", "uvicorn", "src.service.app:app", "--host", "0.0.0.0", "--port", "8000"]
