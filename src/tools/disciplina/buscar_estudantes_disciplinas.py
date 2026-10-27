import logging, asyncio
from ..utils.run_tool import run_tool
from ...helpers.func_utils import get_func_info
from application.config import URL_SIG, chat_sql
from .buscar_disciplinas import buscar_disciplinas
from .aux_matriculas_ufcg import get_matriculas_ufcg
from ...sql.gerenciador_expert import GerenciadorExpert
from ..curso.buscar_calendarios import buscar_calendarios
from ...helpers.tool_handlers.campi_for_tools import campi
from ...helpers.tool_handlers.tool_utils import validar_turma
from ..estudante.buscar_centros_similares import buscar_centros_similares
from ...helpers.tool_handlers.fuzzy_matching import extract_most_similar
from ...helpers.tool_handlers.tool_requests import buscar_curso_por_nome_ou_codigo
from ..utils.extrair_colunas_where import extrair_colunas_where
from ..utils.extrator_informacoes_extras import extrator_informacoes_extras
from langchain_core.runnables import RunnableConfig
from .aux_matriculas_ufcg import get_matriculas_ufcg
from .buscar_disciplinas import buscar_disciplinas
from ..curso.buscar_calendarios import buscar_calendarios
from ...helpers.print_tool_call import print_tool_output, print_tool_call
from .prompt_extra_status_matricula import PROMPT_EXTRA_STATUS_ESTUDANTE
from ...prompts.anomaly_agent_prompt import ANOMALY_AGENT_PROMPT


async def buscar_estudantes_disciplinas(
    config: RunnableConfig | None = None,
    query: str = "",
    curso: str = "",
    centro: str = "",
    campus: str = "",
    disciplina: str = "",
    turma: str = "",
    periodo_de: str = "",
    periodo_ate: str = "",
) -> list:
    """
    Use quando precisar de informações que relacionem o desempenho dos estudantes com uma ou mais disciplinas de tal curso. É possível saber de todos os cursos também.
    Exemplo: notas, aprovações, reprovações dos estudantes, dificuldade das disciplinas, informações mais pessoais dos estudantes de tal disciplina como mc, etc.
    Também responde as matrículas que cada estudante fez em cada disciplina, além da quantidade de estudantes que se matricularam em tal disciplina de tal período.
    Além disso, nessa ferramenta encontra-se dados e turmas dos professor de cada disciplina, turma e período.
    Ou seja, essa ferramenta tem informações de estudantes matriculados nas disciplinas, não no(s) curso(s).

    ATENÇÃO:
        Se o usuário não informar a turma, acrescente mais uma informação na query que quer por cada turma.
        Se o usuário informar alguma(s) turmas específica, então você deverá acrescentar essa informação na query e/ou parâmetro de turma.
        Para o periodo_de e periodo_ate seria bom perguntar ao usuário sobre os periodos de limite da busca. Se periodo_de e periodo_ate forem string vazias, então ele usa o periodo mais recente para cada.
        Você pode usar a ferramenta de calendários para saber os períodos.
        Você deve inferir se ele quer ativos ou não, se identificou implicitamente, entõ informe que quer os ativos na query, caso contrário não precisa especificar isso.
        Quando se tratar de turmas do(s) professor(es) essa ferramenta deve ser acionada também.
    
    Args:
        query (str): Pergunta completa do usuário (não repita aqui os filtros dos outros parâmetros, por exemplo, se o usuário mencionar curso, disicplina, turma, etc, não coloque esses filtros aqui, mas sim nos paraêmtros adequados).
        curso (str): O nome do curso por escrito ou o código numérico dele (se souber o código informe-o aqui em vez do nome do curso. Já se quiser todos os estudantes da UFCG (de todos os campi), use a string vazia '' para obter os estudantes de todos os cursos). Se houver mais de um curso em interesse você deve invocar essa ferramenta para cada curso informando a mesma query passando o nome ou código do curso aqui.
        centro (str): Nome ou sigla do centro (e.g. CEEI, CH, etc). Use a string vazia quando não houver filtro.
        campus (str): O nome do campus ou o código numérico dele, pode ser um desses a seguir: Campina Grande, Cajazeiras, Sousa, Patos, Cuité, Sumé e Pombal. Use a string vazia quando não houver filtro de campus.
        disciplina (str): O nome da disciplina ou o código numérico dela. Se você tiver o código da disciplina no contexto, dê preferência para usar o código neste parâmetro em vez do nome. Se precisar de uma ou mais disciplinas, chame essa ferramenta para cada disciplina por vez, uma por uma. Use a string vazia quando não houver filtro.
        turma (str): Número da turma. Use a string vazia quando não houver filtro.
        periodo_de (str): Período de início da busca (ex: '2019.2', '2020.1', '2020.2', etc). Use a string vazia para o período mais recente.
        periodo_ate (str): Período final da busca (ex: '2019.2', '2020.1', '2020.2', etc). Use a string vazia para o período mais recente.

    Returns:
        list: Uma lista com informações relevantes a respeito das matrículas dos estudantes e professor(es) da(s) disciplina(s).
    """
    if not config:
        config: RunnableConfig = {
            "configurable": {
                "thread_id": "teste-usuario-123",
                "callbacks_sio": []
            }
        }

    query=str(query)    
    disciplina=str(disciplina)
    turma = str(turma)
    curso=str(curso)
    campus=str(campus)
    periodo_de=str(periodo_de)
    periodo_ate=str(periodo_ate)
    func_name, parametros_str = get_func_info()
    
    try:
        callbacks = config["configurable"].get("callbacks_sio")
        for cb in callbacks:
            if hasattr(cb, 'emit'):
                await cb.emit("status", {"resposta": "Buscando por matrículas nas disciplinas"})
            break
    except:
        pass

    try:
        print_tool_call(func_name, parametros_str)

        validou_turma, mensagem = validar_turma(turma_usada=turma)
        if not validou_turma: 
            return mensagem     
        calendario = await buscar_calendarios(
            config=config,
            periodo="",
            todos_calendarios=False,
            proximo_periodo=False,
        )
        if calendario:
            periodo_atual = calendario[-1].get("periodo") # período mais recente

            periodo_de = periodo_atual if periodo_de == "" else periodo_de
            periodo_ate = periodo_atual if periodo_ate == "" else periodo_ate

        params = { "periodo-de": periodo_de, "periodo-ate": periodo_ate }
        params["turma"] = turma if turma != "" else turma

        params_gerais = await _buscar_curso_campus_disciplina(config, curso, campus, disciplina, periodo_ate if periodo_ate != "" else periodo_atual)
        params.update(params_gerais)

        # Se der errado tira esse trecho abaixo:
        if (curso == "" and centro != ""):
            centros_encontrados = await buscar_centros_similares(campus, centro)
            params["codigo_do_setor"] = str(centros_encontrados[0][0]["codigo_do_setor"])
            if len(centros_encontrados) > 1:
                centros_ambiguos = [
                    f"- {c['descricao']} (Código: {c['codigo_do_setor']}), campus {c.get('campus', c.get('nome_do_campus', ''))}"
                    for c, _ in centros_encontrados
                ]
                raise ValueError("Foram encontrados múltiplos centros semelhantes ao informado.\n\nCentros encontrados:\n\n" + "\n".join(centros_ambiguos))

        columns = []
        prompt_extra = PROMPT_EXTRA_STATUS_ESTUDANTE
        if curso != "" and disciplina == "":
            columns += ["nome_do_curso", "codigo_do_curso"]

        if curso != "" and disciplina != "":
            prompt_extra = f"Observação: Ignore o nome do curso informado, pois há estudantes de outros cursos nessa disciplina. Ou seja, não use WHERE para filtrar por nome ou código do curso recebido.\n\n" + PROMPT_EXTRA_STATUS_ESTUDANTE
            params["curso"] = ""

        dados_validos = get_matriculas_ufcg(params)
        if not dados_validos: return "Nenhum estudante foi encontrado devido a algum problema na busca dos dados. Talvez não exista alunos deste curso na disciplina nesse período."

        if turma != "": columns.append("turma")
        if campus != "": columns += ["nome_do_campus", "campus"]
        if disciplina != "": columns += ["nome_da_disciplina", "codigo_da_disciplina"]
        if centro != "": columns += ["codigo_centro_unidade", "nome_centro_unidade", "codigo_do_setor", "nome_do_setor"]
        colunas_comparaveis = ["nacionalidade", "cor", "deficiencias", "forma_de_ingresso", "estado_civil", "turno_do_curso", "local_de_nascimento", "nome_do_professor"]

        observacao = prompt_extra
        if disciplina != "":
            gerenciador_geral = GerenciadorExpert(table_name="Estudante_na_Disciplina", json_data=dados_validos, llm=chat_sql)
            gerenciador_geral.prompt = ANOMALY_AGENT_PROMPT
            resultado_geral = gerenciador_geral.invoke_sql(input=query, columns=columns, show=False)
            result = {"pergunta": query, "resultado_geral": resultado_geral, "periodo_usado_de": periodo_de, "periodo_usado_ate": periodo_ate, "observacao": "Verifique se foi utilizado algum 'status' na consulta sql, caso positivo, informe quais foram usados, caso negativo, informe que a consulta foi feita sem usar algum status específico do estudante. Por último, sempre informe o período utilizado na consulta, se tiver sido o período mais recente pode ser que não tenha dados suficientes nesse período."}
            
            informacoes_extras = extrator_informacoes_extras(resultado_geral["consulta"], colunas_comparaveis, dados_validos)
            if informacoes_extras:
                result["informacoes_extras"] = informacoes_extras
            
            print_tool_output(func_name, parametros_str, result)
            return result

        
        with GerenciadorExpert(table_name="Estudante_na_Disciplina", json_data=dados_validos, llm=chat_sql) as gerenciador:
            if not query:
                return gerenciador.execute_sql_estatico("SELECT * FROM Estudante_na_disciplina;", dados_validos)
            
            result = gerenciador.invoke_sql(input=query, columns=columns, observacao=observacao, show=False)
            result = {"pergunta": query, "consulta": result["consulta"], "resultado": result["resultado"], "periodo_usado_de": periodo_de, "periodo_usado_ate": periodo_ate, "observacao": "Verifique se foi utilizado algum 'status' na consulta sql, caso positivo, informe quais foram usados, caso negativo, informe que a consulta foi feita sem usar algum status específico do estudante. Por último, sempre informe o período utilizado na consulta, se tiver sido o período mais recente pode ser que não tenha dados suficientes nesse período."}
            
            informacoes_extras = extrator_informacoes_extras(result["consulta"], colunas_comparaveis, dados_validos)
            if informacoes_extras:
                result["informacoes_extras"] = informacoes_extras
            
            print_tool_output(func_name, parametros_str, result)
            return result
    
    except Exception as e:
        logging.exception(f"Erro interno inesperado na tool {func_name}: {e}")
        raise Exception(e)


async def _buscar_curso_campus_disciplina(config, curso, campus, disciplina, periodo):
    """
    Resolve curso/campus/disciplina em todas as combinações.
    """
    
    params = {}
    if disciplina and not curso: raise ValueError("Para buscar informações de uma disciplina, é necessário informar o curso.")
    if not curso and not campus and not disciplina: return {}
    
    if curso and campus:
        cursos_encontrados, params_campus = await buscar_curso_por_nome_ou_codigo(curso, campus, URL_SIG)
        if len(cursos_encontrados) > 1:
            cursos_ambiguos = [f"- {c['descricao']} (código: {c['codigo_do_curso']}), {c['nome_do_campus']}" for c in cursos_encontrados]
            raise ValueError("Foram encontrados múltiplos cursos semelhantes ao informado.\n\nCursos encontrados:\n\n" + "\n".join(cursos_ambiguos))

        params["curso"] = str(cursos_encontrados[0]["codigo_do_curso"])
        params["campus"] = params_campus.get("campus")

        if disciplina:
            dados_disciplina = await buscar_disciplinas(
                config=config,
                curso=params["curso"],
                campus=params["campus"],
                disciplina=disciplina,
                curriculo="",
                periodo=periodo,
                fluxograma=False,
            )

            dados_disciplina = dados_disciplina["data"] if isinstance(dados_disciplina, dict) else dados_disciplina
            if type(dados_disciplina) == str: raise ValueError(dados_disciplina)

            if len(dados_disciplina) > 1:
                disciplinas_ambiguas = [f"""- "{d['nome']}" (código: {d['codigo_da_disciplina']}) pertencente a "{d['nome_do_setor']}" """ for d in dados_disciplina]
                raise ValueError(f"Foram encontrados múltiplas disciplinas semelhantes à informada.\n\nDisciplinas encontradas:\n\n" + "\n".join(disciplinas_ambiguas))
            
            params["disciplina"] = dados_disciplina[-1]["codigo_da_disciplina"]

        return params
    
    if curso and not campus:
        cursos_encontrados, params_campus = await buscar_curso_por_nome_ou_codigo(curso, "", URL_SIG)

        if len(cursos_encontrados) > 1:
            cursos_ambiguos = [f"- {c['descricao']} (código: {c['codigo_do_curso']}), {c['nome_do_campus']}" for c in cursos_encontrados]
            raise ValueError("Foram encontrados múltiplos cursos semelhantes ao informado.\n\nCursos encontrados:\n\n" + "\n".join(cursos_ambiguos))
        
        params["curso"] = str(cursos_encontrados[0]["codigo_do_curso"])
        if "campus" in params_campus:
            params["campus"] = params_campus["campus"]

        if disciplina:
            todos_dados_disciplina = await buscar_disciplinas(
                config=config,
                curso=params["curso"],
                campus=params.get("campus", ""),
                disciplina=disciplina,
                curriculo="",
                periodo=periodo,
                fluxograma=False,
            )

            dados_disciplina = todos_dados_disciplina["data"] if isinstance(todos_dados_disciplina, dict) else todos_dados_disciplina
            if len(dados_disciplina) > 1:
                disciplinas_ambiguas = [f"""- "{d['nome']}" (código: {d['codigo_da_disciplina']}) pertencente a "{d['nome_do_setor']}" """ for d in dados_disciplina]
                raise ValueError(f"Foram encontrados múltiplas disciplinas semelhantes à informada.\n\nDisciplinas encontradas:\n\n" + "\n".join(disciplinas_ambiguas))
            
            params["disciplina"] = dados_disciplina[-1]["codigo_da_disciplina"]

        return params
    
    if campus and not curso:
        params["campus"] = campus if (campus.isdigit() or campus == "") else extract_most_similar(campus, campi, "campus")[0][0]['codigo']
        return params
    return params


if __name__ == "__main__":
    asyncio.run(
        run_tool(
            "src.tools.disciplina.buscar_estudantes_disciplinas.buscar_estudantes_disciplinas",
            config=RunnableConfig,
            query="",
            periodo_de="",
            periodo_ate="",
            disciplina="",
            curso="",
            centro="",
            campus="",
            turma="",
        )
    )
