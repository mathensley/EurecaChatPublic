import os
import sqlite3
import json
import uuid
import asyncio
import time
import pandas as pd

from pathlib import Path
from pprint import pprint
from itertools import chain
from contextlib import closing
from functools import lru_cache
from typing import Any, Optional
from .emit_front import emit_front
from application.config import chat_sql

from langchain_core.tools import StructuredTool
from langchain_core.runnables import RunnableConfig
from langchain.tools import ToolRuntime
from src.helpers.context import Context
from .extrair_params_eficiente import buscar_ranking
from .gerenciador_expert_v2 import GerenciadorExpertV2
from .prompt_geral import DESCRICAO_SITUACAO, DOC_STRING_TOOL
from .eureca_bash.workdir import _extrai_exports_dir, criar_url_download
from .atributos_nao_permitidos_por_usuario import LISTA_DE_ATRIBUTOS_NAO_PERMITIDOS_POR_USUARIO, ColunasNaoPermitidasError


gerenciador_expert_v2: Optional[GerenciadorExpertV2] = GerenciadorExpertV2(llm=chat_sql)

# Schema: tabelas, descrições de coluna e visão textual para a docstring.
# Duplicado intencionalmente do que existe em gerenciador_expert_v2.py (a
# pedido: não alterar aquele arquivo). Se um dia as duas cópias divergirem
# na formatação da visão de tabelas, é aqui e lá que teria que corrigir.
TABELAS = ("campus", "centro", "unidade", "curso", "estudante", "inscricao", "estagio", "professor",)
SQLITE_DIR = Path(os.getenv("SQLITE_DIR", ".")).expanduser()
DB_PATH = (SQLITE_DIR / f"ufcg.sqlite").resolve()
if not DB_PATH.is_file(): raise FileNotFoundError(f"Banco consolidado não encontrado: {DB_PATH}")


def _carregar_dados_explicativos() -> dict:
    dados_explicativos = {}
    for tabela in TABELAS:
        caminho = Path(__file__).resolve().parent / "descricao_tabelas" / tabela / "tabela.json"
        with open(caminho, encoding="utf-8") as f:
            bruto = json.load(f)
        nome_da_tabela = bruto["nome_da_tabela"]
        dados_explicativos[nome_da_tabela] = {campo: valor["description"] for campo, valor in bruto.get("dados", {}).items()}
    return dados_explicativos


dados_explicativos = _carregar_dados_explicativos()
def _carregar_visao_tabelas() -> dict[str, dict[str, dict[str, str]]]:
    visao = {}
    with closing(sqlite3.connect(f"{DB_PATH.as_uri()}?mode=ro", uri=True)) as conn:
        for tabela in TABELAS:
            visao[tabela] = {}
            for _, nome, tipo, *_ in conn.execute(f'PRAGMA table_info("{tabela}")').fetchall():
                visao[tabela][nome] = { "tipo": tipo, "descricao": dados_explicativos.get(tabela, {}).get(nome, ""), }
    return visao


visao_tabelas = _carregar_visao_tabelas()
schema = {
    tabela: {coluna: info["tipo"] or "TEXT" for coluna, info in colunas.items()}
    for tabela, colunas in visao_tabelas.items()
}


async def eureca_database(
        runtime: ToolRuntime[Context],
        config: RunnableConfig,
        query: str = "",
        nomes_dos_campus: Any = None,
        nomes_dos_centros: Any = None,
        nomes_das_unidades: Any = None,
        nomes_dos_cursos: Any = None,
        nomes_das_disciplinas: Any = None,
        nomes_dos_professores: Any = None,
        periodo_de_busca_de: Any = None,
        periodo_de_busca_ate: Any = None,
        gerar_csv: Any = False
    ):

    inicio = time.perf_counter()
    await emit_front(config=config, mensagem="Buscando pelos dados do Eureca.")

    entidades = await asyncio.to_thread(
        buscar_ranking,
        nome_do_campus=nomes_dos_campus, top_k_campus=3,
        nome_do_centro=nomes_dos_centros, top_k_centro=10,
        nome_da_unidade=nomes_das_unidades, top_k_unidade=10,
        nome_do_curso=nomes_dos_cursos, top_k_curso=20,
        nome_da_disciplina=nomes_das_disciplinas, top_k_disciplina=30,
        nome_do_professor=nomes_dos_professores, top_k_professor=20,
        periodo_de=periodo_de_busca_de, periodo_ate=periodo_de_busca_ate,
        min_similarity=10.0,
        escopado=True
    )

    entidades = list(chain.from_iterable(entidades.values()))
    global gerenciador_expert_v2

    try:
        resultado = await gerenciador_expert_v2.ainvoke(
            entidades=entidades,
            query=query,
            max_retries=3,
            tipo_user=(
                runtime.context.normalized_user_role
                if runtime.context is not None and runtime.context.is_authenticated
                else "anon"
            )
        )
    except ColunasNaoPermitidasError as e:
        nomes = sorted({c.split(".", 1)[1] for c in e.colunas})
        return {"erro": f"Seu perfil não está autorizado a acessar os dados de {', '.join(nomes)}."}

    tempo_decorrido = time.perf_counter() - inicio

    resposta = {
        "input_tokens": resultado["metadados_llm"].usage_metadata.get("input_tokens"),
        "output_tokens": resultado["metadados_llm"].usage_metadata.get("output_tokens"),
        "tempo decorrido_segundos": float(f"{tempo_decorrido:.2f}"),
        "resultado": resultado["resultado"],
        "sql_criado": resultado["sql_criado"],
        "dados_de_referencia_descobertos_na_ferramenta": resultado["dados_de_referencia"],
        "observacao_sql": "Verifique se o SQL retornado foi feito corretamente olhando os JOINS, WHERE, valores, ENUMS observando a descrição da ferramenta eureca_database."
    }

    max_linhas = 100
    resultado = resposta.get("resultado")

    if isinstance(resultado, str):
        try:
            resultado = json.loads(resultado)
            resposta["resultado"] = resultado
        except (json.JSONDecodeError, TypeError): return resposta

    if not isinstance(resultado, list): return resposta

    solicitar_csv = gerar_csv is True or str(gerar_csv).strip().lower() in {"1", "true", "sim"}
    excedeu_limite = len(resultado) > max_linhas

    async def criar_dados_csv():
        exports_dir = Path(await _extrai_exports_dir(config))

        def gerar_arquivo_csv():
            df = pd.DataFrame(resultado)
            nome_arquivo = f"eureca_query_{uuid.uuid4().hex}.csv"
            caminho = exports_dir / nome_arquivo
            df.to_csv(caminho, index=False, encoding="utf-8-sig")
            url_download = criar_url_download(exports_dir.parent, nome_arquivo)

            return {
                "tipo": "arquivo",
                "nome_arquivo": nome_arquivo,
                "url_download": url_download,
                "total_linhas": len(resultado),
                "colunas": list(df.columns),
                "preview": resultado[:5],
                "observacao": f"Baixe o arquivo completo em [{nome_arquivo}]({url_download}).",
            }

        return await asyncio.to_thread(gerar_arquivo_csv)

    if excedeu_limite:
        dados_csv = await criar_dados_csv()
        observacao = (f"Saída contém mais de {max_linhas} linhas; veja a prévia e baixe o CSV completo em \n[{dados_csv['nome_arquivo']}]({dados_csv['url_download']}).")
        dados_csv["observacao"] = observacao
        return dados_csv

    if solicitar_csv:
        resposta["arquivo_csv"] = await criar_dados_csv()

    return resposta


def formatar_visao_tabelas(tipo_user: str) -> str:
    ocultas = LISTA_DE_ATRIBUTOS_NAO_PERMITIDOS_POR_USUARIO[tipo_user]
    linhas = []
    for tabela, colunas in visao_tabelas.items():
        linhas += [f"• Tabela: {tabela}", "• Colunas:"]
        for nome, info in colunas.items():
            if nome.lower() in ocultas.get(tabela, []): continue
            sufixo = f": {info['descricao']}" if info["descricao"] else ""
            linhas.append(f"\t- {nome} ({info['tipo']}){sufixo}")
    return "\n".join(linhas)


def descricao_tool_eureca(tipo_user: str) -> str:
    return DOC_STRING_TOOL.format(
        formato_tabela=formatar_visao_tabelas(tipo_user),
        descricao_situacao=DESCRICAO_SITUACAO,
    ).strip()


# O agente registra uma descrição segura para anônimos. O middleware cria uma cópia com a descrição do perfil em cada chamada ao modelo.
EURECA_DATABASE_TOOL = StructuredTool.from_function(
    coroutine=eureca_database,
    name="eureca_database",
    description=descricao_tool_eureca("anon"),
)


@lru_cache(maxsize=None)
def criar_tool_eureca(tipo_user: str) -> StructuredTool:
    """Atalho para inspeção manual da descrição de cada perfil."""
    return StructuredTool.from_function(
        coroutine=eureca_database,
        name="eureca_database",
        description=descricao_tool_eureca(tipo_user or "anon"),
    )


if __name__ == "__main__":
    tipo_user = "Professor"
    config_teste: RunnableConfig = { "configurable": { "thread_id": "teste-usuario-123", "callbacks_sio": []}}

    tool = criar_tool_eureca(tipo_user)
    print(tool.description)

    runtime_teste = ToolRuntime(
        state={}, context=Context(token="teste", user_role=tipo_user, user_indentifier="teste"),
        config=config_teste, stream_writer=lambda _: None, tool_call_id=None, store=None,
    )
    resposta = asyncio.run(eureca_database(
        runtime=runtime_teste,
        config=config_teste,
        query="Quais são os professores que estão lecionando em curso para Levi em 2026.2?",
        nomes_dos_campus="campina grande",
        nomes_dos_centros="ceei",
        nomes_das_unidades="uasc",
        nomes_dos_cursos="ciencia da computacao",
        nomes_das_disciplinas="",
        nomes_dos_professores="balby, eliane cristina",
        periodo_de_busca_de="2026.1",
        periodo_de_busca_ate="2026.1",
        gerar_csv=False,
    ))

    pprint(resposta, indent=4, sort_dicts=False, width=200)
