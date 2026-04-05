# Standalone OpenEnv image (python:3.11-slim) for HF Spaces / local docker run.
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY . /app/env
WORKDIR /app/env

ENV PYTHONPATH=/app/env
ENV ENABLE_WEB_INTERFACE=false

RUN uv sync --frozen --no-dev

ENV PATH="/app/env/.venv/bin:$PATH"

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

EXPOSE 8000

CMD ["sh", "-c", "uvicorn server.app:app --host 0.0.0.0 --port 8000"]
