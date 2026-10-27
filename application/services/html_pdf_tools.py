"""Renderização de HTML para PDF em A4 via Chromium headless."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Literal


PDF_PRINT_OVERRIDES = """
<style id="workflow-pdf-overrides">
@page { size: A4; margin: 0; }
@media print {
  body > [data-ied-page] { break-after: page; page-break-after: always; }
  body > [data-ied-page]:last-child { break-after: auto; page-break-after: auto; }
  .pagina > .nota { display: none !important; }
  h1, h2, h3, h4 { break-after: avoid-page; page-break-after: avoid; }
  table tr, li, figure, .card, .callout, .timeline-item, .bloco,
  .atividade, .pergunta, .destaque { break-inside: avoid; page-break-inside: avoid; }
}
</style>
"""


def _browser() -> str:
    browser = next(
        (item for item in ("chromium", "chromium-browser", "google-chrome") if shutil.which(item)),
        None,
    )
    if browser is None:
        raise FileNotFoundError("Nenhum navegador compatível foi encontrado")
    return browser


def _with_print_overrides(content: bytes, orientation: Literal["V", "H"]) -> bytes:
    if orientation not in {"V", "H"}:
        raise ValueError("orientation deve ser 'V' ou 'H'")
    html = content.decode("utf-8", errors="replace")
    size = "A4 landscape" if orientation == "H" else "A4"
    overrides = PDF_PRINT_OVERRIDES.replace("size: A4;", f"size: {size};")
    index = html.lower().find("</head>")
    return (f"{html[:index]}{overrides}{html[index:]}" if index >= 0 else f"{overrides}{html}").encode()


def render_html_to_pdf(content: bytes, orientation: Literal["V", "H"] = "V") -> bytes:
    """Retorna o PDF resultante, mantendo o HTML somente em diretório temporário."""
    with tempfile.TemporaryDirectory(prefix="html-to-pdf-") as directory:
        work_dir = Path(directory)
        html_path = work_dir / "source.html"
        pdf_path = work_dir / "output.pdf"
        profile_path = work_dir / "profile"
        html_path.write_bytes(_with_print_overrides(content, orientation))
        profile_path.mkdir()
        env = os.environ.copy()
        env.update({"XDG_CONFIG_HOME": str(profile_path), "XDG_CACHE_HOME": str(profile_path)})
        result = subprocess.run(
            [
                _browser(), "--headless", "--no-sandbox", "--disable-gpu",
                "--disable-dev-shm-usage", "--allow-file-access-from-files",
                f"--user-data-dir={profile_path}", f"--print-to-pdf={pdf_path}", str(html_path),
            ],
            capture_output=True, env=env, timeout=120, check=False,
        )
        if result.returncode != 0 or not pdf_path.is_file() or pdf_path.stat().st_size == 0:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(detail or "Não foi possível gerar o PDF")
        return pdf_path.read_bytes()
