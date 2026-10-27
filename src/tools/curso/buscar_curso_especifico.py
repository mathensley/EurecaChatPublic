import logging, asyncio
from ..utils.run_tool import run_tool
from application.config import URL_SIG
from ...helpers.func_utils import get_func_info
from ...helpers.print_tool_call import print_tool_output, print_tool_call

from ...helpers.tool_handlers.tool_requests import buscar_curso_por_nome_ou_codigo
from langchain_core.runnables import RunnableConfig


async def buscar_curso_especifico(config: RunnableConfig, curso: str, campus: str) -> list:
    """
    Use quando precisar de informações de um curso específico (nome, código do curso, grau, turno, período de início, data de criação..., informações básicas sobre um curso especificado).
    
    Args:
        curso (str): O nome do curso por escrito ou o código numérico dele. É necessário fornecer o curso.
        campus (str): O nome do campus ou o código numérico dele, pode ser um desses a seguir: Campina Grande, Cajazeiras, Sousa, Patos, Cuité, Sumé e Pombal. Use a string vazia quando não houver filtro de campus.
    
    Returns:
        Lista com informações relevantes do curso específico, como código do curso, código do inep, código e nome do setor desse curso, período de início, etc.
    """

    func_name, parametros_str = get_func_info()
    
    try:
        callbacks = config["configurable"].get("callbacks_sio")
        for cb in callbacks:
            if hasattr(cb, 'emit'):
                await cb.emit("status", {"resposta": "Buscando por dados do curso"})
            break
    except:
        pass
    
    try:
        print_tool_call(func_name, parametros_str)
        data, _ = await buscar_curso_por_nome_ou_codigo(curso, campus, URL_SIG)
        print_tool_output(func_name, parametros_str, data)
        return data
    
    except Exception:
        raise



if __name__ == "__main__":
    asyncio.run(
        run_tool(
            "src.tools.curso.buscar_curso_especifico.buscar_curso_especifico",
            config=RunnableConfig,
            curso="ciencia da computação",
            campus="campina grande"
        )
    )
