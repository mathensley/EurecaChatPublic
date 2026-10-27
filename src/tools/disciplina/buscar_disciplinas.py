import logging, httpx, asyncio

from typing import Annotated
from langgraph.types import Command
from langchain.messages import AIMessage, ToolMessage
from langchain_core.tools import InjectedToolCallId

from application.config import URL_BASE, URL_SIG
from ..utils.run_tool import run_tool
from ...helpers.func_utils import get_func_info
from ...helpers.request_utils import make_request
from ...helpers.tool_handlers.tool_utils import merge_lista_disciplinas, formatar_fluxo_disciplinas, get_most_similar_acronym
from ...helpers.tool_handlers.fuzzy_matching import extract_most_similar, format_subject_results
from ...helpers.tool_handlers.tool_requests import buscar_curso_por_nome_ou_codigo, buscar_curriculo_curso

from langchain_core.runnables import RunnableConfig
from ...helpers.print_tool_call import print_tool_output, print_tool_call


async def buscar_disciplinas(
    config: RunnableConfig,
    curso: str,
    campus: str,
    disciplina: str,
    curriculo: str,
    periodo: str,
    fluxograma: bool,
    tool_call_id: Annotated[str | None, InjectedToolCallId] = None,
) -> list | str | Command:
    """
    Informações de todas as disciplinas da grade de um curso, seu fluxograma ou apenas sobre uma disciplina. **Não** possui informação sobre vagas nem horários.
    
    Use esta função quando a pergunta envolver:
    - código, nome, créditos ou carga horária da disciplina;
    - carga teórica/prática semanal ou total;
    - nome do setor responsável e campus;
    - se a disciplina é optativa, obrigatória ou complementar;
    - semestre/período ideal;
    - fluxograma de um curso, ou seja, as disciplinas da grade do curso;
    - pré-requisitos;
    - ementa e informações de como a disciplina é ministrada.
    
    Args:
        curso (str): O nome do curso por escrito ou o código numérico dele. É necessário fornecer o curso.
        campus (str): O nome do campus ou o código numérico dele, pode ser um desses a seguir: Campina Grande, Cajazeiras, Sousa, Patos, Cuité, Sumé e Pombal. Se não souber use vazio "". Defaults to "".
        disciplina (str): Nome ou código numérico da disciplina. Se você tiver o código da disciplina no contexto ou na mensagem do usuário, prefira utilizar o código em vez do nome. Defaults to "".
        curriculo (str): Número do currículo em ano associado à disciplina. Defaults to "".
        periodo (str): Período em que a disciplina foi ofertada sempre no formato 'AAAA.1' ou 'AAAA.2'. Esse campo só é necessário se o usuário fornecer explicitamente um período no formato correto. Defaults to "".
        fluxograma (bool): Variável de controle para decidir se o retorno será um fluxograma organizado ou não. O valor padrão sempre deve ser False, só coloque True se o usuário **explicitar** claramente que quer o fluxograma.

    Returns:
        list | str: Uma lista com informações relevantes para a pergunta a respeito da(s) disciplina(s) ou uma string contendo o fluxograma.
    """

    curso = str(curso)    
    campus = str(campus)
    disciplina = str(disciplina).strip() if disciplina else ""
    curriculo = str(curriculo).strip() if curriculo else ""
    periodo = str(periodo).strip() if periodo else ""
    func_name, parametros_str = get_func_info()

    try:
        callbacks = config["configurable"].get("callbacks_sio")
        for cb in callbacks:
            if hasattr(cb, 'emit'):
                await cb.emit("status", {"resposta": "Buscando por disciplinas"})
            break
    except:
        pass

    try:
        print_tool_call(func_name, parametros_str)

        url = URL_SIG if periodo == "" or float(periodo) >= 2024.2 else URL_BASE

        try:
            cursos_encontrados, params = await buscar_curso_por_nome_ou_codigo(curso, campus, url)
        except Exception as e:
            url_alternativa = URL_BASE if url == URL_SIG else URL_SIG
            cursos_encontrados, params = await buscar_curso_por_nome_ou_codigo(curso, campus, url_alternativa)
            url = url_alternativa
        
        url_disc = f"{url}/disciplinas"
        url_disc_cur = f"{url}/disciplinas-por-curriculo"
        url_disc_pre = f"{url}/pre-requisito-disciplinas"
        url_disc_turma = f"{url}/turmas"
        url_plano_curso = f"{url}/planos-de-curso"

        if len(cursos_encontrados) > 1:
            cursos_ambiguos = [f"- {c['descricao']} (código: {c['codigo_do_curso']}), {c['nome_do_campus']}" for c in cursos_encontrados]
            raise ValueError("Foram encontrados múltiplos cursos semelhantes ao informado.\n\nCursos encontrados:\n\n" + "\n".join(cursos_ambiguos))
        
        params["curso"] = str(cursos_encontrados[0]["codigo_do_curso"])
        curriculos = await buscar_curriculo_curso(params["curso"], url)
        codigos_curriculo = [str(c["codigo_do_curriculo"]) for c in curriculos]

        if curriculo in codigos_curriculo:
            params["curriculo"] = curriculo
        else:
            curriculo_mais_recente = max(codigos_curriculo, key=lambda x: int(x))
            params["curriculo"] = curriculo_mais_recente
        
        disciplinas = await _buscar_disciplinas(params, url_disc, url_disc_cur, url_disc_pre)

        if disciplina != "":
            data =  _buscar_uma_disciplina(disciplina, disciplinas)
            if isinstance(data, dict) and data.get("ambiguo"):
                print_tool_output(func_name, parametros_str, data["mensagem"])
                return data["mensagem"]
            print_tool_output(func_name, parametros_str, data)

            plano_curso_recuperado = None
            params_plano = {"disciplina": data[0]["codigo_da_disciplina"], "periodo": periodo}
            plano_curso = await make_request(url_plano_curso, params_plano)
            if plano_curso:
                maior_periodo = max(item["periodo"] for item in plano_curso)
                plano_curso_recuperado = [
                    {chave: valor for chave, valor in item.items() if valor is not None}
                    for item in plano_curso
                    if item["periodo"] == maior_periodo
                ]
            
            print_tool_output(func_name, parametros_str, {"data": data, "plano_de_curso": plano_curso_recuperado[:3]})

            return {"data": data, "plano_de_curso": plano_curso_recuperado[:3]}

        if periodo != "":
            data = await _disciplinas_ofertadas_periodo(params, periodo, disciplinas, url_disc_turma)
            print_tool_output(func_name, parametros_str, data)
            return data

        data = formatar_fluxo_disciplinas(disciplinas) if fluxograma else disciplinas
        print_tool_output(func_name, parametros_str, data)
        if fluxograma:
            if not tool_call_id:
                return data
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            content="Fluxograma retornado diretamente ao usuário.",
                            tool_call_id=tool_call_id,
                            name=func_name,
                        ),
                        AIMessage(
                            content=data,
                            additional_kwargs={
                                "lc_source": "tool",
                                "direct_response": True,
                                "tool_name": func_name,
                            },
                        ),
                    ]
                },
            )    
        return data

    except Exception:
        raise


async def _buscar_disciplinas(params, url_disc, url_disc_cur, url_disc_pre):
    """
    Busca disciplinas e seus pré-requisitos.
    """

    data = await make_request(url_disc, params)
    if not data: raise ValueError("Nenhuma disciplina encontrada.")
    data_cur = await make_request(url_disc_cur, params)

    if data_cur:
        data = merge_lista_disciplinas(data, data_cur)

    pre_params = {
        'curso': params.get('curso'),
        'curriculo': params.get('curriculo')
    }

    try:
        data_pre_all = await make_request(url_disc_pre, pre_params)
    except httpx.HTTPStatusError as _:
        data_pre_all = []
    data_pre_all = data_pre_all or []

    pre_map = {}
    for item in data_pre_all:
        codigo_disc = item.get('codigo_da_disciplina')
        condicao = item.get('condicao')
        if not codigo_disc or not condicao:
            continue
        pre_map.setdefault(codigo_disc, []).append(condicao)

    # Dicionário auxiliar para mapear código -> nome de disciplina
    codigo_para_nome = {disc['codigo_da_disciplina']: disc['nome'] for disc in data}

    # Atribui os pré-requisitos correspondentes a cada disciplina
    for disciplina in data:
        codigo = disciplina['codigo_da_disciplina']
        codigos_reqs = pre_map.get(codigo, [])

        if codigos_reqs:
            nomes_reqs = [codigo_para_nome.get(c, f"Desconhecida ({c})") for c in codigos_reqs]
            disciplina["pre_requisitos"] = f"Pré-requisitos: [{', '.join(sorted(set(nomes_reqs)))}]"
        else:
            disciplina["pre_requisitos"] = "-"

    return data

async def _disciplinas_ofertadas_periodo(params, periodo, disciplinas, url_disc_turma):
    """
    """

    params_turma = {'curso': params['curso'], 'periodo-de': periodo, 'periodo-ate': periodo}
    turmas = await make_request(url_disc_turma, params_turma)
    
    if not turmas: raise ValueError(f"Nenhuma turma encontrada ofertada no período {periodo}.")

    codigo_disciplinas = list(set(str(turma["codigo_da_disciplina"]) for turma in turmas))
    result = [d for d in disciplinas if str(d["codigo_da_disciplina"]) in codigo_disciplinas]
    return result
    

def _buscar_uma_disciplina(disciplina, disciplinas):
    """
    """

    if disciplina.isdigit():
        data = [d for d in disciplinas if str(d["codigo_da_disciplina"]) == disciplina]
        if not data: raise ValueError("Nenhuma disciplina encontrada com esse código.")
        return data
    
    disciplina = get_most_similar_acronym(disciplina, "disciplina")

    data = extract_most_similar(disciplina, disciplinas, "nome", tie_break_threshold=1.5)
    if len(data) > 1:
        disciplinas_ambiguas = [f"""- "{d[0]['nome']}" (código: {d[0]['codigo_da_disciplina']}) pertencente a "{d[0]['nome_do_setor']}" """ for d in data]
        raise ValueError(f"Foram encontrados múltiplas disciplinas semelhantes à informada.\n\nDisciplinas encontradas:\n\n" + "\n".join(disciplinas_ambiguas) + "\n\nSe encontrar disciplinas muito similares você mesmo deve decidir qual usar, use o código da disciplina correta informada, caso o nome e o código tenha sido fornecido sempre use o código correto. No final, informe qual foi a disciplina e o seu código usado.")
    return format_subject_results(data)


if __name__ == "__main__":
    asyncio.run(
        run_tool(
            "src.tools.disciplina.buscar_disciplinas.buscar_disciplinas",
            config=RunnableConfig,
            campus="campina",
            curso="108095",
            curriculo="",
            periodo="",
            disciplina="1411378",
            fluxograma=False
        )
    )
