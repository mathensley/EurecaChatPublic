import json
import asyncio
import operator
import sqlite3
import application.http_client as http_client

from typing import Any
from pathlib import Path
from datetime import datetime
from sqlparse.sql import Where
from typing_extensions import TypedDict, Annotated

from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END

from application.config import analysis_model
from application.db.sqlite_paths import SQLITE_DIR

# Import dos métodos que puxam todos os dadosd de cada tabela
from src.tools.estudante.buscar_dados_gerais_de_todos_estudantes import buscar_dados_gerais_de_todos_estudantes
from src.tools.disciplina.buscar_estudantes_disciplinas import buscar_estudantes_disciplinas
from src.tools.curso.buscar_todos_os_cursos import buscar_todos_os_cursos

from src.sql.gerenciador_expert import GerenciadorExpert
from src.tools.utils.run_tool import run_tool
from src.prompts.anomaly_agent_prompt import ANOMALY_AGENT_PROMPT
from src.helpers.dict_to_md_table import dicts_to_markdown_table

ROOT_DIR = Path(__file__).resolve().parents[2]
# Caminho do esqueleto de todas as tabelas
TABLES_DIR = ROOT_DIR / "src" / "tools" / "eureca" / "descricao_tabelas"
DB_PATH = SQLITE_DIR / "ufcg.sqlite"

# Caminho da pasta onde serão gerados os relatórios
ANALYSIS_DIR = SQLITE_DIR / "analise"
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

RELATORIOS_DIR = ANALYSIS_DIR / "relatorios"
RELATORIOS_DIR.mkdir(parents=True, exist_ok=True)

TABLE_NAMES = ["campus", "centro", "curso", "estagio", "estudante", "inscricao", "professor", "unidade"]


class AnomalyAgentState(TypedDict, total=False): # total=False permite que o estado seja montado ao longo da execução
    nome_tabela: str
    esqueleto: dict[str, dict] # {"nome_tabela": {"mapper": {"type": type, "description": description}, ...}}

    resultados: Annotated[list[dict], operator.add] # Resultados das análises
    erros: Annotated[list[dict], operator.add] # Erros encontrados durante as análises

    caminho_relatorio: str # Caminho do relatório de anomalias


async def carregar_esqueleto(state: AnomalyAgentState) -> dict:
    await http_client.init_client()
   
    nome_tabela = state["nome_tabela"]
    esqueleto = await _view_tables_raw(nome_tabela)
    
    return {
        "nome_tabela": nome_tabela,
        "esqueleto": esqueleto,
        "resultados": [],
        "erros": [],
    }

async def _view_tables_raw(table_name: str):
    if table_name not in TABLE_NAMES:
        raise ValueError(f"Erro: Não foi possível encontrar a tabela {table_name}. \nTabelas disponíveis: {TABLE_NAMES}")

    table_path = TABLES_DIR / table_name / "tabela.json"
    with open(table_path, "r", encoding="utf-8") as file:
        tabela = json.load(file)
    
    tabela = tabela["dados"]

    mapped_table = {}
    for key, value in tabela.items():
        mapped_table[value["mapper"]] = {
            "type": value["type"],
            "description": value["description"]
        }

    return mapped_table


async def analisar_atributo(state: AnomalyAgentState) -> dict:
    nome_tabela = state["nome_tabela"]
    esqueleto = state["esqueleto"]
    atributos = list(esqueleto.keys())

    resultados = []
    erros = []

    for atributo in atributos:
        # Parâmetros úteis na análise da tabela de Estudantes
        if "estudante" in nome_tabela.lower():
            cenarios = [True, False]
        else:
            cenarios = [None]

        for so_ativos in cenarios:
            try:
                resultado = await analisar_um_atributo(
                    nome_tabela=state["nome_tabela"],
                    nome_atributo=atributo,
                    esqueleto=esqueleto[atributo],
                    so_ativos=so_ativos
                )

                resultados.append(resultado)

            except Exception as e:
                erros.append({
                    "atributo": atributo,
                    "error": str(e)
                })

    return {
        "resultados": resultados,
        "erros": erros
    }


def query_execute(query: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(query)
        return [dict(row) for row in cursor.fetchall()]


async def analisar_um_atributo(nome_tabela: str, nome_atributo: str, esqueleto: dict, so_ativos: bool | None):
    import re
    await http_client.init_client()

    try:
        filtro_situacao = " AND situacao = 'ativo'" if so_ativos else ""
        prompt = ANOMALY_AGENT_PROMPT.format(
            nome_tabela=nome_tabela,
            nome_atributo=nome_atributo,
            tipo=esqueleto["type"],
            descricao=esqueleto["description"],
            filtro_situacao=filtro_situacao,
        )

        # Chama o LLM diretamente para gerar a SQL (não usa invoke_sql do GerenciadorExpert,
        # pois o prompt é especializado e não encaixa no esquema .format() do gerenciador).
        response = analysis_model.invoke(prompt)
        sql = response.content.strip()
        sql = re.sub(r"```sql|```", "", sql).strip()

        anomalias = query_execute(query=sql)

        return {
            "nome_tabela": nome_tabela,
            "nome_atributo": nome_atributo,
            "esqueleto": esqueleto,
            "so_ativos": so_ativos,
            "anomalias": anomalias,
            "sql_executada": sql,
        }
    finally:
        await http_client.close_client()


async def escrever_relatorio(state: AnomalyAgentState) -> dict:
    data_hora = datetime.now().strftime("%d-%m-%Y_%H-%M")
    data = data_hora.split("_")[0]

    res_dir = RELATORIOS_DIR / f"relatorios-{data}" / state["nome_tabela"] 
    res_dir.mkdir(parents=True, exist_ok=True)

    nome_tabela = state["nome_tabela"]
    esqueleto = state["esqueleto"]

    resultados = state.get("resultados", [])
    erros = state.get("erros", [])

    # Agrupar resultados por atributo
    por_atributo = {}
    for r in resultados:
        por_atributo.setdefault(r["nome_atributo"], []).append(r)

    # Agrupar erros por atributo
    erros_por_atributo = {}
    for e in erros:
        erros_por_atributo.setdefault(e.get("atributo"), []).append(e)

    caminho = None

    for atributo in esqueleto.keys():
        snaps = por_atributo.get(atributo, [])
        erros_attr = erros_por_atributo.get(atributo, [])

        # Se não há análises nem erros para este atributo, pula
        if not snaps and not erros_attr:
            continue
        
        # Escrita do relatório
        caminho = res_dir / f"relatorio_{atributo}_{data}.md"    
        with open(caminho, "w", encoding="utf-8") as f:
            # Cabeçalho
            f.write(f"# Relatório — {nome_tabela}\n\n")
            f.write(f"**Gerado em:** {data_hora}\n\n")
            f.write(f"Durante o uso da interface EurecaAPI, notamos que alguns dados vindos da interface possuem incoerências, o que impacta diretamente com o desempenho da nossa aplicação, enviesando métricas e resultados aplicados sobre esses dados. Dessa forma, elaboramos esse relatório como forma de facilitar a identificação e correção dessas incoerências, de modo que auxilie na correção desses dados.\n\n")

            # Snapshot de referência para calcular o resumo do atributo:
            # prefere o "total" (so_ativos is False); se não houver, aceita o
            # único snapshot disponível (so_ativos is None para tabelas não-Estudante).
            snap_ref = next(
                (r for r in snaps if r.get("so_ativos") is False),
                snaps[0] if snaps else None,
            )

            if snap_ref:
                anomalias_ref = snap_ref.get("anomalias", [])
                qtd_anomalias = sum(int(item.get("qtd", 0)) for item in anomalias_ref)
                len_anomalias = len(anomalias_ref)
            else:
                continue

            tipo_attr = esqueleto[atributo].get("type", "?")
            desc_attr = esqueleto[atributo].get("description", "?")
            f.write(f"### Atributo: {atributo}\n")
            f.write(f"**Tipo:** {tipo_attr}\n")
            f.write(f"**Descrição:** {desc_attr}\n\n")
            f.write(f"O atributo **{atributo}** possui **{qtd_anomalias}** anomalia(s) distribuidas em **{len_anomalias}** instâncias.\n\n")

            for r in snaps:
                if r.get("so_ativos") is not None:
                    snap_label = "ativos" if r.get("so_ativos") else "total"
                    f.write(f"#### Escopo: {snap_label.capitalize()}\n\n")

                # Query utilizada na geração das anomalias:
                f.write("**Query executada:**\n")
                f.write(f"```sql\n{r.get('sql_executada', 'N/A')}\n```\n\n")

                anomalias = r.get("anomalias", [])
                if anomalias:
                    f.write("**Anomalias encontradas:**\n\n")
                    f.write(dicts_to_markdown_table(anomalias))
                    f.write("\n\n")
                else:
                    f.write("_Nenhuma anomalia encontrada neste snapshot._\n\n")

            if erros_attr:
                f.write("## Erros encontrados na análise\n\n")
                f.write("| Atributo | Erro |\n")
                f.write("|---|---|\n")
                for e in erros_attr:
                    f.write(f"| {e.get('atributo', '?')} | {e.get('error', '?')} |\n")

    return {"caminho_relatorio": str(res_dir)}


def create_graph():
    graph = StateGraph(AnomalyAgentState)

    graph.add_node("carregar_esqueleto", carregar_esqueleto)
    graph.add_node("analisar_atributo",  analisar_atributo)
    graph.add_node("escrever_relatorio", escrever_relatorio)

    graph.add_edge(START,                "carregar_esqueleto")
    graph.add_edge("carregar_esqueleto", "analisar_atributo")
    graph.add_edge("analisar_atributo",  "escrever_relatorio")
    graph.add_edge("escrever_relatorio", END)

    workflow = graph.compile()
    return workflow


async def execute(tabelas: list[str] = None):
    if not tabelas:
        tabelas = TABLE_NAMES
    
    analise = []
    for tabela in tabelas:
        workflow = create_graph()

        estado_inicial = {
            "nome_tabela": tabela,
            "resultado": [],
            "erros": [],
        }

        resultado = await workflow.ainvoke(estado_inicial)
        analise.append(resultado)

    return analise

# Para executar, altere as tabelas manualmente no parâmetro "tabelas"
if __name__ == "__main__":
    asyncio.run(
        execute(
            tabelas=[]
        )
    )
