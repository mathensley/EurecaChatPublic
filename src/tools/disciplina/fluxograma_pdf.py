from pathlib import Path

import fitz

from src.helpers.tool_handlers.tool_utils import limpar_prerequisitos


PAGINA = fitz.paper_rect("a4-l")
MARGEM = 28
LIMITE_INFERIOR = PAGINA.height - 28
VERDE = (23 / 255, 79 / 255, 64 / 255)
VERDE_CLARO = (237 / 255, 245 / 255, 242 / 255)
CINZA_CLARO = (244 / 255, 247 / 255, 246 / 255)
BORDA = (157 / 255, 169 / 255, 165 / 255)
TEXTO = (23 / 255, 32 / 255, 51 / 255)
BRANCO = (1, 1, 1)
TAMANHO_FONTE = 7.5
ALTURA_CABECALHO = 22

COLUNAS = (
    ("Disciplina", 190),
    ("Código", 55),
    ("Créditos", 45),
    ("Carga horária", 65),
    ("Setor", 255),
    ("Tipo", 65),
    ("Pré-requisito", 111),
)

FONTE_NORMAL = fitz.Font(fontname="helv")


def _texto(valor, padrao: str = "-") -> str:
    if valor is None or valor == "":
        return padrao
    return str(valor)


def _valores_disciplina(disciplina: dict) -> tuple[str, ...]:
    return (
        _texto(disciplina.get("nome")),
        _texto(disciplina.get("codigo_da_disciplina")),
        _texto(disciplina.get("quantidade_de_creditos")),
        f"{_texto(disciplina.get('horas_totais'))}h",
        _texto(disciplina.get("nome_do_setor")),
        _texto(disciplina.get("tipo")),
        limpar_prerequisitos(_texto(disciplina.get("pre_requisitos"), "")),
    )


def _dividir_palavra(palavra: str, largura: float, fonte: fitz.Font) -> list[str]:
    partes = []
    parte = ""
    for caractere in palavra:
        candidata = parte + caractere
        if parte and fonte.text_length(candidata, fontsize=TAMANHO_FONTE) > largura:
            partes.append(parte)
            parte = caractere
        else:
            parte = candidata
    if parte:
        partes.append(parte)
    return partes or [""]


def _quebrar_texto(
    texto: str,
    largura: float,
    *,
    fonte: fitz.Font = FONTE_NORMAL,
) -> list[str]:
    linhas = []
    paragrafos = texto.splitlines() or [""]

    for paragrafo in paragrafos:
        palavras = paragrafo.split() or [""]
        linha = ""

        for palavra in palavras:
            partes = (
                [palavra]
                if fonte.text_length(palavra, fontsize=TAMANHO_FONTE) <= largura
                else _dividir_palavra(palavra, largura, fonte)
            )
            for parte in partes:
                candidata = f"{linha} {parte}".strip()
                if linha and fonte.text_length(
                    candidata,
                    fontsize=TAMANHO_FONTE,
                ) > largura:
                    linhas.append(linha)
                    linha = parte
                else:
                    linha = candidata

        linhas.append(linha)

    return linhas or [""]


def _preparar_linha(disciplina: dict) -> tuple[list[list[str]], float]:
    celulas = [
        _quebrar_texto(valor, largura - 8)
        for valor, (_, largura) in zip(_valores_disciplina(disciplina), COLUNAS)
    ]
    quantidade_linhas = max(len(celula) for celula in celulas)
    altura = max(18, quantidade_linhas * TAMANHO_FONTE * 1.35 + 8)
    return celulas, altura


def _nova_pagina(documento: fitz.Document) -> tuple[fitz.Page, float]:
    pagina = documento.new_page(width=PAGINA.width, height=PAGINA.height)
    return pagina, float(MARGEM)


def _desenhar_cabecalho(pagina: fitz.Page, y: float) -> float:
    x = float(MARGEM)
    for titulo, largura in COLUNAS:
        caixa = fitz.Rect(x, y, x + largura, y + ALTURA_CABECALHO)
        pagina.draw_rect(caixa, color=BORDA, fill=VERDE, width=0.5)
        pagina.insert_textbox(
            caixa + (3, 5, -3, -2),
            titulo,
            fontsize=7,
            fontname="hebo",
            color=BRANCO,
            align=fitz.TEXT_ALIGN_CENTER,
        )
        x += largura
    return y + ALTURA_CABECALHO


def _desenhar_linha(
    pagina: fitz.Page,
    y: float,
    celulas: list[list[str]],
    altura: float,
    *,
    alternada: bool,
) -> float:
    x = float(MARGEM)
    fundo = CINZA_CLARO if alternada else BRANCO

    for linhas, (_, largura) in zip(celulas, COLUNAS):
        caixa = fitz.Rect(x, y, x + largura, y + altura)
        pagina.draw_rect(caixa, color=BORDA, fill=fundo, width=0.4)
        restante = pagina.insert_textbox(
            caixa + (4, 4, -4, -3),
            "\n".join(linhas),
            fontsize=TAMANHO_FONTE,
            fontname="helv",
            color=TEXTO,
            lineheight=1.15,
        )
        if restante < -0.1:
            raise RuntimeError("Não foi possível acomodar o texto em uma célula do PDF.")
        x += largura

    return y + altura


def _desenhar_titulo_secao(pagina: fitz.Page, y: float, titulo: str) -> float:
    pagina.insert_text(
        (MARGEM, y + 16),
        titulo,
        fontsize=14,
        fontname="hebo",
        color=VERDE,
    )
    return y + 24


def _agrupar_disciplinas(
    disciplinas: list[dict],
) -> tuple[list[tuple[str, list[dict]]], int, int, int]:
    semestres: dict[int, list[dict]] = {}
    optativas = []
    complementares = []

    for disciplina in disciplinas:
        semestre = disciplina.get("semestre_ideal")
        tipo = _texto(disciplina.get("tipo"), "").upper()

        if tipo == "COMPLEMENTAR":
            complementares.append(disciplina)
        elif tipo == "OPTATIVO" or semestre in {None, "0", 0}:
            optativas.append(disciplina)
        else:
            try:
                semestres.setdefault(int(semestre), []).append(disciplina)
            except (TypeError, ValueError):
                optativas.append(disciplina)

    secoes = [
        (f"{semestre}º semestre", semestres[semestre])
        for semestre in sorted(semestres)
    ]
    if optativas:
        secoes.append(("Disciplinas optativas", optativas))
    if complementares:
        secoes.append(("Disciplinas complementares", complementares))

    obrigatorias = sum(len(itens) for itens in semestres.values())
    return secoes, obrigatorias, len(optativas), len(complementares)


def _desenhar_identificacao(
    pagina: fitz.Page,
    *,
    curso: str,
    campus: str,
    curriculo: str,
) -> float:
    pagina.insert_text(
        (MARGEM, MARGEM + 23),
        "Fluxograma de disciplinas",
        fontsize=22,
        fontname="hebo",
        color=VERDE,
    )

    topo = MARGEM + 38
    caixa = fitz.Rect(MARGEM, topo, PAGINA.width - MARGEM, topo + 48)
    pagina.draw_rect(caixa, color=(0.72, 0.83, 0.79), fill=VERDE_CLARO, width=0.7)
    pagina.insert_textbox(
        caixa + (9, 8, -9, -6),
        f"Curso: {curso}\nCampus: {campus}\nCurrículo: {curriculo}",
        fontsize=9,
        fontname="hebo",
        color=TEXTO,
        lineheight=1.15,
    )
    return caixa.y1 + 14


def _desenhar_resumo(
    documento: fitz.Document,
    pagina: fitz.Page,
    y: float,
    *,
    obrigatorias: int,
    optativas: int,
    complementares: int,
    curriculo: str,
) -> tuple[fitz.Page, float]:
    altura = 105
    if y + altura > LIMITE_INFERIOR:
        pagina, y = _nova_pagina(documento)

    y = _desenhar_titulo_secao(pagina, y, "Resumo geral")
    caixa = fitz.Rect(MARGEM, y, PAGINA.width - MARGEM, y + 72)
    pagina.draw_rect(caixa, color=(0.72, 0.83, 0.79), fill=VERDE_CLARO, width=0.7)
    total = obrigatorias + optativas + complementares
    pagina.insert_textbox(
        caixa + (10, 8, -10, -6),
        (
            f"Total: {total} disciplinas\n"
            f"Obrigatórias: {obrigatorias}\n"
            f"Optativas: {optativas}\n"
            f"Complementares: {complementares}\n"
            f"Currículo utilizado: {curriculo}"
        ),
        fontsize=9,
        fontname="hebo",
        color=TEXTO,
        lineheight=1.15,
    )
    return pagina, caixa.y1


def _adicionar_numeracao(documento: fitz.Document) -> None:
    total = len(documento)
    for indice, pagina in enumerate(documento):
        numero = f"Página {indice + 1} de {total}"
        largura = FONTE_NORMAL.text_length(numero, fontsize=7)
        pagina.insert_text(
            ((PAGINA.width - largura) / 2, PAGINA.height - 10),
            numero,
            fontsize=7,
            fontname="helv",
            color=(0.35, 0.4, 0.39),
        )


def gerar_pdf_fluxograma(
    disciplinas: list[dict],
    caminho: Path,
    *,
    curso: str,
    campus: str,
    curriculo: str,
) -> None:
    """Gera um PDF paginado sem fragmentar as linhas das disciplinas."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    secoes, obrigatorias, optativas, complementares = _agrupar_disciplinas(
        disciplinas
    )
    documento = fitz.open()

    try:
        pagina, y = _nova_pagina(documento)
        y = _desenhar_identificacao(
            pagina,
            curso=curso,
            campus=campus,
            curriculo=curriculo,
        )

        for titulo, itens in secoes:
            primeira_linha, primeira_altura = _preparar_linha(itens[0])
            altura_minima = 24 + ALTURA_CABECALHO + primeira_altura
            if y + altura_minima > LIMITE_INFERIOR:
                pagina, y = _nova_pagina(documento)

            y = _desenhar_titulo_secao(pagina, y, titulo)
            y = _desenhar_cabecalho(pagina, y)

            for indice, disciplina in enumerate(itens):
                if indice == 0:
                    celulas, altura = primeira_linha, primeira_altura
                else:
                    celulas, altura = _preparar_linha(disciplina)

                if y + altura > LIMITE_INFERIOR:
                    pagina, y = _nova_pagina(documento)
                    y = _desenhar_titulo_secao(
                        pagina,
                        y,
                        f"{titulo} (continuação)",
                    )
                    y = _desenhar_cabecalho(pagina, y)

                y = _desenhar_linha(
                    pagina,
                    y,
                    celulas,
                    altura,
                    alternada=indice % 2 == 1,
                )

            y += 12

        _desenhar_resumo(
            documento,
            pagina,
            y,
            obrigatorias=obrigatorias,
            optativas=optativas,
            complementares=complementares,
            curriculo=curriculo,
        )
        _adicionar_numeracao(documento)
        documento.set_metadata(
            {
                "title": f"Fluxograma de disciplinas - {curso}",
                "author": "EurecaChat - UFCG",
                "subject": f"Currículo {curriculo}",
            }
        )
        documento.save(caminho, garbage=4, deflate=True)
    finally:
        documento.close()
