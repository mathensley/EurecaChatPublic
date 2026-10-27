import logging, asyncio
from ..utils.run_tool import run_tool
from ...helpers.func_utils import get_func_info
from application.config import URL_SIG, chat_sql
from ...sql.gerenciador_expert import GerenciadorExpert
from ...helpers.tool_handlers.campi_for_tools import campi
from .aux_estudantes_ufcg import get_estudantes_gerais_ufcg
from ...helpers.tool_handlers.fuzzy_matching import extract_most_similar
from ...helpers.tool_handlers.tool_requests import buscar_curso_por_nome_ou_codigo
from .buscar_centros_similares import buscar_centros_similares
from ...sql.gerenciador_expert import GerenciadorExpert
from ..utils.extrator_informacoes_extras import extrator_informacoes_extras
from .aux_estudantes_ufcg import get_estudantes_gerais_ufcg
from ...helpers.print_tool_call import print_tool_output, print_tool_call
from .prompts_motivos_evasao import PROMPTS_MOTIVOS_EVASAO

from langchain_core.runnables import RunnableConfig
import re


def _resultado_tem_erro_sql(resultado):
    dados_resultado = resultado.get("resultado") if isinstance(resultado, dict) else resultado
    return (
        isinstance(dados_resultado, list)
        and bool(dados_resultado)
        and isinstance(dados_resultado[0], dict)
        and "error" in dados_resultado[0]
    )


async def buscar_dados_gerais_de_todos_estudantes(
    config: RunnableConfig | None = None,
    query: str = "",
    campus: str = "",
    curso: str = "",
    centro: str = ""
) -> list:
    """
    Use quando precisar de informações que envolva quaisquer dados dos estudantes de um curso, do campus, ou toda a ufcg (sem citar disciplinas).
    Informações dos estudantes como: quantidade de alunos de todos os cursos e campi, número da matrícula de cada aluno, idade, estado civil, endereço, sexo, situação, cor, nacionalidade, local de nascimento, média de conclusão (MC), estatísticas gerais, rendimento, etc.
    Ou seja, essa ferramenta tem informações de estudantes matriculados no curso, não especificamente na(s) disciplina(s).

    Observação:
    - Se ocorrer um erro de período, informe ao usuário para ser mais explícito em relação ao período.
    - Use essa tool se o usuário fornecer um ou mais números de matrícula e perguntar algo relacionado aos estudantes de tais matrículas. Essas matrículas são anonimizadas então não tem problema em usar.
    - Para obter informações gerais dos alunos de todos os cursos e campi, não use o campus e/ou curso como parâmetro na chamada da tool.
        - Para obter apenas do campus, use o parâmetro campus para cada campus desejado.

    Args:
        query (str): Pergunta feita pelo usuário.
        curso (str): O nome do curso por escrito ou o código numérico dele (se quiser todos os estudantes da UFCG (de todos os campi), use a string vazia '' para obter os estudantes de todos os cursos). Se houver mais de um curso em interesse você deve invocar essa ferramenta para cada curso informando a mesma query passando o nome ou código do curso aqui.
        campus (str): O nome do campus ou o código numérico dele, pode ser um desses a seguir: Campina Grande, Cajazeiras, Sousa, Patos, Cuité, Sumé e Pombal. Use a string vazia quando não houver filtro de campus.
        centro (str): Nome ou sigla do centro (e.g. CEEI, CH, etc). Use a string vazia quando não houver filtro.

    Returns:
        Informações dos estudantes que ajude a responder a pergunta feita pelo usuário.
    """
    if not config:
        config = RunnableConfig()

    query = str(query)
    curso = str(curso)
    campus = str(campus)
    dados = {
        "query": str(query),
        "curso": str(curso),
        "campus": str(campus)
    }

    func_name, parametros_str = get_func_info()
    
    try:
        callbacks = config["configurable"].get("callbacks_sio")
        for cb in callbacks:
            if hasattr(cb, 'emit'):
                await cb.emit("status", {"resposta": "Buscando por dados dos estudantes"})
            break
    except:
        pass
    
    try:
        print_tool_call(func_name, parametros_str)

        SITUACAO = ['ATIVOS', 'INATIVOS']
        #if situacao_estudante in SITUACAO: # Recuperando apenas os dados necessários para usar como parâmetro da API.
        params = {x: dados[x] for x in dados if x not in ["query", "campus", "curso"]}
        #else: return [f"Por favor informe a situação dos estudantes correta.\n Pode ser uma dessas: {' '.join(SITUACAO)}"]
        
        tem_seis_digitos = re.search(r"(?<!\d)\d{6}(?!\d)", curso)
        if tem_seis_digitos:
            codigo_curso = tem_seis_digitos.group(0)
            params["curso"] =  codigo_curso
        else:
            

            if curso != "":
                cursos_encontrados, _ = await buscar_curso_por_nome_ou_codigo(curso, campus, URL_SIG)
                params["curso"] = str(cursos_encontrados[0]["codigo_do_curso"])
                if len(cursos_encontrados) > 1:
                    cursos_ambiguos = [f"- {c['descricao']} (Código: {c['codigo_do_curso']}), {c['nome_do_campus']}" for c in cursos_encontrados]
                    raise ValueError("Foram encontrados múltiplos cursos semelhantes ao informado.\n\nCursos encontrados:\n\n" + "\n".join(cursos_ambiguos))

            elif (curso == "" and campus != "" and centro == ""):
                params["campus"] = (campus if (campus.isdigit() or campus == "") else extract_most_similar(campus, campi, "campus")[0][0]["codigo"])        
            elif (curso == "" and centro != ""):
                centros_encontrados = await buscar_centros_similares(campus, centro)
                params["codigo_do_setor"] = str(centros_encontrados[0][0]["codigo_do_setor"])
                if len(centros_encontrados) > 1:
                    centros_ambiguos = [
                        f"- {c['descricao']} (Código: {c['codigo_do_setor']}), campus {c.get('campus', c.get('nome_do_campus', ''))}"
                        for c, _ in centros_encontrados
                    ]
                    raise ValueError("Foram encontrados múltiplos centros semelhantes ao informado.\n\nCentros encontrados:\n\n" + "\n".join(centros_ambiguos))

            elif (curso != "" and campus == ""): return [{"error_status": 500, "msg": "Não foi possível obter a informação porque foi informado um curso sem passar qual o seu campus."}]

        estudantes = get_estudantes_gerais_ufcg(params)

        print(len(estudantes))


        if estudantes:
            columns = []#["situacao"]
            if campus != "":
                columns += ["nome_do_campus", "campus"]
            if curso != "":
                columns += ["nome_do_curso", "nome_do_setor", "codigo_do_setor", "turno_do_curso", "codigo_do_curso"]
            if centro != "":
                columns += ["codigo_centro_unidade", "nome_centro_unidade", "codigo_do_setor", "nome_do_setor"]

            with GerenciadorExpert(table_name="Estudante_Info_Gerais", json_data=estudantes, llm=chat_sql) as gerenciador:
                if not query:
                    return gerenciador.execute_sql_estatico("SELECT * FROM Estudante_Info_Gerais;", estudantes)

                observacao = PROMPTS_MOTIVOS_EVASAO
                resultado = gerenciador.invoke_sql(input=query, columns=columns, observacao=observacao)
                
                colunas_comparaveis = ["nacionalidade", "cor", "deficiencias", "forma_de_ingresso", "estado_civil", "turno_do_curso", "local_de_nascimento", "motivo_que_saiu_do_curso"]
                if not _resultado_tem_erro_sql(resultado):
                    informacoes_extras = extrator_informacoes_extras(resultado.get("consulta"), colunas_comparaveis, estudantes)
                    if informacoes_extras:
                        resultado["informacoes_extras"] = informacoes_extras

            for dado in dados: # Inserindo chaves e valores dos parâmetros usados na chamada da ferramenta.
                resultado[dado] = dados[dado]

            resultado["extra"] = params
            print_tool_output(func_name, parametros_str, resultado)
            return resultado
        
        else:
            raise ValueError("Não foram encontrado estudantes para esse nome ou código.")

    except Exception:
        raise


if __name__ == "__main__":
    asyncio.run(
        run_tool(
            "src.tools.estudante.buscar_dados_gerais_de_todos_estudantes.buscar_dados_gerais_de_todos_estudantes",
            config=RunnableConfig,
            query="""quaais são os estado_civil tem na ufcg?""",
            campus="",
            curso="",
            centro=""
        )
    )
