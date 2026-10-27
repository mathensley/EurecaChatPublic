"""
pdf_helpers.py
----------------
Biblioteca de apoio para geração de PDFs "bonitos" com reportlab.

Objetivo: dar ao agente um conjunto de blocos prontos (paleta, tipografia,
tabelas, capa, rodapé numerado) para que ele NÃO precise reinventar
estilo a cada script gerado. O agente escreve o "conteúdo"
(quais seções, quais dados) e importa isso aqui para cuidar da "forma".

Uso típico dentro do sandbox:

    from pdf_helpers import (
        PALETA, obter_estilos, tabela_estilizada,
        construir_documento, paragrafo_capa
    )

    estilos = obter_estilos()
    elementos = []
    elementos += paragrafo_capa("Relatório Mensal", "Setembro/2026")
    elementos.append(Paragraph("Resumo", estilos["H1"]))
    elementos.append(Paragraph("Texto do corpo...", estilos["Corpo"]))
    elementos.append(tabela_estilizada(
        cabecalho=["Item", "Valor"],
        linhas=[["Receita", "R$ 1.200"], ["Custo", "R$ 800"]],
    ))
    construir_documento("saida.pdf", elementos, titulo_doc="Relatório Mensal")

IMPORTANTE (evita os erros mais comuns):
- NUNCA use caracteres unicode de subscrito/sobrescrito (₀₁₂ ⁰¹²) — as
  fontes core do reportlab não têm esses glifos e viram um quadrado preto.
  Use as tags <sub> e <super> dentro de um Paragraph (ex: "H<sub>2</sub>O").
- Prefira SEMPRE Platypus (SimpleDocTemplate + Paragraph/Table/Spacer) a
  canvas.drawString cru. Canvas cru não quebra texto automaticamente e
  facilmente estoura a página.
- Use só fontes core (Helvetica, Times-Roman, Courier e variantes bold/
  italic) a menos que registre uma fonte TTF explicitamente — qualquer
  outro nome de fonte quebra silenciosamente ou lança exceção.
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    Image as _RLImage,
)
from PIL import Image as _PILImage
from pathlib import Path
import base64

# ---------------------------------------------------------------------------
# Paleta de cores — deliberadamente curta. Um documento com 2-3 cores bem
# usadas parece mais profissional do que um com muitas cores soltas.
# ---------------------------------------------------------------------------
PALETA = {
    "primaria": colors.HexColor("#1F3A5F"),   # azul petróleo — títulos, header de tabela
    "secundaria": colors.HexColor("#4A7C9E"), # azul mais claro — acentos, subtítulos
    "texto": colors.HexColor("#222222"),      # quase preto — corpo de texto
    "texto_claro": colors.HexColor("#666666"),# cinza — legendas, rodapé
    "linha": colors.HexColor("#D8DEE4"),      # cinza claro — bordas, divisores
    "fundo_alt": colors.HexColor("#F4F6F8"),  # cinza muito claro — linhas zebradas
    "branco": colors.white,
}

MARGEM = 2.2 * cm
LARGURA_UTIL = A4[0] - 2 * MARGEM       # ~16.6cm — largura de conteúdo disponível
ALTURA_MAX_IMAGEM = 18 * cm             # teto pra uma imagem não estourar a página sozinha


def imagem_ajustada(caminho: str, largura_max_cm: float = None, altura_max_cm: float = None) -> _RLImage:
    """
    Abre uma imagem (PNG/JPEG/...) e devolve um flowable Image do
    reportlab já redimensionado pra caber na página, MANTENDO a
    proporção original — evita o erro comum de imagem esticada/achatada
    por width/height chutados na mão.

    Por padrão, usa a largura útil da página (respeitando as margens de
    `construir_documento`) e um teto de altura de 18cm. Passe
    largura_max_cm/altura_max_cm pra restringir mais (ex: imagem menor,
    lado a lado com texto).

    Uso:
        elementos.append(imagem_ajustada("grafico.png"))
        elementos.append(imagem_ajustada("logo.png", largura_max_cm=5))
    """
    largura_max = (largura_max_cm * cm) if largura_max_cm else LARGURA_UTIL
    altura_max = (altura_max_cm * cm) if altura_max_cm else ALTURA_MAX_IMAGEM

    with _PILImage.open(caminho) as img:
        largura_px, altura_px = img.size
    razao = altura_px / largura_px

    largura_final = largura_max
    altura_final = largura_final * razao
    if altura_final > altura_max:
        altura_final = altura_max
        largura_final = altura_final / razao

    return _RLImage(caminho, width=largura_final, height=altura_final)


def obter_estilos() -> dict:
    """
    Retorna um dicionário de ParagraphStyle prontos, com hierarquia
    tipográfica definida (tamanho + peso + espaçamento + cor).
    Chaves: Titulo, Subtitulo, H1, H2, Corpo, CorpoCentro, Legenda, RodapeTexto
    """
    base = getSampleStyleSheet()
    estilos = {
        "Titulo": ParagraphStyle(
            "Titulo", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=24, leading=28, textColor=PALETA["primaria"],
            spaceAfter=6, alignment=TA_CENTER,
        ),
        "Subtitulo": ParagraphStyle(
            "Subtitulo", parent=base["Normal"], fontName="Helvetica",
            fontSize=13, leading=16, textColor=PALETA["texto_claro"],
            spaceAfter=24, alignment=TA_CENTER,
        ),
        "H1": ParagraphStyle(
            "H1", parent=base["Heading1"], fontName="Helvetica-Bold",
            fontSize=16, leading=20, textColor=PALETA["primaria"],
            spaceBefore=18, spaceAfter=10,
        ),
        "H2": ParagraphStyle(
            "H2", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=12.5, leading=16, textColor=PALETA["secundaria"],
            spaceBefore=12, spaceAfter=6,
        ),
        "Corpo": ParagraphStyle(
            "Corpo", parent=base["Normal"], fontName="Helvetica",
            fontSize=10.5, leading=15, textColor=PALETA["texto"],
            spaceAfter=8, alignment=TA_LEFT,
        ),
        "CorpoCentro": ParagraphStyle(
            "CorpoCentro", parent=base["Normal"], fontName="Helvetica",
            fontSize=10.5, leading=15, textColor=PALETA["texto"],
            spaceAfter=8, alignment=TA_CENTER,
        ),
        "Legenda": ParagraphStyle(
            "Legenda", parent=base["Normal"], fontName="Helvetica-Oblique",
            fontSize=8.5, leading=11, textColor=PALETA["texto_claro"],
        ),
    }
    return estilos


def paragrafo_capa(titulo: str, subtitulo: str = "", autor: str = "") -> list:
    """
    Monta os flowables de uma página de capa simples e limpa.
    Retorna uma lista pronta para ser somada (+=) à sua lista de elementos.
    Termina com PageBreak — o conteúdo seguinte já começa em página nova.
    """
    estilos = obter_estilos()
    elementos = [
        Spacer(1, 6 * cm),
        Paragraph(titulo, estilos["Titulo"]),
    ]
    if subtitulo:
        elementos.append(Paragraph(subtitulo, estilos["Subtitulo"]))
    if autor:
        elementos.append(Spacer(1, 1 * cm))
        elementos.append(Paragraph(autor, estilos["CorpoCentro"]))
    elementos.append(PageBreak())
    return elementos


def tabela_estilizada(cabecalho: list, linhas: list, col_widths=None) -> Table:
    """
    Cria uma Table com: header colorido (fundo primária, texto branco,
    negrito), linhas zebradas (branco / cinza claro alternados), bordas
    discretas e padding confortável. Pronta pra usar direto no `story`.

    cabecalho: lista de strings, ex: ["Item", "Quantidade", "Valor"]
    linhas: lista de listas, mesmo número de colunas do cabeçalho
    col_widths: opcional, lista de larguras em cm (ex: [6, 3, 3])
    """
    dados = [cabecalho] + linhas
    tabela = Table(
        dados,
        colWidths=[w * cm for w in col_widths] if col_widths else None,
        repeatRows=1,  # repete o cabeçalho se a tabela quebrar de página
    )

    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), PALETA["primaria"]),
        ("TEXTCOLOR", (0, 0), (-1, 0), PALETA["branco"]),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("TEXTCOLOR", (0, 1), (-1, -1), PALETA["texto"]),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, 0), 0.75, PALETA["primaria"]),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, PALETA["linha"]),
    ]
    # zebra striping nas linhas de dados
    for i in range(1, len(dados)):
        if i % 2 == 0:
            estilo.append(("BACKGROUND", (0, i), (-1, i), PALETA["fundo_alt"]))

    tabela.setStyle(TableStyle(estilo))
    return tabela


def _rodape_numerado(canvas_obj, doc):
    """Callback interno usado por construir_documento — não chamar direto."""
    canvas_obj.saveState()
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.setFillColor(PALETA["texto_claro"])
    largura_pagina = doc.pagesize[0]
    texto = f"Página {doc.page}"
    canvas_obj.drawRightString(largura_pagina - MARGEM, 1.2 * cm, texto)
    if getattr(doc, "titulo_doc", None):
        canvas_obj.drawString(MARGEM, 1.2 * cm, doc.titulo_doc)
    canvas_obj.setStrokeColor(PALETA["linha"])
    canvas_obj.line(MARGEM, 1.5 * cm, largura_pagina - MARGEM, 1.5 * cm)
    canvas_obj.restoreState()


def construir_documento(caminho_saida: str, elementos: list, titulo_doc: str = "", pagesize=A4) -> str:
    """
    Monta o SimpleDocTemplate com margens padronizadas e rodapé numerado
    automático, e escreve o PDF em caminho_saida.

    Retorna o caminho_saida (útil para logar/confirmar no stdout do bash).
    """
    doc = SimpleDocTemplate(
        caminho_saida,
        pagesize=pagesize,
        topMargin=MARGEM,
        bottomMargin=MARGEM + 0.4 * cm,
        leftMargin=MARGEM,
        rightMargin=MARGEM,
    )
    doc.titulo_doc = titulo_doc  # lido pelo callback de rodapé
    doc.build(elementos, onFirstPage=_rodape_numerado, onLaterPages=_rodape_numerado)
    return caminho_saida


def renderizar_pdf_para_imagens(caminho_pdf: str, prefixo: str = "pagina", dpi: int = 150, formato: str = "png") -> list:
    """
    Roda DENTRO do sandbox (via execute_bash). Abre `caminho_pdf` e
    salva uma imagem por página como `{prefixo}-{numero}.{formato}`
    no diretório atual (o work_dir, que é o mesmo dir visível pelo
    processo principal do agente, já que é montado com --bind e não
    copiado).

    Retorna a lista de caminhos gerados, em ordem — é essa lista que a
    ferramenta deve devolver no stdout/JSON pro código que roda fora
    do sandbox (montar_mensagem_visual) usar em seguida.
    """
    import fitz  # PyMuPDF

    doc = fitz.open(caminho_pdf)
    zoom = dpi / 72  # fitz usa 72 dpi como base de conversão
    matriz = fitz.Matrix(zoom, zoom)

    caminhos = []
    for indice, pagina in enumerate(doc, start=1):
        pix = pagina.get_pixmap(matrix=matriz)
        caminho_saida = f"{prefixo}-{indice}.{formato}"
        pix.save(caminho_saida)
        caminhos.append(caminho_saida)

    doc.close()
    return caminhos


def montar_mensagem_visual(caminhos_imagens: list, instrucao: str, formato: str = "png"):
    """
    Roda FORA do sandbox, no processo principal do agente (onde
    langchain e a rede estão disponíveis). Lê as imagens já geradas
    por renderizar_pdf_para_imagens e monta um HumanMessage multimodal
    no formato que o ChatOpenAI espera (content-blocks com
    "image_url" em data URI base64).

    Retorna um langchain_core.messages.HumanMessage pronto pra ser
    anexado à lista `mensagens` do loop do agente — na próxima chamada
    ao LLM, ele "vê" as páginas renderizadas junto com `instrucao`.
    """
    from langchain_core.messages import HumanMessage

    conteudo = [{"type": "text", "text": instrucao}]
    for caminho in caminhos_imagens:
        dados = base64.b64encode(Path(caminho).read_bytes()).decode("utf-8")
        conteudo.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/{formato};base64,{dados}"},
        })

    return HumanMessage(content=conteudo)