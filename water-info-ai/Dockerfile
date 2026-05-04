# ── Build ──────────────────────────────────────────────────────────────────────
ARG DOCKER_REGISTRY_PREFIX=docker.m.daocloud.io/library/
FROM ${DOCKER_REGISTRY_PREFIX}python:3.11-slim AS builder
WORKDIR /build

RUN pip install --no-cache-dir uv -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

ENV UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/

# Install deps first — only invalidated when pyproject.toml or uv.lock changes
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --no-install-project

# Then copy source code
COPY app ./app
RUN uv sync --no-dev

# ── Runtime ────────────────────────────────────────────────────────────────────
FROM ${DOCKER_REGISTRY_PREFIX}python:3.11-slim
WORKDIR /app

RUN groupadd -r appgroup && useradd -r -g appgroup appuser

COPY --from=builder /build/.venv /opt/venv
COPY --from=builder /build/app ./app

RUN mkdir -p /app/logs && chown -R appuser:appgroup /app
USER appuser

EXPOSE 8100

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]
