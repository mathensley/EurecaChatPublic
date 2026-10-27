#!/bin/sh
set -e

cron

echo "Aguardando Postgres..."
until pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER"; do
  sleep 1
done

echo "Aplicando migrations do Postgres..."
uv run --no-sync python -m application.db.run_migrations

echo "Preparando checkpointer do LangGraph..."
uv run --no-sync python -m application.db.setup_checkpointer

echo "Sincronizando arquivos SQLite..."
uv run --no-sync python -m application.db.create_sqlite

echo "Preparando imagem do sandbox..."
uv run --no-sync python -m sandbox.ensure_image

echo "Iniciando aplicação..."
exec uv run --no-sync hypercorn application.app:sio_app --bind 0.0.0.0:8000 -w 1 -k asyncio
