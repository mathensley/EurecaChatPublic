from pathlib import Path
from .hierarquia_siglas.siglas import SIGLAS
from typing import Any, Optional
from rapidfuzz import process, fuzz
from application.config import URL_SIG
from application.config import chat_sql
from .gerenciador_expert_v2 import GerenciadorExpertV2
import json, re, sqlite3, requests, unicodedata, difflib, os
from ...helpers.tool_handlers.campi_for_tools import campi as _campi


campi = [{ "nome_do_campus": campus["campus"], "codigo_do_campus": campus["codigo"], } for campus in _campi]
gerenciador_expert_v2: Optional[GerenciadorExpertV2] = GerenciadorExpertV2(llm=chat_sql)

BASE_DIR = Path(__file__).resolve().parent
JSON_PATH = BASE_DIR / "hierarquia_siglas" / "cursos.json"
SQLITE_DIR = Path(os.getenv("SQLITE_DIR", ".")).expanduser()
TABELA = "ufcg"
DB_PATH = (SQLITE_DIR / f"{TABELA}.sqlite").resolve()
UFCG_SQLITE = DB_PATH

_CACHE_CURSOS: Optional[list[dict]] = None
_CACHE_CURSOS_FORMATADOS: Optional[list[dict]] = None
_CACHE_CURSOS_POR_CODIGO: Optional[dict[int, dict]] = None
_CACHE_UNIDADES: Optional[dict[int, dict]] = None
_CACHE_CENTROS: Optional[dict[int, dict]] = None
_CACHE_ESTRUTURA: Optional[list[dict]] = None
_CACHE_ESTRUTURA_CENTRO_INDEX: Optional[dict[int, dict]] = None
_CACHE_ESTRUTURA_UNIDADE_INDEX: Optional[dict[int, dict]] = None
_CACHE_CENTRO_DA_UNIDADE: Optional[dict[int, dict]] = None

def roman_to_int(match):
    ROMAN_MAP = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10}
    roman = match.group(0).lower()
    return str(ROMAN_MAP[roman])

def normalize_txt(txt):
    txt = "".join(c for c in unicodedata.normalize("NFD", txt.lower()) if unicodedata.category(c) != "Mn")
    txt = re.sub(r"\b(i|ii|iii|iv|v|vi|vii|viii|ix|x)\b", roman_to_int, txt)
    txt = re.sub(r"[^a-z0-9\s]", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt

def format_course_results(matches: list[tuple[dict, float]]) -> list[dict]:
    """
    Formata os resultados da busca de cursos.
    
    - Se houver mais de um candidato, retorna lista resumida com apenas código, descrição, turno, modalidade e similaridade.
    - Se houver apenas um candidato, retorna lista com o curso completo (sem incluir a similaridade).

    Args:
        matches (list[tuple[dict, float]]): Lista de tuplas contendo (curso_dict, score_de_similaridade).

    Returns:
        list[dict]: Lista formatada conforme regra descrita acima.
    """

    if not matches: return []
    
    if len(matches) > 1:
        resultado = [
            {
                "codigo_do_curso": c.get("codigo_do_curso"),
                "nome_do_curso": c.get("nome_do_curso"),
                "nome_do_campus": c.get("nome_do_campus"),
                "turno": c.get("turno"),
                "modalidade_academica": c.get("modalidade_academica"),
                "similaridade": score
            }
            for c, score in matches
        ]
        if len(resultado) > 1:
            tops = "\n".join(f'- "{x["nome_do_curso"]}", Código do curso: {x.get("codigo_do_curso")}, Campus: {x.get("nome_do_campus", "")}' for x in resultado)
            texto_adicional = "Se você achar que algum destes itens é o correto, então chame essa ferramenta novamente fornecendo o nome correto e outros parâmetros necessários. Caso não encontre alguma similar, pergunte ao usuário."
            raise ValueError(f"Nenhum item semelhante encontrado.\nTermos mais próximos encontrados:\n\n{tops}\n\n{texto_adicional}")
    curso, _ = matches[0]
    return [curso]


def get_most_similar_acronym(sigla: str, context: str):
    """
    Função que utiliza difflib para encontrar a sigla mais similar à sigla informada.

    Args:
        sigla: sigla desejada.
        context: Contexto da sigla, pode ser disciplina, curso etc. Por exemplo se o contexto informado for 'disciplina' então as siglas a serem consideradas serão as siglas das disciplinas que estão no arquivo json siglas.
    
    Returns:
            Sigla original ou nome por extenso da sigla mais próxima à desejada. Ex: se for 'fm cc 2', a função retornará 'fundamentos de matemática para ciência da computação 2'.
    
    Observação:
        Caso a sigla não tenha correspondência no arquivo json então a sigla orginal que foi passado para o parâmetro da função é o que será retornado.
    """
    
    if not SIGLAS: return sigla
    if context not in SIGLAS: return sigla

    sigla_copia = sigla
    sigla = sigla.upper().strip()
    lista_siglas = list(SIGLAS[context].keys())
    most_similar = difflib.get_close_matches(sigla, lista_siglas, n=1, cutoff=0.7)

    return SIGLAS[context][most_similar[0]] if most_similar else sigla_copia


def remover_acentos(texto: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')


def formatar_nome_curso(curso: dict) -> str:
    return f"{curso['nome_do_curso']} - {curso['turno']} - {curso['modalidade_academica']}"


def _sufixo_sigla(sigla: str) -> str:
    """
    Retorna " - SIGLA" se houver sigla, senão string vazia.

    Existia um bug de precedência de operador no código original:

        curso["nome_da_unidade"] + f'...sigla...' if curso["sigla_da_unidade"] else ""

    O `if/else` tem precedência menor que `+`, então essa linha equivale a
    `(nome + sufixo) if sigla else ""` -- ou seja, sempre que a unidade não
    tinha sigla, o campo "nome_da_unidade" inteiro virava string vazia, e
    não apenas o sufixo. Esta função corrige isso.
    """
    return f" - {sigla}" if sigla else ""


def _carregar_cursos() -> list[dict]:
    global _CACHE_CURSOS
    if _CACHE_CURSOS is None:
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            _CACHE_CURSOS = json.load(f)
    return _CACHE_CURSOS


def _cursos_formatados() -> list[dict]:
    """Cursos com nome_do_curso já formatado, calculado uma única vez
    (substitui a cópia + formatação que get_cursos fazia em toda chamada)."""
    global _CACHE_CURSOS_FORMATADOS
    if _CACHE_CURSOS_FORMATADOS is None:
        _CACHE_CURSOS_FORMATADOS = [
            dict(c, nome_do_curso=formatar_nome_curso(c)) for c in _carregar_cursos()
        ]
    return _CACHE_CURSOS_FORMATADOS


def _cursos_por_codigo() -> dict[int, dict]:
    """Índice O(1) por codigo_do_curso (antes era busca linear + rebuild completo)."""
    global _CACHE_CURSOS_POR_CODIGO
    if _CACHE_CURSOS_POR_CODIGO is None:
        _CACHE_CURSOS_POR_CODIGO = {c["codigo_do_curso"]: c for c in _cursos_formatados()}
    return _CACHE_CURSOS_POR_CODIGO


def _montar_unidades() -> dict[int, dict]:
    global _CACHE_UNIDADES
    if _CACHE_UNIDADES is not None:
        return _CACHE_UNIDADES

    unidades: dict[int, dict] = {}
    for curso in _carregar_cursos():
        cod_unidade = curso["codigo_da_unidade"]
        if cod_unidade not in unidades:
            unidades[cod_unidade] = {
                "codigo_da_unidade": cod_unidade,
                "nome_da_unidade": curso["nome_da_unidade"] + _sufixo_sigla(curso["sigla_da_unidade"]),
                "codigo_do_campus": curso["codigo_do_campus"],
                "nome_do_campus": curso["nome_do_campus"],
                "codigo_do_centro": curso["codigo_do_centro"],
                "nome_do_centro": curso["nome_do_centro"] + " - " + curso["sigla_do_centro"],
                "codigo_dos_cursos": [],
                "cursos": [],
            }
        unidades[cod_unidade]["codigo_dos_cursos"].append(curso["codigo_do_curso"])
        unidades[cod_unidade]["cursos"].append({
            "nome_do_curso": formatar_nome_curso(curso),
            "modalidade_academica": curso["modalidade_academica"],
            "codigo_do_curso": curso["codigo_do_curso"],
            "turno": curso["turno"],
        })

    _CACHE_UNIDADES = unidades
    return unidades


def _montar_centros() -> dict[int, dict]:
    global _CACHE_CENTROS
    if _CACHE_CENTROS is not None:
        return _CACHE_CENTROS

    centros: dict[int, dict] = {}
    for curso in _carregar_cursos():
        cod_centro = curso["codigo_do_centro"]
        if cod_centro not in centros:
            centros[cod_centro] = {
                "codigo_do_campus": curso["codigo_do_campus"],
                "nome_do_campus": curso["nome_do_campus"],
                "codigo_do_centro": cod_centro,
                "nome_do_centro": curso["nome_do_centro"] + " - " + curso["sigla_do_centro"],
                "codigo_dos_cursos": [],
                "cursos": [],
            }
        centros[cod_centro]["codigo_dos_cursos"].append(curso["codigo_do_curso"])
        centros[cod_centro]["cursos"].append({
            "nome_do_curso": formatar_nome_curso(curso),
            "modalidade_academica": curso["modalidade_academica"],
            "codigo_do_curso": curso["codigo_do_curso"],
            "turno": curso["turno"],
        })

    _CACHE_CENTROS = centros
    return centros


def _montar_estrutura() -> list[dict]:
    global _CACHE_ESTRUTURA, _CACHE_ESTRUTURA_CENTRO_INDEX, _CACHE_ESTRUTURA_UNIDADE_INDEX
    if _CACHE_ESTRUTURA is not None:
        return _CACHE_ESTRUTURA

    campi_dict: dict[int, dict] = {}
    centro_index: dict[int, dict] = {}
    unidade_index: dict[int, dict] = {}

    for curso in _carregar_cursos():
        cod_campus = curso["codigo_do_campus"]
        cod_centro = curso["codigo_do_centro"]
        cod_unidade = curso["codigo_da_unidade"]

        campus = campi_dict.setdefault(cod_campus, {
            "codigo_do_campus": cod_campus,
            "nome_do_campus": curso["nome_do_campus"],
            "centros": {},
        })

        centro = campus["centros"].setdefault(cod_centro, {
            "codigo_do_centro": cod_centro,
            "nome_do_centro": f'{curso["nome_do_centro"]} - {curso["sigla_do_centro"]}',
            "unidades": {},
        })
        centro_index.setdefault(cod_centro, centro)

        unidade = centro["unidades"].setdefault(cod_unidade, {
            "codigo_da_unidade": cod_unidade,
            "nome_da_unidade": curso["nome_da_unidade"] + _sufixo_sigla(curso["sigla_da_unidade"]),
            "codigo_dos_cursos": [],
            "cursos": [],
        })
        unidade_index.setdefault(cod_unidade, unidade)

        unidade["codigo_dos_cursos"].append(curso["codigo_do_curso"])
        unidade["cursos"].append({
            "codigo_do_curso": curso["codigo_do_curso"],
            "nome_do_curso": formatar_nome_curso(curso),
            "modalidade_academica": curso["modalidade_academica"],
            "turno": curso["turno"],
        })

    resultado = []
    for campus in campi_dict.values():
        campus["centros"] = list(campus["centros"].values())
        for centro in campus["centros"]:
            centro["unidades"] = list(centro["unidades"].values())
        resultado.append(campus)

    _CACHE_ESTRUTURA = resultado
    _CACHE_ESTRUTURA_CENTRO_INDEX = centro_index
    _CACHE_ESTRUTURA_UNIDADE_INDEX = unidade_index
    return resultado


def _montar_centro_da_unidade() -> dict[int, dict]:
    global _CACHE_CENTRO_DA_UNIDADE
    if _CACHE_CENTRO_DA_UNIDADE is not None:
        return _CACHE_CENTRO_DA_UNIDADE

    indice: dict[int, dict] = {}
    for curso in _carregar_cursos():
        cod_unidade = curso["codigo_da_unidade"]
        if cod_unidade not in indice:
            indice[cod_unidade] = {
                "codigo_do_centro": curso["codigo_do_centro"],
                "nome_do_centro": f'{curso["nome_do_centro"]} - {curso["sigla_do_centro"]}',
            }

    _CACHE_CENTRO_DA_UNIDADE = indice
    return indice


# ---------------------------------------------------------------------------
# API pública -- mesma assinatura e mesmo comportamento de antes, agora lendo
# do cache em vez de reconstruir tudo a cada chamada.
# ---------------------------------------------------------------------------

def get_unidades(codigo_do_campus=None, codigo_do_centro=None, codigo_da_unidade=None):
    codigo_do_campus = int(codigo_do_campus) if codigo_do_campus not in ("", None) else None
    codigo_do_centro = int(codigo_do_centro) if codigo_do_centro not in ("", None) else None
    codigo_da_unidade = int(codigo_da_unidade) if codigo_da_unidade not in ("", None) else None

    unidades = _montar_unidades()

    if codigo_da_unidade:
        unidade = unidades.get(codigo_da_unidade)
        return [dict(unidade)] if unidade else []
    if codigo_do_centro:
        return [dict(u) for u in unidades.values() if u["codigo_do_centro"] == codigo_do_centro]
    if codigo_do_campus:
        return [dict(u) for u in unidades.values() if u["codigo_do_campus"] == codigo_do_campus]
    return [dict(u) for u in unidades.values()]


def get_centros(codigo_do_campus=None, codigo_do_centro=None):
    codigo_do_campus = int(codigo_do_campus) if codigo_do_campus not in ("", None) else None
    codigo_do_centro = int(codigo_do_centro) if codigo_do_centro not in ("", None) else None

    centros = _montar_centros()

    if codigo_do_centro:
        centro = centros.get(codigo_do_centro)
        return [dict(centro)] if centro else []
    if codigo_do_campus:
        return [dict(c) for c in centros.values() if c["codigo_do_campus"] == codigo_do_campus]
    return [dict(c) for c in centros.values()]


def get_cursos(codigo_do_campus=None, codigo_do_centro=None, codigo_da_unidade=None, codigo_do_curso=None):
    codigo_do_campus = int(codigo_do_campus) if codigo_do_campus not in ("", None) else None
    codigo_do_centro = int(codigo_do_centro) if codigo_do_centro not in ("", None) else None
    codigo_da_unidade = int(codigo_da_unidade) if codigo_da_unidade not in ("", None) else None
    codigo_do_curso = int(codigo_do_curso) if codigo_do_curso not in ("", None) else None

    if codigo_do_curso:
        curso = _cursos_por_codigo().get(codigo_do_curso)
        return [dict(curso)] if curso else None

    cursos = _cursos_formatados()
    if codigo_do_centro: return [dict(c) for c in cursos if c["codigo_do_centro"] == codigo_do_centro]
    if codigo_do_campus: return [dict(c) for c in cursos if c["codigo_do_campus"] == codigo_do_campus]
    if codigo_da_unidade: return [dict(c) for c in cursos if c["codigo_da_unidade"] == codigo_da_unidade]
    return [dict(c) for c in cursos]


def get_estrutura(codigo_do_campus=None, codigo_do_centro=None, codigo_da_unidade=None):
    codigo_do_campus = int(codigo_do_campus) if codigo_do_campus not in ("", None) else None
    codigo_do_centro = int(codigo_do_centro) if codigo_do_centro not in ("", None) else None
    codigo_da_unidade = int(codigo_da_unidade) if codigo_da_unidade not in ("", None) else None

    resultado = _montar_estrutura()

    if codigo_da_unidade is not None:
        unidade = _CACHE_ESTRUTURA_UNIDADE_INDEX.get(codigo_da_unidade)
        return [dict(unidade)] if unidade else []

    if codigo_do_centro is not None:
        centro = _CACHE_ESTRUTURA_CENTRO_INDEX.get(codigo_do_centro)
        return [dict(centro)] if centro else []

    if codigo_do_campus is not None:
        return [dict(c) for c in resultado if c["codigo_do_campus"] == codigo_do_campus]

    return [dict(c) for c in resultado]


def get_centro_da_unidade(codigo_da_unidade):
    codigo_da_unidade = int(codigo_da_unidade) if codigo_da_unidade not in ("", None) else None
    resultado = _montar_centro_da_unidade().get(codigo_da_unidade)
    return dict(resultado) if resultado else None


def _texto_comparacao(item: dict, field: str) -> str:
    """
    Monta o texto usado na comparação fuzzy, concatenando o nome do campus quando
    aplicável -- sem mutar o dicionário original. Compartilhado por
    extract_most_similar() e pelo modo de ranking (_top_k_fuzzy / _ranking_multi_termo).
    """
    valor = item.get(field, "")
    if "nome_do_campus" in item and field in (
        "nome_da_disciplina", "nome_do_curso", "nome_da_unidade", "nome_do_centro"
    ):
        return f"{valor} - {item['nome_do_campus']}"
    return valor


def extract_most_similar(
        query_text: str,
        items: list[dict],
        field: str,
        tie_break_threshold: float = 2.0,
        top_k: int = 10,
        min_similarity: float = 40.0
) -> list[tuple[dict, float]]:
    """
    Retorna os itens mais semelhantes a um texto de consulta com base em comparação
    aproximada de strings (fuzzy matching).

    Args:
        query_text (str): Texto de entrada a ser comparado.
        items (list[dict]): Lista de objetos (dicionários) a serem buscados.
        field (str): Nome do atributo (chave do dicionário) usado para comparação.
        tie_break_threshold (float, optional): Diferença máxima de score em relação
            ao melhor resultado para considerar empate.
        top_k (int, optional): Número máximo de candidatos a retornar antes da
            aplicação do critério de desempate.
        min_similarity (float, optional): Similaridade mínima aceitável para
            considerar uma correspondência válida.

    Returns:
        list[tuple[dict, float]]: Lista de tuplas (item original, score).

    Raises:
        ValueError: Se nenhuma correspondência tiver similaridade suficiente.
    """
    query = normalize_txt(query_text)
    list_norm = [normalize_txt(_texto_comparacao(obj, field)) for obj in items]

    matches = process.extract(query, list_norm, limit=top_k, scorer=fuzz.token_set_ratio)

    if not matches:
        return []

    best_score = matches[0][1]
    if best_score < min_similarity:
        tops = "\n".join(f'- "{str(items[idx][field])}"' for _, _, idx in matches[:top_k])
        texto_adicional = (
            "Se você achar que algum destes itens é o correto, então chame essa ferramenta "
            "novamente fornecendo o nome correto e outros parâmetros necessários. Caso não "
            "encontre alguma similar, pergunte ao usuário."
        )
        raise ValueError(
            f"Nenhum item semelhante encontrado.\nTermos mais próximos encontrados:\n\n{tops}\n\n{texto_adicional}"
        )

    possibles = [m for m in matches if best_score - m[1] <= tie_break_threshold]
    return [(items[idx], score) for _, score, idx in possibles]


def resolver_similar_ou_codigo(valor: Any, lista: list, campo_nome: str, campo_codigo: str):
    """
    Aceita nome OU código para busca de entidades (centro, unidade, etc).

    Busca um número "isolado" (não colado a outros dígitos) dentro da string,
    mesmo padrão usado em buscar_curso_por_nome_ou_codigo. Permite tanto "123"
    quanto "Centro 123" ou "123 - Nome do Centro".

    Se o código existir na lista, retorna no MESMO FORMATO do extract_most_similar
    (lista de tuplas (item, score)), preservando compatibilidade com quem consome
    o resultado (ex: [0][0], len(...) > 1).

    Se o código não existir, cai no fuzzy match por nome, que levanta ValueError
    com sugestões caso nada seja suficientemente semelhante.
    """
    if valor not in ("", None):
        codigo_encontrado = re.search(r"(?<!\d)\d+(?!\d)", str(valor).strip())
        if codigo_encontrado:
            codigo = codigo_encontrado.group(0)
            encontrados = [item for item in lista if str(item[campo_codigo]) == codigo]
            if encontrados:
                return [(item, 100.0) for item in encontrados]

    return extract_most_similar(valor, lista, campo_nome)


def resolver_codigo_campus(campus: Any, campi: list):
    """
    Resolve o código do campus a partir de nome OU código, reaproveitado por
    todas as funções que hoje repetiam essa mesma lógica inline.
    """
    if campus in ("", None):
        return ""
    if str(campus).strip().isdigit():
        return campus
    return extract_most_similar(campus, campi, "nome_do_campus")[0][0]["codigo_do_campus"]


async def buscar_centros_similares(campus: Any = "", centro: Any = ""):
    """
    campus: nome ou código do campus
    centro: nome ou código do centro
    """
    codigo_campus = resolver_codigo_campus(campus, campi)
    centros = get_centros(codigo_do_campus=codigo_campus)
    return resolver_similar_ou_codigo(centro, centros, "nome_do_centro", "codigo_do_centro")


async def buscar_unidades_similares(campus: Any = "", codigo_do_centro=None, unidade_academica: Any = ""):
    """
    campus: nome ou código do campus
    codigo_do_centro: apenas código do centro
    unidade_academica: nome ou código da unidade
    """
    codigo_campus = resolver_codigo_campus(campus, campi)

    lista_unidades = get_unidades(codigo_do_campus=codigo_campus if codigo_campus != "" else None)
    if codigo_do_centro:
        lista_unidades = [u for u in lista_unidades if u["codigo_do_centro"] == codigo_do_centro]

    return resolver_similar_ou_codigo(unidade_academica, lista_unidades, "nome_da_unidade", "codigo_da_unidade")


async def buscar_curso_por_nome_ou_codigo(curso: Any, campus: Any, url) -> tuple[list[dict], dict]:
    """
    Busca cursos da UFCG por nome ou código, com base no campus especificado.

    - Se o curso for um número, é tratado como código direto.
    - Se for nome, será aplicada correspondência aproximada via `extract_most_similar`.
    - Caso mais de um curso seja semelhante, será retornada uma lista resumida com os candidatos.
    - Caso haja apenas um curso, os dados completos desse curso são retornados.

    Args:
        curso (Any): Nome ou código do curso a ser buscado.
        campus (Any): Código numérico ou nome do campus.
        url (Any): URL da API do Eureca (SCAO ou SIGAA).

    Returns:
        tuple[list[dict], dict]: Lista de cursos (completa ou resumida) e parâmetros usados na requisição.
    """
    curso = str(curso)
    campus = str(campus)
    url = f"{url}/cursos"

    params = {"status": "ATIVOS", "codigo_do_campus": resolver_codigo_campus(campus, campi)}
    tem_digitos_curso = re.search(r"(?<!\d)\d{6}(?!\d)", curso)

    if tem_digitos_curso:
        codigo = tem_digitos_curso.group(0)
        data = get_cursos(codigo_do_curso=codigo)
        if not data:
            raise ValueError("Nenhum curso encontrado com esse código.")
        return data, params

    data = get_cursos(codigo_do_campus=params.get("codigo_do_campus", None))
    if not data:
        raise ValueError("Nenhum curso encontrado com esse nome.")

    curso = get_most_similar_acronym(curso, "nome_do_curso")
    matches = extract_most_similar(curso, data, "nome_do_curso")
    return format_course_results(matches), params


async def _resolver_centro(nome_do_centro: Any, nome_do_campus: Any, params: dict, codigos_auxiliares: dict, observacoes_auxiliares: list) -> None:
    """Resolve o centro por nome/código e atualiza params/codigos_auxiliares/observacoes
    in-place. Lógica compartilhada entre extrair_dados() e filtragem()."""
    codigo_do_campus = params.get("codigo_do_campus", None)
    centros_encontrados = await buscar_centros_similares(
        campus=codigo_do_campus if codigo_do_campus else nome_do_campus,
        centro=nome_do_centro,
    )
    centro_similar = centros_encontrados[0][0]
    observacoes_auxiliares.append(f"""codigo_do_campus: "{centro_similar['codigo_do_campus']} """)
    params["codigo_do_centro"] = centro_similar["codigo_do_centro"]
    codigos_auxiliares["codigo_do_centro"] = centro_similar["codigo_do_centro"]
    observacoes_auxiliares.append(f"""nome_do_centro: "{centro_similar['nome_do_centro']}" | codigo_do_centro: {centro_similar['codigo_do_centro']}""")

    if len(centros_encontrados) > 1:
        centros_ambiguos = [
            f"- {c['nome_do_centro']} (Código: {c['codigo_do_centro']}) do campus de {c.get('nome_do_campus', '')}"
            for c, _ in centros_encontrados
        ]
        raise ValueError(
            "Foram encontrados múltiplos centros semelhantes ao informado.\n\nCentros encontrados:\n\n"
            + "\n".join(centros_ambiguos)
        )


async def _resolver_unidade(unidade_academica: Any, nome_do_campus: Any, params: dict, codigos_auxiliares: dict, observacoes_auxiliares: list) -> None:
    """Resolve a unidade acadêmica por nome/código e atualiza params/observacoes
    in-place. Lógica compartilhada entre extrair_dados() e filtragem()."""
    codigo_do_campus = params.get("codigo_do_campus", None)
    unidades_similares = await buscar_unidades_similares(
        campus=codigo_do_campus if codigo_do_campus else nome_do_campus,
        codigo_do_centro=codigos_auxiliares.get("codigo_do_centro", None),
        unidade_academica=unidade_academica,
    )
    unidade_similar = unidades_similares[0][0]
    params["codigo_da_unidade"] = unidade_similar["codigo_da_unidade"]
    observacoes_auxiliares.append(f"""nome_da_unidade: "{unidade_similar['nome_da_unidade']}" | codigo_da_unidade: {unidade_similar['codigo_da_unidade']}""")

    if len(unidades_similares) > 1:
        unidades_ambiguas = [
            f"- {u['nome_da_unidade']} (Código: {u['codigo_da_unidade']}) - pertencente ao {u['nome_do_centro']} do campus de {u['nome_do_campus']}"
            for u, _ in unidades_similares
        ]
        raise ValueError(
            "Foram encontrados múltiplas unidades acadêmicas semelhantes ao informado.\n\nCentros encontrados:\n\n"
            + "\n".join(unidades_ambiguas)
        )


async def _resolver_curso(nome_do_curso: Any, nome_do_campus: Any, params: dict) -> None:
    """Resolve o curso por nome/código e atualiza params in-place.
    Lógica compartilhada entre extrair_dados() e filtragem()."""
    codigo_do_campus = params.get("codigo_do_campus", None)
    cursos_encontrados, _ = await buscar_curso_por_nome_ou_codigo(
        nome_do_curso, codigo_do_campus if codigo_do_campus else nome_do_campus, URL_SIG
    )
    curso_escolhido = cursos_encontrados[0]
    params["codigo_do_curso"] = str(curso_escolhido["codigo_do_curso"])

    if len(cursos_encontrados) > 1:
        cursos_ambiguos = [
            f"- {c['nome_do_curso']} (Código: {c['codigo_do_curso']}), {c['nome_do_campus']}"
            for c in cursos_encontrados
        ]
        raise ValueError(
            "Foram encontrados múltiplos cursos semelhantes ao informado.\n\nCursos encontrados:\n\n"
            + "\n".join(cursos_ambiguos)
        )


def resolve_disciplina(
    codigo_do_campus=None,
    codigo_do_centro=None,
    codigo_da_unidade=None,
    codigo_do_curso=None,
    periodo_de=None,
    periodo_ate=None,
):
    """
    Monta dinamicamente a query de disciplinas, incluindo só os JOINs
    necessários para os filtros informados.

    Cadeia: campus -> centro -> unidade -> curso -> estudante -> inscricao
    (é em Inscricao que existe codigo_da_disciplina / nome_da_disciplina).

    periodo_de / periodo_ate filtram pelo campo Inscricao.periodo (TEXT no
    formato 'AAAA.S'), convertido para REAL na comparação, de forma que
    periodo_de <= periodo <= periodo_ate.

    O resultado final é agrupado por codigo_da_disciplina para garantir
    que cada código apareça uma única vez, com um único nome associado.
    Se houver grafias diferentes para o mesmo código, apenas uma é mantida.

    Retorna (sql, params) prontos para sqlite3.
    """
    filtros, params = [], []

    if codigo_do_campus is not None:
        nivel = "campus"
    elif codigo_do_centro is not None:
        nivel = "centro"
    elif codigo_da_unidade is not None:
        nivel = "unidade"
    elif codigo_do_curso is not None:
        nivel = "curso"
    else:
        nivel = None

    from_clause = []

    if nivel == "campus":
        from_clause += [
            "FROM campus AS cp",
            "JOIN centro AS ce ON ce.codigo_do_campus = cp.codigo_do_campus",
            "JOIN unidade AS u ON u.codigo_do_centro = ce.codigo_do_centro",
            "JOIN curso AS cu ON cu.codigo_da_unidade = u.codigo_da_unidade",
        ]
    elif nivel == "centro":
        from_clause += [
            "FROM centro AS ce",
            "JOIN unidade AS u ON u.codigo_do_centro = ce.codigo_do_centro",
            "JOIN curso AS cu ON cu.codigo_da_unidade = u.codigo_da_unidade",
        ]
    elif nivel == "unidade":
        from_clause += [
            "FROM unidade AS u",
            "JOIN curso AS cu ON cu.codigo_da_unidade = u.codigo_da_unidade",
        ]
    elif nivel == "curso":
        from_clause += ["FROM curso AS cu"]
    else:
        from_clause += ["FROM inscricao AS i"]

    if nivel is not None:
        from_clause += [
            "JOIN estudante AS e ON e.codigo_do_curso = cu.codigo_do_curso",
            "JOIN inscricao AS i ON i.matricula_do_estudante = e.matricula_do_estudante",
        ]

    if codigo_do_campus is not None:
        filtros.append("cp.codigo_do_campus = ?")
        params.append(codigo_do_campus)
    if codigo_do_centro is not None:
        filtros.append("ce.codigo_do_centro = ?")
        params.append(codigo_do_centro)
    if codigo_da_unidade is not None:
        filtros.append("u.codigo_da_unidade = ?")
        params.append(codigo_da_unidade)
    if codigo_do_curso is not None:
        filtros.append("cu.codigo_do_curso = ?")
        params.append(codigo_do_curso)
    if periodo_de is not None:
        filtros.append("CAST(i.periodo AS REAL) >= ?")
        params.append(float(periodo_de))
    if periodo_ate is not None:
        filtros.append("CAST(i.periodo AS REAL) <= ?")
        params.append(float(periodo_ate))

    base_sql = "SELECT\n    i.codigo_da_disciplina,\n    i.nome_da_disciplina\n"
    base_sql += "\n".join(from_clause)
    if filtros:
        base_sql += "\nWHERE " + "\n  AND ".join(filtros)

    sql = (
        "SELECT\n"
        "    base.codigo_da_disciplina,\n"
        "    MIN(base.nome_da_disciplina) AS nome_da_disciplina\n"
        "FROM (\n"
        f"{base_sql}\n"
        ") AS base\n"
        "GROUP BY base.codigo_da_disciplina\n"
        "ORDER BY base.codigo_da_disciplina;"
    )

    return sql, params


async def extrair_dados(
        nome_do_campus: Any = None,
        nome_do_centro: Any = None,
        nome_da_unidade: Any = None,
        nome_do_curso: Any = None,
        params: Optional[dict] = None,
        observacoes_auxiliares: Optional[list] = None,
):
    """
    Todos os filtros são opcionais -- passe apenas o que fizer sentido pra
    consulta (None ou "" são tratados igual, como "não informado").

    `params` e `observacoes_auxiliares` também são opcionais: se não forem
    passados, cada chamada cria os seus próprios objetos novos (NUNCA use
    `{}`/`[]` como valor padrão direto na assinatura -- esse valor é criado
    uma única vez, na definição da função, e fica compartilhado por todas as
    chamadas que não passarem o argumento, causando dados de uma chamada
    vazando pra outra).

    Atenção: `observacoes_auxiliares` só é preenchido por mutação in-place
    (append); ele não é devolvido no retorno. Se você quer inspecionar essas
    observações depois da chamada, precisa passar sua própria lista.
    """
    if params is None:
        params = {}
    if observacoes_auxiliares is None:
        observacoes_auxiliares = []

    codigos_auxiliares = {}

    if nome_do_campus:
        params["codigo_do_campus"] = resolver_codigo_campus(nome_do_campus, campi)

    if nome_do_centro:
        await _resolver_centro(nome_do_centro, nome_do_campus, params, codigos_auxiliares, observacoes_auxiliares)

    if nome_da_unidade:
        await _resolver_unidade(nome_da_unidade, nome_do_campus, params, codigos_auxiliares, observacoes_auxiliares)

    if nome_do_curso:
        await _resolver_curso(nome_do_curso, nome_do_campus, params)

    return params


async def filtragem(
        nome_do_campus: Any = None,
        centro: Any = None,
        unidade_academica: Any = None,
        nome_do_curso: Any = None,
        params: Optional[dict] = None,
        codigos_auxiliares: Optional[dict] = None,
        observacoes_auxiliares: Optional[list] = None,
):
    """Todos os filtros são opcionais -- ver docstring de extrair_dados() para
    os detalhes sobre None vs "" e sobre por que params/codigos_auxiliares/
    observacoes_auxiliares nunca devem ter {}/[] como valor padrão fixo."""
    if params is None:
        params = {}
    if codigos_auxiliares is None:
        codigos_auxiliares = {}
    if observacoes_auxiliares is None:
        observacoes_auxiliares = []

    if nome_do_campus:
        params["codigo_do_campus"] = resolver_codigo_campus(nome_do_campus, campi)

    if unidade_academica:
        await _resolver_unidade(unidade_academica, nome_do_campus, params, codigos_auxiliares, observacoes_auxiliares)

    if centro:
        await _resolver_centro(centro, nome_do_campus, params, codigos_auxiliares, observacoes_auxiliares)

    if nome_do_curso:
        await _resolver_curso(nome_do_curso, nome_do_campus, params)

    return params


# ---------------------------------------------------------------------------
# Busca por ranking (top-k) -- modo NOVO, separado de extrair_dados()/filtragem().
#
# Diferença central: extrair_dados()/filtragem() resolvem cada campo pra um
# ÚNICO código (e levantam ValueError se houver ambiguidade). buscar_ranking()
# nunca levanta erro por ambiguidade -- ao invés disso, devolve até `top_k`
# candidatos por campo, ordenados por similaridade, cada um já com nome e
# código. Também aceita múltiplos termos separados por vírgula num mesmo
# campo (ex.: nome_do_curso="engenharia eletrica, engenharia civil"), e cada
# termo pode ser nome (fuzzy) OU código (match exato).
# ---------------------------------------------------------------------------

def _top_k_fuzzy(query_text: str, items: list[dict], field: str, top_k: int, min_similarity: float) -> list[tuple[dict, float]]:
    """
    Núcleo do modo de ranking: igual ao miolo de extract_most_similar(), mas
    sem o corte por tie_break_threshold e sem levantar erro em baixa
    similaridade -- aqui o objetivo é devolver um ranking (até `top_k`
    itens), não resolver pra um único item.
    """
    if top_k <= 0 or not items:
        return []

    query = normalize_txt(query_text)
    list_norm = [normalize_txt(_texto_comparacao(obj, field)) for obj in items]
    matches = process.extract(query, list_norm, limit=top_k, scorer=fuzz.token_set_ratio)
    return [(items[idx], score) for _, score, idx in matches if score >= min_similarity]


def _ranking_multi_termo(
        texto: Any,
        items: list[dict],
        campo_nome: str,
        campo_codigo: str,
        top_k: int,
        min_similarity: float = 40.0,
        codigo_regex: str = r"(?<!\d)\d+(?!\d)",
        pre_processar_termo=None,
) -> list[tuple[dict, float]]:
    """
    Versão "ranking" de resolver_similar_ou_codigo(): em vez de resolver pra
    um único item, devolve até `top_k` itens mais parecidos POR TERMO,
    ordenados por similaridade.

    `texto` pode conter múltiplos termos separados por vírgula (ex.:
    "engenharia eletrica, engenharia civil"). Cada termo é buscado
    separadamente -- por código (match exato, se contiver um número isolado
    que bata com algum item) ou por nome (fuzzy, respeitando `top_k`) -- e os
    resultados de todos os termos são combinados num único ranking, sem
    duplicados (mantendo o maior score de cada item, caso ele apareça pra
    mais de um termo). Por isso o retorno pode ter mais de `top_k` itens no
    total quando `texto` tem mais de um termo -- `top_k` é o teto POR TERMO,
    não um teto global.

    `pre_processar_termo`, se informado, roda em cima de cada termo antes da
    busca fuzzy (usado pra normalizar sigla/acrônimo de curso).
    """
    if texto in ("", None) or top_k <= 0:
        return []

    termos = [t.strip() for t in str(texto).split(",") if t.strip()]
    melhores: dict[Any, tuple[dict, float]] = {}

    for termo in termos:
        codigo_encontrado = re.search(codigo_regex, termo)
        if codigo_encontrado:
            codigo = codigo_encontrado.group(0)
            encontrados = [item for item in items if str(item[campo_codigo]) == codigo]
            if encontrados:
                for item in encontrados:
                    chave = item[campo_codigo]
                    if chave not in melhores or melhores[chave][1] < 100.0:
                        melhores[chave] = (item, 100.0)
                continue  # código bateu exato: não precisa de fuzzy pra esse termo

        termo_busca = pre_processar_termo(termo) if pre_processar_termo else termo
        for item, score in _top_k_fuzzy(termo_busca, items, campo_nome, top_k, min_similarity):
            chave = item[campo_codigo]
            if chave not in melhores or melhores[chave][1] < score:
                melhores[chave] = (item, score)

    return sorted(melhores.values(), key=lambda par: par[1], reverse=True)


def _ranking_cursos(texto: Any, cursos: list[dict], top_k: int, min_similarity: float) -> list[tuple[dict, float]]:
    """Igual a _ranking_multi_termo(), mas com as particularidades de curso:
    código de 6 dígitos (em vez de número isolado genérico) e normalização de
    acrônimo (get_most_similar_acronym) antes da busca fuzzy por nome."""
    return _ranking_multi_termo(
        texto, cursos, "nome_do_curso", "codigo_do_curso", top_k,
        min_similarity=min_similarity,
        codigo_regex=r"(?<!\d)\d{6}(?!\d)",
        pre_processar_termo=lambda termo: get_most_similar_acronym(termo, "nome_do_curso"),
    )


# Mapa "campo de código no item bruto" -> "nome do campo de ancestral no
# item formatado". Um centro/unidade/curso, montado a partir do
# cursos.json, já carrega de graça o código de TODOS os seus ancestrais --
# não só o pai imediato -- porque cada linha de curso no JSON já vem com
# codigo_do_campus, codigo_do_centro e codigo_da_unidade juntos.
# _formatar_item_ranking usa esse mapa pra devolver a cadeia inteira de
# ancestrais disponíveis, não só o pai imediato -- isso é o que permite ao
# consumidor (ex.: GerenciadorExpertV2.construir_contexto_dados)
# hierarquizar direto entre dois níveis quando um nível intermediário não
# foi buscado (ex.: campus + curso, sem centro/unidade).
_MAPA_ANCESTRAIS = {
    "codigo_do_campus": "pertence_ao_campus_de_codigo",
    "codigo_do_centro": "pertence_ao_centro_de_codigo",
    "codigo_da_unidade": "pertence_a_unidade_de_codigo",
}


def _formatar_item_ranking(item: dict, campo_nome: str, campo_codigo: str) -> dict:
    """
    Formata um item do ranking como {nome: ..., codigo: ...} e inclui TODOS
    os códigos de ancestrais disponíveis no item (campus/centro/unidade,
    conforme aplicável a cada tipo), não só o pai imediato -- ver
    _MAPA_ANCESTRAIS. Esse dado já vem de graça dentro do próprio item (os
    objetos montados em _montar_centros/_montar_unidades/_cursos_formatados
    já carregam os códigos de todos os "pais"), então não é preciso nenhuma
    busca extra pra descobrir isso.
    """
    formatado = {campo_nome: item[campo_nome], campo_codigo: item[campo_codigo]}
    for campo_origem, campo_saida in _MAPA_ANCESTRAIS.items():
        if campo_origem != campo_codigo and campo_origem in item:
            formatado[campo_saida] = item[campo_origem]
    return formatado


def _filtrar_por_escopo(pool: list[dict], campo: str, codigos_permitidos: Optional[set]) -> list[dict]:
    """
    Restringe `pool` aos itens cujo `campo` esteja em `codigos_permitidos`.

    Recebe um CONJUNTO de códigos (não um único código) porque o campo
    anterior do ranking pode ter mais de um candidato igualmente válido
    (top_k_campus/top_k_centro > 1, ou múltiplos termos separados por
    vírgula). Se `codigos_permitidos` for None, não filtra nada -- usado
    quando aquele campo não foi buscado ou quando escopado=False.

    Compara como STRING dos dois lados (mesmo padrão de
    resolver_similar_ou_codigo: `str(item[campo_codigo]) == codigo`). Isso
    importa porque `campi` (campi_for_tools) guarda codigo_do_campus como
    string (ex.: '1'), enquanto centro/unidade/curso -- montados a partir do
    cursos.json -- guardam codigo_do_campus como inteiro (ex.: 1). Uma
    comparação direta com `in` sobre um set misto de tipos (`1 in {'1'}` é
    False) descartava o pool inteiro sempre que nome_do_campus era
    informado, sem levantar nenhum erro -- por isso centro/unidade/curso
    voltavam vazios sempre que o escopo de campus entrava em jogo.
    """
    if codigos_permitidos is None:
        return pool
    permitidos_str = {str(c) for c in codigos_permitidos}
    return [p for p in pool if str(p[campo]) in permitidos_str]


def buscar_disciplinas(**filtros):
    db_path=UFCG_SQLITE
    sql, params = resolve_disciplina(**filtros)

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(sql, params)
        colunas = [c[0] for c in cursor.description]
        resultado = [dict(zip(colunas, linha)) for linha in cursor.fetchall()]
    finally:
        conn.close()

    return resultado


def buscar_professores():
    db_path = UFCG_SQLITE

    sql = (
        "SELECT\n"
        "    p.matricula_do_professor,\n"
        "    MIN(p.nome_do_professor) AS nome_do_professor,\n"
        "    p.codigo_da_unidade\n"
        "FROM professor AS p\n"
        "GROUP BY p.matricula_do_professor\n"
        "ORDER BY p.matricula_do_professor;"
    )

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(sql)
        colunas = [c[0] for c in cursor.description]
        resultado = [dict(zip(colunas, linha)) for linha in cursor.fetchall()]
    finally:
        conn.close()

    return resultado


def buscar_ranking(
        nome_do_campus: Any = None, top_k_campus: int = 1,
        nome_do_centro: Any = None, top_k_centro: int = 1,
        nome_da_unidade: Any = None, top_k_unidade: int = 1,
        nome_do_curso: Any = None, top_k_curso: int = 1,
        nome_da_disciplina: Any = None, top_k_disciplina: int = 1,
        nome_do_professor: Any = None, top_k_professor: int = 1,
        periodo_de: Any = None, periodo_ate=None,
        escopado: bool = True,
        min_similarity: float = 70.0,
) -> dict[str, list[dict]]:
    """
    Busca campus, centro, unidade e/ou curso por nome (fuzzy -- aceita
    múltiplos termos separados por vírgula) ou código, devolvendo pra cada
    campo o top_k mais provável em vez de resolver pra um único item (essa é
    a diferença central pra extrair_dados()/filtragem(), que resolvem pra um
    único código e levantam erro em caso de ambiguidade).

    Todo parâmetro nome_do_* é opcional -- só entram no resultado os campos
    cujo nome_do_* foi informado. Cada top_k_* tem padrão 1 (só o mais
    provável). Pode passar nome, código, ou os dois misturados separados por
    vírgula (ex.: nome_do_curso="123456, engenharia civil").

    Com escopado=True (padrão), o escopo de um campo é o CONJUNTO de todos
    os códigos encontrados no ranking do campo anterior -- não só o
    primeiro colocado. Isso importa quando top_k_campus/top_k_centro > 1 ou
    quando o nome_do_centro/nome_do_campus tem múltiplos termos: se restringir
    ao top-1 apenas, um centro/campus candidato genuíno (mas não o melhor
    colocado) fica de fora do escopo, e tudo que só existe nele (ex.: uma
    unidade de um centro diferente do topo) nunca aparece no ranking de
    unidade/curso, mesmo tendo sido encontrado corretamente no ranking de
    centro/campus. Com escopado=False, cada campo busca de forma totalmente
    independente, sobre a base inteira.

    Retorna um dict só com as chaves pedidas. Centro/unidade/curso vêm com o
    código de quem eles pertencem (não precisa buscar de novo -- já está no
    próprio item):

        {
          "curso": [
            {"nome_do_curso": "Ciência da Computação - ...", "codigo_do_curso": 1100, "pertence_a_unidade_de_codigo": 110},
          ],
          "unidade": [
            {"nome_da_unidade": "Unidade Acadêmica de Sistemas e Computação - UASC", "codigo_da_unidade": 110, "pertence_ao_centro_de_codigo": 10},
          ],
          "centro": [
            {"nome_do_centro": "Centro de Engenharia Elétrica e Informática - CEEI", "codigo_do_centro": 10, "pertence_ao_campus_de_codigo": 1},
          ],
          "campus": [
            {"nome_do_campus": "Campina Grande", "codigo_do_campus": 1},
          ],
        }
    """
    resultado: dict[str, list[dict]] = {}

    campus_ranking: list[tuple[dict, float]] = []
    params_ufcg = {}

    if nome_do_campus:
        campus_ranking = _ranking_multi_termo(nome_do_campus, campi, "nome_do_campus", "codigo_do_campus", top_k_campus, min_similarity)
        resultado["campus"] = [_formatar_item_ranking(item, "nome_do_campus", "codigo_do_campus") for item, _ in campus_ranking]
        if campus_ranking:
            params_ufcg["codigo_do_campus"] = campus_ranking[0][0]["codigo_do_campus"]

    # Escopo = TODOS os campi do ranking, não só o primeiro (ver docstring).
    codigos_campus_escopo = ({item["codigo_do_campus"] for item, _ in campus_ranking} if (escopado and campus_ranking) else None)

    centro_ranking: list[tuple[dict, float]] = []
    if nome_do_centro:
        pool_centros = _filtrar_por_escopo(get_centros(), "codigo_do_campus", codigos_campus_escopo)
        centro_ranking = _ranking_multi_termo(nome_do_centro, pool_centros, "nome_do_centro", "codigo_do_centro", top_k_centro, min_similarity)
        resultado["centro"] = [_formatar_item_ranking(item, "nome_do_centro", "codigo_do_centro") for item, _ in centro_ranking]
        if centro_ranking:
            params_ufcg["codigo_do_centro"] = centro_ranking[0][0]["codigo_do_centro"]

    # Escopo = TODOS os centros do ranking, não só o primeiro (ver docstring).
    codigos_centro_escopo = ({item["codigo_do_centro"] for item, _ in centro_ranking} if (escopado and centro_ranking) else None)

    if nome_da_unidade:
        pool_unidades = _filtrar_por_escopo(get_unidades(), "codigo_do_campus", codigos_campus_escopo)
        pool_unidades = _filtrar_por_escopo(pool_unidades, "codigo_do_centro", codigos_centro_escopo)
        unidade_ranking = _ranking_multi_termo(nome_da_unidade, pool_unidades, "nome_da_unidade", "codigo_da_unidade", top_k_unidade, min_similarity)
        resultado["unidade"] = [_formatar_item_ranking(item, "nome_da_unidade", "codigo_da_unidade") for item, _ in unidade_ranking]
        if unidade_ranking:
            params_ufcg["codigo_da_unidade"] = unidade_ranking[0][0]["codigo_da_unidade"]

    if nome_do_curso:
        pool_cursos = _filtrar_por_escopo(get_cursos(), "codigo_do_campus", codigos_campus_escopo)
        curso_ranking = _ranking_cursos(nome_do_curso, pool_cursos, top_k_curso, min_similarity)
        resultado["curso"] = [_formatar_item_ranking(item, "nome_do_curso", "codigo_do_curso") for item, _ in curso_ranking]
        if curso_ranking:
            params_ufcg["codigo_do_curso"] = curso_ranking[0][0]["codigo_do_curso"]

    if periodo_de is None or periodo_ate is None:
        periodo_recente_data = requests.get(
            "https://eureca.sti.ufcg.edu.br/das-sig/v1/calendarios/periodo-corrente",
            timeout=30,
        )
        if periodo_recente_data.status_code == 200:
            periodo_recente = periodo_recente_data.json()[-1]["periodo"]
            if periodo_de is None and periodo_ate is None:
                periodo_de = periodo_recente
                periodo_ate = periodo_recente
            elif periodo_de is not None and periodo_ate is None:
                periodo_ate = periodo_recente
            elif periodo_de is None and periodo_ate is not None:
                periodo_de = "2001.1"

    kwargs = {"periodo_de": periodo_de, "periodo_ate": periodo_ate}
    if params_ufcg.get("codigo_do_curso") is not None:
        kwargs["codigo_do_curso"] = params_ufcg["codigo_do_curso"]
    elif params_ufcg.get("codigo_da_unidade") is not None:
        kwargs["codigo_da_unidade"] = params_ufcg["codigo_da_unidade"]
    elif params_ufcg.get("codigo_do_centro") is not None:
        kwargs["codigo_do_centro"] = params_ufcg["codigo_do_centro"]
    elif params_ufcg.get("codigo_do_campus") is not None:
        kwargs["codigo_do_campus"] = params_ufcg["codigo_do_campus"]
    professores_e_disciplinas = get_professores_periodo(**kwargs)

    if nome_da_disciplina:
        disciplina_ranking = _ranking_multi_termo(nome_da_disciplina, professores_e_disciplinas, "nome_da_disciplina", "codigo_da_disciplina", top_k_disciplina, min_similarity=0.01,)
        resultado["disciplina"] = [_formatar_item_ranking(item, "nome_da_disciplina", "codigo_da_disciplina") for item, _ in disciplina_ranking]

    if nome_do_professor:
        professor_ranking = _ranking_multi_termo(nome_do_professor, professores_e_disciplinas, "nome_do_professor", "matricula_do_professor", top_k_professor, min_similarity=0.01,)
        resultado["professor"] = [item for item, _ in professor_ranking]

    resultado["periodo"] = [{"periodo_de": periodo_de, "periodo_ate": periodo_ate}]
    return resultado


def get_professores_periodo(
    codigo_do_campus=None,
    codigo_do_centro=None,
    codigo_da_unidade=None,
    codigo_do_curso=None,
    periodo_de=None,
    periodo_ate=None
):
    conn = sqlite3.connect(UFCG_SQLITE)
    try:
        filtros = []
        parametros = []
        joins = """
            FROM inscricao i
            INNER JOIN professor p
                ON p.matricula_do_professor = i.matricula_do_professor
        """

        if periodo_de is not None:
            filtros.append("i.periodo >= ?")
            parametros.append(periodo_de)

        if periodo_ate is not None:
            filtros.append("i.periodo <= ?")
            parametros.append(periodo_ate)

        if codigo_do_campus is not None:
            filtros.append("""
                EXISTS (
                    SELECT 1 FROM unidade u
                    WHERE u.codigo_da_unidade = p.codigo_da_unidade
                      AND u.codigo_do_campus = ?
                )
            """)
            parametros.append(codigo_do_campus)

        if codigo_do_centro is not None:
            filtros.append("""
                EXISTS (
                    SELECT 1 FROM unidade u
                    WHERE u.codigo_da_unidade = p.codigo_da_unidade
                      AND u.codigo_do_centro = ?
                )
            """)
            parametros.append(codigo_do_centro)

        if codigo_da_unidade is not None:
            filtros.append("p.codigo_da_unidade = ?")
            parametros.append(codigo_da_unidade)

        if codigo_do_curso is not None:
            joins += """
                INNER JOIN estudante e
                    ON e.matricula_do_estudante = i.matricula_do_estudante
            """
            filtros.append("e.codigo_do_curso = ?")
            parametros.append(codigo_do_curso)

        where = ""

        if filtros:
            where = "WHERE " + "\nAND ".join(filtros)

        cursor = conn.execute(
            f"""
            SELECT DISTINCT
                p.nome_do_professor,
                p.matricula_do_professor,
                i.nome_da_disciplina,
                i.codigo_da_disciplina,
                i.turma
            {joins}
            {where};
            """,
            parametros,
        )

        colunas = [c[0] for c in cursor.description]
        return [dict(zip(colunas, linha)) for linha in cursor.fetchall()]

    finally:
        conn.close()
