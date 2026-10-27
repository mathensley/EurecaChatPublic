import logging, re
import logging, asyncio
from ..utils.run_tool import run_tool
from application.config import URL_BASE
from ...helpers.func_utils import get_func_info
from ...helpers.request_utils import make_request
from langchain_core.runnables import RunnableConfig
from ...helpers.tool_handlers.campi_for_tools import campi
from ...helpers.tool_handlers.fuzzy_matching import extract_most_similar
from ...helpers.tool_handlers.tool_requests import buscar_curso_por_nome_ou_codigo
from ...helpers.print_tool_call import print_tool_output, print_tool_call


async def buscar_ingressantes_sisu(
    config: RunnableConfig,
    curso: str,
    campus: str,
    periodo: str,
) -> list:
    """
    Use apenas quando quiser informações em relação a números de ingressantes
    Contém a quantidade de estudantes que ingressaram para cada e sem cotas. 
 
    Args:
        curso (str): Nome do curso. Use a string vazia quando não houver filtro.
        campus (str): Cidade do campus. Use a string vazia quando não houver filtro.
        periodo (str): Período do campus ou curso. Use a string vazia para o período mais recente.
    
    Returns:
        list: Retorna uma lista contendo a quantidade de ingressantes.
    """
    
    campus=str(campus)
    curso=str(curso)
    periodo=str(periodo)
    func_name, parametros_str = get_func_info()
    
    try:
        callbacks = config["configurable"].get("callbacks_sio")
        for cb in callbacks:
            if hasattr(cb, 'emit'):
                await cb.emit("status", {"resposta": "Buscando por ingressantes do SiSU"})
            break
    except:
        pass
    
    try:
        print_tool_call(func_name, parametros_str)

        if periodo == "":
            periodo = "2024.2"

        params = {"periodo-de": periodo, "periodo-ate": periodo}
        if curso != "": # Se o nome do curso e nome do campus for informado. Traze dados dos ingressantes Sisu do curso naquele campus

            tem_seis_digitos = re.search(r"(?<!\d)\d{8}(?!\d)", curso)
            if tem_seis_digitos:
                params["curso"] = tem_seis_digitos.group(0)
            else:
                cursos_encontrados, params = await buscar_curso_por_nome_ou_codigo(curso, campus, URL_BASE)
                if len(cursos_encontrados) > 1:
                    cursos_ambiguos = [f"""- "{c['descricao']}" (código do curso: {c['codigo_do_curso']}) do campus de "{c['nome_do_campus']}" """ for c in cursos_encontrados]
                    raise ValueError(f"Foram encontrados múltiplos cursos semelhantes ao informado.\n\nCursos encontrados:\n\n" + "\n".join(cursos_ambiguos))
            
                params["curso"] = str(cursos_encontrados[0]["codigo_do_curso"])

        elif curso == "" and campus != "":
            params["campus"] = (campus if (campus.isdigit() or campus == "") else extract_most_similar(campus, campi, "campus")[0][0]["codigo"])

        print(params)
        dados = await make_request(url=f'{URL_BASE}/vagas-no-sisu', params=params)
        """
        Retorna informações númericas a respeito do Sisu para cada curso, como:
        [
        {
        - "periodo": string,
        - "codigo_do_curso": int,
        - a0: int, -- Ampla Concorrência.
        - l1: int, -- Candidatos com Renda Familiar Bruta per capita igual ou inferior a 1,5 Salário Mínimo que tenham cursado integralmente o ensino médio em escolas públicas (Lei. 12.711/2012).
        - l2: int, -- Candidatos autodeclarado pretos, pardos ou indígenas, com Renda Familiar Bruta per capita igual ou inferior a 1,5 Salário Mínimo que tenham cursado integralmente o ensino médio em escolas públicas (Lei. 12.711/2012).
        - l5: int, -- Candidatos que, independentemente da renda (art. 14, II, Portaria Normativa nº 18/2012), tenham cursado integralmente o ensino médio em escolas públicas (Lei. 12.711/2012).
        - l6: int, -- Candidatos autodeclarado pretos, pardos ou indígenas que, independentemente da renda (art. 14, II, Portaria Normativa nº 18/2012), tenham cursado integralmente o ensino médio em escolas públicas (Lei. 12.711/2012).
        - l9: int, -- Candidatos com deficiência com Renda Familiar Bruta per capita igual ou inferior a 1,5 Salário Mínimo e que tenham cursado integralmente o ensino médio em escolas públicas (Lei. 12.711/2012).
        - l10: int, -- Candidatos com deficiência autodeclarado pretos, pardos ou indígenas, com Renda Familiar Bruta per capita igual ou inferior a 1,5 Salário Mínimo que tenham cursado integralmente o ensino médio em escolas públicas (Lei. 12.711/2012).
        - l13: int, -- Candidatos com deficiência que, independentemente da renda (art. 14, II, Portaria Normativa nº 18/2012), tenham cursado integralmente o ensino médio em escolas públicas (Lei. 12.711/2012).
        - l14: int, -- Candidatos com deficiência autodeclarado pretos, pardos ou indígenas que, independentemente da renda (art. 14, II, Portaria Normativa nº 18/2012), tenham cursado integralmente o ensino médio em escolas públicas (Lei. 12.711/2012). 
        - "total": int, -- Total de estidantes ingressantes pelo Sisu.
        - contém outras informações pois, os dados citados anteriormente são antes de 2024.1, a partir de 2024.1 usam outras siglas estabelecidas pelo governo.
        }
        ]
        """
        
        if dados is None or len(dados) == 1: 
            print_tool_output(func_name, parametros_str, dados)
            return dados

        cursos = await make_request(url=f'{URL_BASE}/cursos', params={"status": "ATIVOS", "campus": ""})
        if not cursos: raise ValueError("Não foi possível obter os cursos ou nenhum curso foi encontrado")

        dicionario_cursos = {}
        for dado in dados:
            # Inserindo como chave o código do curso e valor as informações dos ingressantes para cada curso.
            dicionario_cursos[dado["codigo_do_curso"]] = dado
        
        for curso in cursos:
            codigo = curso.get("codigo_do_curso")
            if codigo in dicionario_cursos:
                # Inserindo o nome do curso para cada curso junto as informações de quantidade de ingressantes do Sisu.
                dicionario_cursos[codigo]["campus"] = curso.get("nome_do_campus", "")
                dicionario_cursos[codigo]["nome_do_curso"] = curso.get("descricao", "")


        # Adicionando uma descrição sobre o significado de cada tipo de entrada pelo Sisu aos dados.
        data = str(list(dicionario_cursos.values())) + """
            Significado dos dados retornados são:
                - A0: Ampla Concorrência.
                - L1: Candidatos com Renda Familiar Bruta per capita igual ou inferior a 1,5 Salário Mínimo que tenham cursado integralmente o ensino médio em escolas públicas (Lei. 12.711/2012).
                - L2: Candidatos autodeclarado pretos, pardos ou indígenas, com Renda Familiar Bruta per capita igual ou inferior a 1,5 Salário Mínimo que tenham cursado integralmente o ensino médio em escolas públicas (Lei. 12.711/2012).
                - L5: Candidatos que, independentemente da renda (art. 14, II, Portaria Normativa nº 18/2012), tenham cursado integralmente o ensino médio em escolas públicas (Lei. 12.711/2012).
                - L6: Candidatos autodeclarado pretos, pardos ou indígenas que, independentemente da renda (art. 14, II, Portaria Normativa nº 18/2012), tenham cursado integralmente o ensino médio em escolas públicas (Lei. 12.711/2012).
                - L9: Candidatos com deficiência com Renda Familiar Bruta per capita igual ou inferior a 1,5 Salário Mínimo e que tenham cursado integralmente o ensino médio em escolas públicas (Lei. 12.711/2012).
                - L10: Candidatos com deficiência autodeclarado pretos, pardos ou indígenas, com Renda Familiar Bruta per capita igual ou inferior a 1,5 Salário Mínimo que tenham cursado integralmente o ensino médio em escolas públicas (Lei. 12.711/2012).
                - L13: Candidatos com deficiência que, independentemente da renda (art. 14, II, Portaria Normativa nº 18/2012), tenham cursado integralmente o ensino médio em escolas públicas (Lei. 12.711/2012).
                - L14: Candidatos com deficiência autodeclarado pretos, pardos ou indígenas que, independentemente da renda (art. 14, II, Portaria Normativa nº 18/2012), tenham cursado integralmente o ensino médio em escolas públicas (Lei. 12.711/2012). 
            """
        
        print_tool_output(func_name, parametros_str, data)
        return data
    
    
    except Exception:
        raise


if __name__ == "__main__":
    asyncio.run(
        run_tool(
            "src.tools.estudante.buscar_ingressantes_sisu.buscar_ingressantes_sisu",
            config=RunnableConfig,
            periodo="2023.1", # Só funciona de 2023.2 para trás, pois usa o SCAO 
            curso="ssss14102100",
            campus="campina"
        )
    )
