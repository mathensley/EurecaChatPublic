import re
from typing import Any
from .campi_for_tools import campi
from .tool_utils import remover_acentos
from ...helpers.request_utils import make_request
from ...helpers.tool_handlers.tool_utils import get_most_similar_acronym
from ...helpers.tool_handlers.fuzzy_matching import extract_most_similar, format_course_results


async def buscar_curso_por_nome_ou_codigo(curso: Any, campus: Any, url) -> tuple[list[dict], dict]:
    """
    Busca cursos da UFCG por nome ou código, com base no campus especificado.

    - Se o curso for um número, é tratado como código direto.
    - Se for nome, será aplicada correspondência aproximada via `extract_most_similar`.
    - Caso mais de um curso seja semelhante, será retornada uma lista resumida com os candidatos.
    - Caso haja apenas um curso, os dados completos desse curso são retornados.

    Args:
        curso (Any): Nome ou código do curso a ser buscado.
        campus (Any): Código numérico ou nome do campus.
        url (Any): URL da API do Eureca (SCAO ou SIGAA).

    Returns:
        tuple[list[dict], dict]: 
            - Lista de cursos (completa ou resumida).
            - Parâmetros usados na requisição à API.
    """

    curso = str(curso)
    campus = str(campus)
    url = f"{url}/cursos"
    try:
        params = {"status": "ATIVOS", "campus": campus if (campus.isdigit() or campus == "") else extract_most_similar(campus, campi, "campus")[0][0]['codigo']}

        quantidade_digitos = 6 if "das-sig" in url else 8
        tem_digitos_curso = re.search(rf"(?<!\d)\d{{{quantidade_digitos}}}(?!\d)", curso)
        if tem_digitos_curso:
            curso = tem_digitos_curso.group(0)
            params["curso"] = curso
            data = await make_request(url, params)
            if not data: raise ValueError("Nenhum curso encontrado com esse código.")
            return data, params
        
        data = await make_request(url, params)
        if not data: raise ValueError("Nenhum curso encontrado com esse nome.")
        data = [curso for curso in data if remover_acentos(curso["grau_do_curso"]) == "GRADUACAO"]
        curso = get_most_similar_acronym(curso, "curso")
        matches = extract_most_similar(curso, data, "descricao")
        return format_course_results(matches), params
    
    except Exception as e:
        raise e


async def buscar_curriculo_curso(curso: Any, url: Any) -> list[dict]:
    """
    Busca os currículos de um curso.

    Args:
        curso (Any): Código do curso a ser buscado.
        url (Any): URL da API do Eureca (SCAO ou SIGAA).
    
    Returns:
        list[dict]:
            [
                {
                    "codigo_do_curriculo": "2017"
                }
            ]
    """

    curso = str(curso)
    url = f"{url}/curriculos/codigos-curriculo"
    params = {"curso": curso}
    data = await make_request(url, params)
    if not data: raise ValueError("Nenhum currículo encontrado com esse nome.")
    return data