import logging, asyncio

from application.config import URL_SIG, chat_sql

from ..utils.run_tool import run_tool

from ...helpers.func_utils import get_func_info
from ...helpers.request_utils import make_request
from ...helpers.tool_handlers.campi_for_tools import campi
from ...helpers.tool_handlers.tool_utils import remover_acentos
from ...helpers.tool_handlers.fuzzy_matching import extract_most_similar
from ...helpers.print_tool_call import print_tool_output, print_tool_call
from ...sql.gerenciador_expert import GerenciadorExpert
from langchain_core.runnables import RunnableConfig


async def buscar_todos_os_cursos(config: RunnableConfig | None = None, query: str = "", campus: str = "") -> list:
    """
    Buscar informações gerais relativo a todos os cursos da UFCG.
    Use esta função quando o usuário fizer uma pergunta **geral** sobre cursos da UFCG, sem mencionar nomes específicos.
    **Não** fornece informação de vaga, **nem** de estudantes do curso e **nem** das disciplinas dos cursos.
    
    - **NÃO** use essa tool se a pergunta envolver:
     - Um curso específico;
     - Informações sobre vagas de curso;
     - Informações sobre estudantes dos curso;
     - Informações sobre as disciplinas de um curso.

    - Essa tool só responde os seguintes dados para todos os cursos e nada além disso:

    {
        "codigo_do_curso",
        "descricao",
        "status",
        "grau_do_curso",
        "codigo_do_setor",
        "nome_do_setor",
        "campus",
        "nome_do_campus",
        "turno",
        "periodo_de_inicio",
        "data_de_funcionamento",
        "codigo_inep",
        "modalidade_academica",
        "curriculo_atual",
        "area_de_retencao",
        "ciclo_enade"
    }
    
    Args:
        query (str): pergunta completa feita pelo usuário.
        campus (str): O nome do campus ou o código numérico dele, pode ser um desses a seguir: Campina Grande, Cajazeiras, Sousa, Patos, Cuité, Sumé e Pombal. Se desejar saber de cada campus ou de todos os campi, use a string vazia ''.
    Returns:
        Informações que ajude a responder a pergunta feita pelo usuário.
    """
    if not config:
        config = RunnableConfig()

    query = str(query)
    campus = str(campus)
    func_name, parametros_str = get_func_info()
    
    try:
        callbacks = config["configurable"].get("callbacks_sio")
        for cb in callbacks:
            if hasattr(cb, 'emit'):
                await cb.emit("status", {"resposta": "Buscando pelos dados dos cursos"})
            break
    except:
        pass
    
    
    try:
        print_tool_call(func_name, parametros_str)

        params = {"status": "ATIVOS", "campus": campus if (campus.isdigit() or campus == "") else extract_most_similar(campus, campi, "campus")[0][0]['codigo']}
        cursos = await make_request(f"{URL_SIG}/cursos", params)
        if not cursos: raise ValueError("Não foi possível obter os cursos ou nenhum curso foi encontrado")

        todos_cursos_graduacao = []
        for curso in cursos:
            grau_do_curso = remover_acentos(curso["grau_do_curso"])
            if grau_do_curso == "GRADUACAO":
                curso["grau_do_curso"] = grau_do_curso
                todos_cursos_graduacao.append(curso)

        observacao = """
        Observação:
        - Essa é a tabela de cursos da UFCG. Nunca informe 'UFCG' como filtro em where, pois a UFCG é a universidade e não o curso, e esta é a tabela de cursos.
        - Ignore o nome do curso perguntado, se alguém perguntar por um ou mais curso específico, assuma que não sabe e selecione a coluna nome do curso sem filtro.
        - Ignore o nome do centro perguntado. Se alguém perguntar por um ou mais curso específico(s), assuma que não sabe e selecione as colunas nome do curso sem filtro.
        """
        columns = ["nome_do_campus", "codigo_do_campus"] if campus != "" else []
        with GerenciadorExpert(table_name="Curso", json_data=todos_cursos_graduacao, llm=chat_sql) as gerenciador:
            if not query:
                return gerenciador.execute_sql_estatico("SELECT * FROM Curso", todos_cursos_graduacao)
            result = gerenciador.invoke_sql(input=query, columns=columns, observacao=observacao, to_dict=True)
            print_tool_output(func_name, parametros_str, result)
            return result
    
    except Exception:
        raise


if __name__ == "__main__":
    asyncio.run(
        run_tool(
            "src.tools.curso.buscar_todos_os_cursos.buscar_todos_os_cursos",
            config=RunnableConfig,
            query="Quantos cursos de graduação existem?",
            campus="Campina Grande"
        )
    )
