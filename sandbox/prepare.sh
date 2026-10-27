#!/usr/bin/env bash
set -euo pipefail

# Opcional: o entrypoint já prepara a imagem automaticamente a cada deploy.
docker compose exec -T backend python -m sandbox.ensure_image
