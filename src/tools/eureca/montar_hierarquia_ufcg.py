import json
from pathlib import Path
from typing import Optional

DIRETORIO_TABELA_JSON = Path(__file__).resolve().parent
JSON_PATH = DIRETORIO_TABELA_JSON / "hierarquia_siglas" / "cursos.json"


def get_cursos(codigo_do_campus=None, codigo_do_centro=None, codigo_da_unidade=None, codigo_do_curso=None):
    codigo_do_campus = int(codigo_do_campus) if codigo_do_campus not in ("", None) else None
    codigo_do_centro = int(codigo_do_centro) if codigo_do_centro not in ("", None) else None
    codigo_da_unidade = int(codigo_da_unidade) if codigo_da_unidade not in ("", None) else None
    codigo_do_curso = int(codigo_do_curso) if codigo_do_curso not in ("", None) else None

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        cursos = json.load(f)

    for curso in cursos:
        curso["nome_do_curso"] = f"{curso['nome_do_curso']} - {curso['turno']} - {curso['modalidade_academica']}"
    
    if codigo_do_curso:
        curso_encontrado = [curso for curso in cursos if curso["codigo_do_curso"] == codigo_do_curso]
        return curso_encontrado if curso_encontrado else None
    
    if codigo_do_centro: return [curso for curso in cursos if curso["codigo_do_centro"] == codigo_do_centro]
    if codigo_do_campus: return [curso for curso in cursos if curso["codigo_do_campus"] == codigo_do_campus]
    if codigo_da_unidade: return [curso for curso in cursos if curso["codigo_da_unidade"] == codigo_da_unidade]
    return cursos


campus_centro_unidade = {"nome_do_campus": [], "nome_do_centro": [], "nome_da_unidade": [], "nome_do_curso": []}
for curso in get_cursos():
    campus_centro_unidade["nome_do_campus"].append(curso["nome_do_campus"])
    campus_centro_unidade["nome_do_curso"].append(curso["nome_do_curso"])
    campus_centro_unidade["nome_do_centro"].append(curso["nome_do_centro"])
    campus_centro_unidade["nome_da_unidade"].append(curso["nome_da_unidade"])

campus_centro_unidade["nome_do_campus"] = ", ".join(f"'{x}'" for x in set(campus_centro_unidade["nome_do_campus"]))
campus_centro_unidade["nome_do_curso"] = ", ".join(f"'{x}'" for x in set(campus_centro_unidade["nome_do_curso"]))
campus_centro_unidade["nome_do_centro"] = ", ".join(f"'{x}'" for x in set(campus_centro_unidade["nome_do_centro"]))
campus_centro_unidade["nome_da_unidade"] = ", ".join(f"'{x}'" for x in set(campus_centro_unidade["nome_da_unidade"]))


TABELAS = ("campus", "centro", "unidade", "curso", "estudante", "inscricao", "estagio", "professor",)

_ORDEM_NIVEIS = ["campus", "centro", "unidade", "curso"]

_CAMPO_CODIGO = {
    "campus": "codigo_do_campus",
    "centro": "codigo_do_centro",
    "unidade": "codigo_da_unidade",
    "curso": "codigo_do_curso",
}

_CAMPO_NOME = {
    "campus": "nome_do_campus",
    "centro": "nome_do_centro",
    "unidade": "nome_da_unidade",
    "curso": "nome_do_curso",
}

_CAMPO_PERTENCE = {
    # O extrator ainda pode devolver os nomes legados ``pertence_*``.
    "centro": {"campus": ("codigo_do_campus", "pertence_ao_campus_de_codigo")},
    "unidade": {
        "campus": ("codigo_do_campus", "pertence_ao_campus_de_codigo"),
        "centro": ("codigo_do_centro", "pertence_ao_centro_de_codigo"),
    },
    "curso": {
        "campus": ("codigo_do_campus", "pertence_ao_campus_de_codigo"),
        "centro": ("codigo_do_centro", "pertence_ao_centro_de_codigo"),
        "unidade": ("codigo_da_unidade", "pertence_a_unidade_de_codigo"),
    },
}


def buscar_dados_explicativos():
    dados_explicativos = {}
    _DIRETORIO_DESTE_MODULO = Path(__file__).resolve().parent
    with open(_DIRETORIO_DESTE_MODULO / "descricao_tabelas" / "campus" / "tabela.json", encoding="utf-8") as campus:
        campus = json.load(campus)
        nome_da_tabela = campus["nome_da_tabela"]
        dados_explicativos[nome_da_tabela] = {}
        if campus:
            for key, value in campus["dados"].items():
                dados_explicativos[nome_da_tabela][key] = value["description"]
        # dados_explicativos[nome_da_tabela]["nome_do_campus"] = campus_centro_unidade["nome_do_campus"]

    with open(_DIRETORIO_DESTE_MODULO / "descricao_tabelas" / "centro" / "tabela.json", encoding="utf-8") as centro:
        centro = json.load(centro)
        nome_da_tabela = centro["nome_da_tabela"]
        dados_explicativos[nome_da_tabela] = {}
        if centro:
            for key, value in centro["dados"].items():
                dados_explicativos[nome_da_tabela][key] = value["description"]
        # dados_explicativos[nome_da_tabela]["nome_do_centro"] = campus_centro_unidade["nome_do_centro"]

    with open(_DIRETORIO_DESTE_MODULO / "descricao_tabelas" /"unidade" / "tabela.json", encoding="utf-8") as unidade:
        unidade = json.load(unidade)
        nome_da_tabela = unidade["nome_da_tabela"]
        dados_explicativos[nome_da_tabela] = {}
        if unidade:
            for key, value in unidade["dados"].items():
                dados_explicativos[nome_da_tabela][key] = value["description"]
        # dados_explicativos[nome_da_tabela]["nome_da_unidade"] = campus_centro_unidade["nome_da_unidade"]

    with open(_DIRETORIO_DESTE_MODULO / "descricao_tabelas" / "curso" / "tabela.json", encoding="utf-8") as curso:
        curso = json.load(curso)
        nome_da_tabela = curso["nome_da_tabela"]
        dados_explicativos[nome_da_tabela] = {}
        if curso:
            for key, value in curso["dados"].items():
                dados_explicativos[nome_da_tabela][key] = value["description"]
        # dados_explicativos[nome_da_tabela]["nome_do_curso"] = campus_centro_unidade["nome_do_curso"]

    with open(_DIRETORIO_DESTE_MODULO / "descricao_tabelas" / "estudante" / "tabela.json", encoding="utf-8") as estudante:
        estudante = json.load(estudante)
        nome_da_tabela = estudante["nome_da_tabela"]
        dados_explicativos[nome_da_tabela] = {}
        if estudante:
            for key, value in estudante["dados"].items():
                dados_explicativos[nome_da_tabela][key] = value["description"]

    with open(_DIRETORIO_DESTE_MODULO / "descricao_tabelas" / "estagio" / "tabela.json", encoding="utf-8") as estagio:
        estagio = json.load(estagio)
        nome_da_tabela = estagio["nome_da_tabela"]
        dados_explicativos[nome_da_tabela] = {}
        if estagio:
            for key, value in estagio["dados"].items():
                dados_explicativos[nome_da_tabela][key] = value["description"]

    with open(_DIRETORIO_DESTE_MODULO / "descricao_tabelas" / "professor" / "tabela.json", encoding="utf-8") as professor:
        professor = json.load(professor)
        nome_da_tabela = professor["nome_da_tabela"]
        dados_explicativos[nome_da_tabela] = {}
        if professor:
            for key, value in professor["dados"].items():
                dados_explicativos[nome_da_tabela][key] = value["description"]

    with open(_DIRETORIO_DESTE_MODULO / "descricao_tabelas" / "inscricao" / "tabela.json", encoding="utf-8") as inscricao:
        inscricao = json.load(inscricao)
        nome_da_tabela = inscricao["nome_da_tabela"]
        dados_explicativos[nome_da_tabela] = {}
        if inscricao:
            for key, value in inscricao["dados"].items():
                dados_explicativos[nome_da_tabela][key] = value["description"]

    return dados_explicativos


def _ancestral_mais_proximo(nivel: str, niveis_presentes: list) -> Optional[str]:
    candidatos = [n for n in niveis_presentes if n in _CAMPO_PERTENCE.get(nivel, {})]
    return candidatos[-1] if candidatos else None


def _obter_codigo_pai(item: dict, campos: tuple[str, ...]) -> object:
    """Obtém o código relacional, aceitando o formato atual e o legado."""
    for campo in campos:
        if campo in item:
            return item[campo]
    raise KeyError(f"Nenhum dos campos de relacionamento foi encontrado: {campos}")


def _montar_hierarquia(entidades: dict, niveis_presentes: list) -> list:
    pai_de = {nivel: _ancestral_mais_proximo(nivel, niveis_presentes) for nivel in niveis_presentes[1:]}

    filhos_por_pai_e_codigo: dict[str, dict[str, list]] = {nivel: {} for nivel in _ORDEM_NIVEIS}
    for nivel, pai in pai_de.items():
        campos_pertence = _CAMPO_PERTENCE[nivel][pai]
        for item in entidades.get(nivel, []):
            codigo_pai = str(_obter_codigo_pai(item, campos_pertence))
            filhos_por_pai_e_codigo[pai].setdefault(codigo_pai, []).append(item)

    def _render(nivel: str, item: dict, profundidade: int) -> list:
        prefixo = ("    " * profundidade) + ("└─ " if profundidade else "- ")
        campo_codigo, campo_nome = _CAMPO_CODIGO[nivel], _CAMPO_NOME[nivel]
        linhas = [f'{prefixo}{campo_codigo}={item[campo_codigo]} | {campo_nome}="{item[campo_nome]}"']

        codigo_deste_item = str(item[campo_codigo])
        for nivel_filho in _ORDEM_NIVEIS:
            if pai_de.get(nivel_filho) == nivel:
                for filho in filhos_por_pai_e_codigo[nivel].get(codigo_deste_item, []):
                    linhas.extend(_render(nivel_filho, filho, profundidade + 1))
        return linhas

    nivel_raiz = niveis_presentes[0]
    linhas = []
    for item in entidades.get(nivel_raiz, []):
        linhas.extend(_render(nivel_raiz, item, 0))
    return linhas
