"""Conversão direta de PDF para HTML editável.

Este endpoint é deliberadamente independente do fluxo de agentes/workflows.
"""

import base64
import html
import io
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import fitz
from quart import Blueprint, jsonify, request, Response

bp = Blueprint("pdf_conversion", __name__, url_prefix="/api")


def _css_text(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "-", value)


def _pdf_to_html(pdf_bytes: bytes, title: str) -> str:
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages: list[str] = []
    try:
        for index, page in enumerate(document):
            rect = page.rect
            # 96 CSS px por polegada, mesma unidade usada pelo editor.
            scale = 96 / 72
            matrix = fitz.Matrix(scale, scale)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            image = base64.b64encode(pixmap.tobytes("png")).decode("ascii")
            spans: list[str] = []
            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    text = "".join(span.get("text", "") for span in line.get("spans", [])).strip()
                    if not text:
                        continue
                    x0, y0, x1, y1 = line["bbox"]
                    style = (
                        f"left:{x0 * scale:.3f}px;top:{y0 * scale:.3f}px;"
                        f"width:{max(1, (x1-x0) * scale):.3f}px;"
                        f"font-size:{max(1, line['spans'][0].get('size', 10) * scale):.3f}px;"
                    )
                    spans.append(
                        f'<div class="pdf-text" data-ied-layer="{len(spans)}" '
                        f'contenteditable="true" style="{style}">{html.escape(text)}</div>'
                    )
            width, height = rect.width * scale, rect.height * scale
            pages.append(
                f'<section class="pdf-page" style="width:{width:.3f}px;height:{height:.3f}px;">'
                f'<img class="pdf-background" src="data:image/png;base64,{image}" alt="">'
                f'{"".join(spans)}</section>'
            )
    finally:
        document.close()

    safe_title = html.escape(title or "Documento PDF")
    return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>{safe_title}</title>
<style>html,body{{margin:0;background:#e5e5e5;font-family:Arial,sans-serif}}body{{padding:20px 0}}
.pdf-page{{position:relative;margin:0 auto 20px;background:#fff;overflow:hidden;box-shadow:0 2px 10px #0005}}
.pdf-background{{position:absolute;inset:0;width:100%;height:100%;object-fit:fill;pointer-events:none}}
.pdf-text{{position:absolute;z-index:1;line-height:1.15;white-space:pre-wrap;overflow:hidden;outline:none}}
.pdf-text:focus{{box-shadow:0 0 0 2px #2563eb55;background:#fff8}}
.pdf-actions{{position:fixed;right:16px;top:16px;z-index:5;display:flex;gap:8px}}
.pdf-actions button{{border:0;border-radius:8px;padding:9px 13px;background:#155e75;color:#fff;font-weight:700;cursor:pointer}}</style></head><body>
<div class="pdf-actions"><button id="save-html" type="button">Salvar HTML</button></div>
{"".join(pages)}
<script>(function(){{
  function save(){{
    document.querySelectorAll('[contenteditable]').forEach(function(el){{el.removeAttribute('contenteditable')}});
    document.querySelectorAll('.pdf-actions').forEach(function(el){{el.remove()}});
    var blob=new Blob(['<!doctype html>\\n'+document.documentElement.outerHTML],{{type:'text/html;charset=utf-8'}});
    var a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download={html.escape(title)!r}+'.html';a.click();
  }}
  document.getElementById('save-html').addEventListener('click',save);
  document.addEventListener('keydown',function(e){{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='s'){{e.preventDefault();save()}}}});
}})();</script></body></html>'''


def _pdf_to_html_poppler(pdf_bytes: bytes, title: str) -> str:
    """Converte separando o raster de fundo do texto editável."""
    if shutil.which("pdftohtml") is None:
        raise RuntimeError("pdftohtml não está instalado")

    page_re = re.compile(
        r'<div id="page(\d+)-div" style="[^"]*?width:(\d+(?:\.\d+)?)px;height:(\d+(?:\.\d+)?)px;[^"]*">(.*?)(?=<div id="page\d+-div|</body>)',
        re.S,
    )
    image_re = re.compile(r'<img\b[^>]*?src="(data:[^"]+)"[^>]*/?>', re.S)
    paragraph_re = re.compile(r'<p\b[^>]*>.*?</p>', re.S)
    top_re = re.compile(r'top:(-?\d+(?:\.\d+)?)px')
    a4_width, a4_height = 793.700787, 1122.519685

    with tempfile.TemporaryDirectory() as directory:
        pdf_path = Path(directory) / "input.pdf"
        output_base = Path(directory) / "converted"
        pdf_path.write_bytes(pdf_bytes)
        result = subprocess.run(
            ["pdftohtml", "-c", "-s", "-dataurls", "-zoom", "2", str(pdf_path), str(output_base)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "pdftohtml falhou")
        raw_html = output_base.with_name("converted-html.html").read_text(encoding="utf-8")

    # O pdftohtml gera as classes .ftXX com a tipografia e cores originais.
    # Mantê-las é essencial para o HTML ter a mesma aparência do PDF.
    source_styles = "".join(re.findall(r"<style[^>]*>.*?</style>", raw_html, re.S))

    pages = []
    for match in page_re.finditer(raw_html):
        number, raw_width, raw_height, body = match.groups()
        width, height = float(raw_width), float(raw_height)
        image = image_re.search(body)
        if not image:
            continue
        background = image.group(1)
        body = body[:image.start()] + body[image.end():]
        texts = []
        for paragraph in paragraph_re.finditer(body):
            content = re.sub(
                r"<p\b", '<p contenteditable="true" spellcheck="false"', paragraph.group(0), count=1,
            )
            top_match = top_re.search(content)
            texts.append((float(top_match.group(1)) if top_match else 0.0, content))

        scale = a4_width / width
        slice_height = a4_height / scale
        sheet_count = max(1, int((height - slice_height * 0.01 + slice_height - 1) // slice_height))
        for sheet in range(sheet_count):
            offset = sheet * slice_height
            sheet_text = []
            for top, content in texts:
                if int(top // slice_height) != sheet and sheet != sheet_count - 1:
                    continue
                if offset:
                    content = top_re.sub(f"top:{max(0, top - offset):.6f}px", content, count=1)
                sheet_text.append(content)
            pages.append(
                f'<section class="pdf-page" data-page="{number}"><div class="pdf-page-content" '
                f'style="width:{width:.3f}px;height:{slice_height:.3f}px;transform:scale({scale:.6f});'
                f'background-image:url(&quot;{background}&quot;);background-size:{width:.3f}px {height:.3f}px;'
                f'background-position:0 -{offset:.3f}px;">{"".join(sheet_text)}</div></section>'
            )

    safe_title = html.escape(title or "Documento PDF")
    return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>{safe_title}</title>{source_styles}
<style>html,body{{margin:0;background:#e5e5e5;font-family:Arial,sans-serif}}body{{padding:20px 0;overflow:auto}}
.pdf-page{{position:relative;width:210mm;height:297mm;margin:0 auto 20px;background:#fff;overflow:hidden;box-shadow:0 2px 10px #0005}}
.pdf-page-content{{position:absolute;top:0;left:0;overflow:hidden;transform-origin:0 0;background-repeat:no-repeat}}
.pdf-page-content p{{outline:none;cursor:text}}
.pdf-page-content p:focus{{box-shadow:0 0 0 2px #2563eb55;background:#fff8}}
.pdf-actions{{position:fixed;right:16px;top:16px;z-index:5}}.pdf-actions button{{border:0;border-radius:8px;padding:9px 13px;background:#155e75;color:#fff;font-weight:700;cursor:pointer}}</style></head><body>
<div class="pdf-actions"><button id="save-html" type="button">Salvar HTML</button></div>{"".join(pages)}
<script>(function(){{function save(){{document.querySelectorAll('.pdf-actions').forEach(function(e){{e.remove()}});document.querySelectorAll('[contenteditable]').forEach(function(e){{e.removeAttribute('contenteditable')}});var b=new Blob(['<!doctype html>\\n'+document.documentElement.outerHTML],{{type:'text/html;charset=utf-8'}});var a=document.createElement('a');a.href=URL.createObjectURL(b);a.download={html.escape(title)!r}+'.html';a.click()}}document.getElementById('save-html').onclick=save;}})();</script></body></html>'''


@bp.post("/pdf-to-html")
async def pdf_to_html():
    uploaded = (await request.files).get("file")
    if uploaded is None or not uploaded.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Envie um arquivo PDF no campo 'file'"}), 400
    data = uploaded.read()
    if not data:
        return jsonify({"error": "O arquivo PDF está vazio"}), 400
    try:
        result = _pdf_to_html_poppler(data, uploaded.filename.rsplit(".", 1)[0])
    except (fitz.FileDataError, ValueError, RuntimeError):
        return jsonify({"error": "Não foi possível ler o PDF"}), 422
    return Response(result, content_type="text/html; charset=utf-8")
