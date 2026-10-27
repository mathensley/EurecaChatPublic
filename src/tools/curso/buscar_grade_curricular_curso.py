import logging, asyncio
from ..utils.run_tool import run_tool
from application.config import URL_SIG
from ...helpers.request_utils import make_request
from ...helpers.tool_handlers.tool_requests import buscar_curso_por_nome_ou_codigo
from langchain_core.runnables import RunnableConfig


async def buscar_grade_curricular_curso(
    config: RunnableConfig,
    curso: str,
    campus: str,
    todos_curriculos: bool,
) -> list:
    """
    Use quando precisar de informações sobre a grade curricular (código, regime, duração, carga horária, número de créditos, número de atividades, número de disciplinas).
    
    Args:

        curso (str): O nome do curso por escrito ou o código numérico dele. É necessário fornecer o curso.
        campus (str): O nome do campus ou o código numérico dele, pode ser um desses a seguir: Campina Grande, Cajazeiras, Sousa, Patos, Cuité, Sumé e Pombal. Use a string vazia quando não houver filtro de campus.
        todos_curriculos (bool): Se True, retorna todos os currículos do curso. Se False, retorna apenas o currículo mais recente. Defaults to False.

    Returns:
        Lista com informações relevantes dos currículos do curso específico.
    """
    
    curso=str(curso)
    campus=str(campus)

    try:
        callbacks = config["configurable"].get("callbacks_sio")
        for cb in callbacks:
            if hasattr(cb, 'emit'):
                await cb.emit("status", {"resposta": "Buscando por dados da grade curricular"})
            break
    except:
        pass
    
    try:
        cursos_encontrados, params = await buscar_curso_por_nome_ou_codigo(curso, campus, URL_SIG)
        
        if len(cursos_encontrados) > 1:
            cursos_ambiguos = [f"- {c['descricao']} (Código: {c['codigo_do_curso']}), {c['nome_do_campus']}" for c in cursos_encontrados]
            raise ValueError("Foram encontrados múltiplos cursos semelhantes ao informado.\n\nCursos encontrados:\n\n" + "\n".join(cursos_ambiguos))
        
        params["curso"] = str(cursos_encontrados[0]["codigo_do_curso"])
        curriculos = await make_request(url=f'{URL_SIG}/curriculos', params=params)

        if not curriculos:
            raise ValueError("Nenhum currículo encontrado.")
        
        data = curriculos if todos_curriculos else [curriculos[-1]]
        return data
    
    except Exception:
        raise


if __name__ == "__main__":
    asyncio.run(
        run_tool(
            "src.tools.curso.buscar_grade_curricular_curso.buscar_grade_curricular_curso",
            config=RunnableConfig,
            curso="10895",
            campus="",
            todos_curriculos=False
        )
    )
