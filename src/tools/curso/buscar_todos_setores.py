import logging, asyncio
from ..utils.run_tool import run_tool
from application.config import URL_SIG
from ...helpers.func_utils import get_func_info
from ...helpers.request_utils import make_request
from ...helpers.tool_handlers.campi_for_tools import campi
from ...helpers.tool_handlers.tool_utils import remover_acentos
from ...helpers.tool_handlers.fuzzy_matching import extract_most_similar
from ...helpers.print_tool_call import print_tool_output, print_tool_call
from langchain_core.runnables import RunnableConfig


async def buscar_todos_setores(
    config: RunnableConfig,
    campus: str,
    filtro: str,
    apenas_setor: bool,
) -> list:
    """
    Use quando precisar de informações sobre os setores e seus cursos por setor.
    
    Args:
        campus (str): O nome do campus ou o código numérico dele, pode ser um desses a seguir: Campina Grande, Cajazeiras, Sousa, Patos, Cuité, Sumé e Pombal. Use a string vazia quando não houver filtro de campus.
        filtro (str): passe 'UNID' no parametro do filtro se perguntou pelas unidades ou passe 'CENTRO' se perguntou pelos centros. (se não foi informado, ou se perguntar pelo setor, então use a string vazia '').
        apenas_setor (bool): Use True para buscar apenas pelos setores, use False para buscar pelos setores e seus cursos. Defaults to `False`.

    Returns:
        Lista com informações relevantes do setor (centro) específico. Podendo haver informações dos cursos relacionados a cada setor, caso o parâmetro apenas_centro seja False.
    """
        
    campus = str(campus)
    filtro = (filtro or "").lower()
    if filtro not in ["centro", "unid", ""]:
        return "Use o parâMetro 'UNID' no filtro para buscar unidades ou passe 'CENTRO' para os centros. (se não foi informado, ou se perguntar pelo setor, então use a string vazia '')."
    func_name, parametros_str = get_func_info()

    try:
        callbacks = config["configurable"].get("callbacks_sio")
        for cb in callbacks:
            if hasattr(cb, 'emit'):
                await cb.emit("status", {"resposta": "Buscando por setores"})
            break
    except:
        pass
    

    try:
        print_tool_call(func_name, parametros_str)

        codigo_campus = (
            campus if (campus.isdigit() or campus == "")
            else extract_most_similar(campus, campi, "campus")[0][0]["codigo"]
        )

        params = {}
        if codigo_campus != "":
            params["campus"] = codigo_campus
        
        setores = await make_request(url=f"{URL_SIG}/setores", params={"campus": codigo_campus if codigo_campus != "" else ""})
        if not setores: raise ValueError("Não foi possível obter os setores da UFCG.")
        
        setores_filtrados = [setor for setor in setores if filtro in setor["descricao"].lower() and setor["tipo_setor"] in ("1", "4") and setor["codigo_do_setor"] != 112129]
        if apenas_setor: return setores_filtrados
        cursos = await make_request(url=f"{URL_SIG}/cursos", params={"status": "ATIVOS", "campus": codigo_campus })
        if not cursos: raise ValueError("Não foi possível obter a lista de cursos da UFCG.")
        
        cursos_filtrados = []
        for curso in cursos:
            grau_curso = remover_acentos(curso["grau_do_curso"])
            if grau_curso == "GRADUACAO":
                curso["grau_do_curso"] = grau_curso
                curso = { "codigo_do_curso": curso["codigo_do_curso"], "descricao": curso["descricao"] }
                cursos_filtrados.append(curso)

        data = setores_filtrados + cursos_filtrados

        print_tool_output(func_name, parametros_str, data)
        return data

    except Exception:
        raise


# Essa função geralmente é usada como função auxiliar de outra ferramentas para evitar o reprocessamento de dados que já obtemos
async def buscar_todos_setores_por_codigo_do_campus(codigo_do_campus: str = "", filtro: str = "") -> list:
    """
    Busca as informações dos setores (centros) do campus da UFCG a partir do código do campus.
    
    Args:
        codigo_do_campus: código do campus. (se não foi informado ou se quiser saber sobre todos os centros, então passe a string vazia '').
        filtro: passe 'UNID' parametro do filtro se perguntou pelas unidades ou passe 'CENTRO' se perguntou pelos centros. (se não foi informado, ou se perguntar pelo setor, então use a string vazia '').
    
    Returns:
        Lista com informações relevantes do setor (centro) específico.
    """
        
    codigo = str(codigo_do_campus)
    filtro = (filtro or "").lower()

    try:
        func_name, parametros_str = get_func_info()
        print(f"🔍 Chamando {func_name}({parametros_str})")

        setores = await make_request(url=f"{URL_SIG}/setores", params={"campus": codigo if codigo != "" else ""})
        if not setores: raise ValueError("Não foi possível obter os setores da UFCG.")

        if filtro != "":
            setores = [setor for setor in setores if filtro in setor["descricao"].lower()]
        
        return setores

    except Exception as e:
        logging.exception(f"Erro interno inesperado na tool {func_name}: {e}")
        error = f"""Ocorreu um erro ao chamar a função "{func_name}" com os parâmetros {parametros_str}: {str(e)}"""
        return error


if __name__ == "__main__":
    asyncio.run(
        run_tool(
            "src.tools.curso.buscar_todos_setores.buscar_todos_setores",
            config=RunnableConfig,
            campus="",
            filtro="centro",
            apenas_setor=False
        )
    )
