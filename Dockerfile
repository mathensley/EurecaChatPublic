FROM python:3.11-slim AS sandbox-rootfs

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/skills \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/matplotlib

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY sandbox/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

COPY src/tools/eureca/sandbox_files/ /skills/
WORKDIR /workspace


FROM debian:trixie-slim AS sandbox-archive

RUN apt-get update && apt-get install -y --no-install-recommends umoci ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN umoci init --layout /oci \
    && umoci new --image /oci:sandbox \
    && umoci unpack --image /oci:sandbox /bundle
COPY --from=sandbox-rootfs / /bundle/rootfs/
RUN umoci repack --image /oci:sandbox /bundle \
    && tar -C /oci -cf /sandbox.tar . \
    && sha256sum /sandbox.tar | cut -d ' ' -f1 > /sandbox.sha256


FROM node:22-slim AS frontend-builder

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY pyproject.toml /pyproject.toml
COPY frontend/ ./
RUN npm run build


FROM python:3.11-slim

ARG APP_VERSION=local

WORKDIR /EurecaAI

ENV PYTHONUNBUFFERED=1
ENV SQLITE_DIR=/EurecaAI/sqlite
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PATH="/EurecaAI/.venv/bin:$PATH"
ENV APP_VERSION=$APP_VERSION

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    ffmpeg \
    libpq-dev \
    postgresql-client \
    gcc \
    ca-certificates \
    tzdata \
    cron \
    poppler-utils \
    libreoffice \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.8.11 /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

RUN echo "*/5 * * * * cd /EurecaAI && /EurecaAI/.venv/bin/python ./src/tools/eureca/scripts_consolidacao_bd/main.py >> /var/log/script.log 2>&1" \
    > /etc/cron.d/eureca \
    && chmod 0644 /etc/cron.d/eureca \
    && crontab /etc/cron.d/eureca

COPY . .
COPY --from=frontend-builder /frontend/out ./frontend/out
COPY --from=sandbox-archive /sandbox.tar /opt/eureca-sandbox/sandbox.tar
COPY --from=sandbox-archive /sandbox.sha256 /opt/eureca-sandbox/sandbox.sha256

EXPOSE 8000 9464

RUN chmod +x entrypoint.sh

CMD ["./entrypoint.sh"]
