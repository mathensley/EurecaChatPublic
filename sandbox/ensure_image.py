"""Carrega a imagem OCI embutida no backend no cache persistente do microsandbox."""

import asyncio
import os
from pathlib import Path

from microsandbox import Image, ImageNotFoundError


IMAGE_NAME = "eureca-sandbox:0.1.0"
ARCHIVE_DIR = Path("/opt/eureca-sandbox")


async def ensure_image() -> None:
    archive = ARCHIVE_DIR / "sandbox.tar"
    expected_digest = (ARCHIVE_DIR / "sandbox.sha256").read_text(encoding="ascii").strip()
    cache_dir = Path(os.environ.get("MSB_HOME", "/EurecaAI/microsandbox"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    marker = cache_dir / "eureca-sandbox.sha256"

    try:
        await Image.get(IMAGE_NAME)
        present = True
    except ImageNotFoundError:
        present = False

    if present and marker.is_file() and marker.read_text(encoding="ascii").strip() == expected_digest:
        print(f"Imagem {IMAGE_NAME} já está no cache do microsandbox.", flush=True)
        return

    print(f"Carregando imagem {IMAGE_NAME} no microsandbox...", flush=True)
    await Image.load(str(archive), tag=IMAGE_NAME)
    marker.write_text(expected_digest + "\n", encoding="ascii")
    print(f"Imagem {IMAGE_NAME} pronta.", flush=True)


if __name__ == "__main__":
    asyncio.run(ensure_image())
