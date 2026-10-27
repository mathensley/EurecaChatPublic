import logging
import asyncio
from datetime import datetime
from ..utils.run_tool import run_tool
from ...helpers.func_utils import get_func_info
from application.config import chat_sql, URL_SIG
from .aux_estagios_ufcg import get_todos_estagios
from langchain_core.runnables import RunnableConfig
from ...sql.gerenciador_expert import GerenciadorExpert
from ...helpers.tool_handlers.campi_for_tools import campi
from ...helpers.tool_handlers.fuzzy_matching import extract_most_similar
from ...helpers.tool_handlers.tool_requests import buscar_curso_por_nome_ou_codigo


async def buscar_estagios(
    config: RunnableConfig,
    query: str,
    ano_de: str,
    ano_ate: str,
    nome_do_campus: str,
    nome_do_curso: str,
) -> list:
    """
    Buscar informações sobre estágios dos estudantes de uma centro da unidade de um curso.
    Se for informado apenas um ano, usar o mesmo ano no parâmetrio ano_de e ano_ate.
    Se for informado apenas um ano e você identificar que é a data de ínicio, mas que não é a de término, então só passe o ano apenas em ano_de.
    Se for informado apenas um ano e você identificar que é a data limite, mas que não é de início, então so passe o ano apenas em ano_ate.

    Args:
        query (str): Pergunta do usuário.
        ano_de (str): Ano em valor inteiro de início dos estágios (use o ano perguntado, se não souber use vazio ""). Use a string vazia quando não houver limite inicial.
        ano_ate (str): Ano em valor inteiro do ano limite para busca (use o ano perguntado, se não souber use vazio ""). Use a string vazia quando não houver limite final.
        nome_do_campus (str): O nome do campus ou o código numérico dele, pode ser um desses a seguir: Campina Grande, Cajazeiras, Sousa, Patos, Cuité, Sumé e Pombal. Use a string vazia quando não houver filtro de campus.
        nome_do_curso (str): Nome do curso ou código numérico dele. Use a string vazia quando não houver filtro.
    
    Returns:
        Lista com informações relevantes de estágio.
    """
    
    query = str(query)
    nome_do_campus = str(nome_do_campus)
    nome_do_curso = str(nome_do_curso)
    ano_de = 0 if ano_de == "" else int(ano_de) 
    ano_ate = int(str(datetime.now().year)) if ano_ate == "" else int(ano_ate)

    func_name, parametros_str = get_func_info()
    
    try:
        callbacks = config["configurable"].get("callbacks_sio")
        for cb in callbacks:
            if hasattr(cb, 'emit'):
                await cb.emit("status", {"resposta": "Buscando dados por estágios"})
            break
    except:
        pass
    
    try:
        func_name, parametros_str = get_func_info()
        print(f"🔍 Chamando {func_name}({parametros_str})")

        estagios, mensagem_sucesso = await filtragem(nome_do_campus=nome_do_campus, nome_do_curso=nome_do_curso, params={ "inicio-de": ano_de, "fim-ate": ano_ate })
        if len(estagios) == 0: return f"{'Erro: Não foram encontrados estagiários.'} {'Causas possíveis: Possa ser que o estágio não seja obrigatório no curso desejado, tente buscando pelo setor do curso.' if nome_do_curso else ''}"

        columns = []
        if nome_do_campus != "":
            columns += ["campus", "nome_do_campus"]
        if nome_do_curso != "":
            columns += ["codigo_do_curso", "nome_do_curso"]
        
        gerenciador = GerenciadorExpert(table_name="Estagio", json_data=estagios, llm=chat_sql)
        # return gerenciador.execute_sql_estatico("SELECT DISTINCT(auxilio_transporte_diario) FROM ESTAGIO", estagios)
        result = gerenciador.invoke_sql(input=query, columns=columns, show=False)
        return { "resposta": result, "observação": mensagem_sucesso }

    except Exception:
        raise


async def extrair_ano(data_str):
    if not data_str: return None
    try: return datetime.strptime(data_str.split(" ")[0], "%Y-%m-%d").year
    except: return None


async def filtragem(nome_do_campus, nome_do_curso, params):    
    mensagem = ""
    if nome_do_campus and not nome_do_curso:
        codigo_campus = extract_most_similar(nome_do_campus, campi, "campus")[0][0]["codigo"]
        params["campus"] = codigo_campus
        mensagem = f"Dados obtidos para o campus de {nome_do_campus}."
    
    elif nome_do_curso:
        cursos_encontrados, _ = await buscar_curso_por_nome_ou_codigo(nome_do_curso, nome_do_campus, URL_SIG)
        if len(cursos_encontrados) > 1:
            cursos_ambiguos = [f"- {c['descricao']} (Código: {c['codigo_do_curso']}), {c['nome_do_campus']}" for c in cursos_encontrados]
            raise ValueError("Foram encontrados múltiplos cursos semelhantes ao informado.\n\nCursos encontrados:\n\n" + "\n".join(cursos_ambiguos))
        
        curso_escolhido = cursos_encontrados[0]
        codigo_curso = str(curso_escolhido["codigo_do_curso"])
        params["codigo_do_curso"] = codigo_curso
        print(curso_escolhido)
        mensagem = f"Dados obtidos para o curso de {curso_escolhido['descricao']} do campus de {curso_escolhido['nome_do_campus']}."

    else: mensagem = "Dados obtidos para toda a UFCG"

    # Chama a função auxiliar de aux_estagios_ufcg filtrando pelos params.
    return get_todos_estagios(params), mensagem


if __name__ == "__main__":
    asyncio.run(
        run_tool(
            "src.tools.estudante.buscar_estagios.buscar_estagios",
            config=RunnableConfig,
            query="Quantos estágiarios há entre 2025 e 2026?",
            nome_do_campus="campina grande",
            nome_do_curso="ciencia da computacao - 108095",
            ano_de="2023",
            ano_ate="2026",
        )
    )
