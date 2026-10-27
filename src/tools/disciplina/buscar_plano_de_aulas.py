import re
import logging, asyncio
from ..utils.run_tool import run_tool
from ...helpers.func_utils import get_func_info
from application.config import URL_BASE, URL_SIG
from ...helpers.request_utils import make_request
from .buscar_disciplinas import buscar_disciplinas
from ...helpers.tool_handlers.tool_utils import validar_turma
from ...helpers.tool_handlers.tool_requests import buscar_curso_por_nome_ou_codigo

from .buscar_disciplinas import buscar_disciplinas
from ...helpers.print_tool_call import print_tool_output, print_tool_call
from langchain_core.runnables import RunnableConfig


async def buscar_plano_de_aulas(
    config: RunnableConfig,
    curso: str,
    disciplina: str,
    campus: str,
    periodo: str,
    turma: str,
) -> list:
    """
    Use quando precisar de informações sobre o plano de aula de uma disciplina (datas contendo os conteúdos abordados em cada aula e provas).
    
    Args:
        curso (str): O nome do curso por escrito ou o código numérico dele.
        disciplina (str): Nome ou código da disciplina.
        campus (str): Nome ou código do campus. Use a string vazia quando não houver filtro.
        periodo (str): Período no formato 'AAAA.1' ou 'AAAA.2'. Use a string vazia para o período mais recente.
        turma (str): Número da turma. Use a string vazia quando não houver filtro.

    Returns:
        list: Lista dos cronograma de aulas da disciplina.
    """
    
    curso=str(curso)
    campus=str(campus)
    disciplina=str(disciplina)
    turma = str(turma)
    periodo=str(periodo)
    func_name, parametros_str = get_func_info()

    try:
        if float(periodo) >= 2024.2:
            return """
            Não é possivel retornar o plano de aulas para periodos superiores a 2024.2, mas tem para períodos menores que 2024.2.
            Caso ache necessário passar periodo abaixo de 2024.2, pergunte ao usuário se ele quer isso e peça para ele informar o periodo que gostaria.
            Se não for necessário, ignore essa informação (caso a pergunta feita não tenha haver com essa ferramenta de plano de aula).
            """
    except:
        return "O formato do período está errado"
    
    try:
        callbacks = config["configurable"].get("callbacks_sio")
        for cb in callbacks:
            if hasattr(cb, 'emit'):
                await cb.emit("status", {"resposta": "Buscando por plano de aulas"})
            break
    except:
        pass

    try:
        print_tool_call(func_name, parametros_str)

        url = URL_SIG if periodo == "" or float(periodo) > 2024.2 else URL_BASE
        validou_turma, mensagem = validar_turma(turma_usada=turma)
        if not validou_turma: return mensagem

        tem_seis_digitos = re.search(r"(?<!\d)\d{8}(?!\d)", curso)
        if tem_seis_digitos:
            params["curso"] = tem_seis_digitos.group(0)
        else:
            cursos_encontrados, params = await buscar_curso_por_nome_ou_codigo(curso, campus, url)
            if len(cursos_encontrados) > 1:
                raise ValueError(
                    "Foram encontrados múltiplos cursos semelhantes ao informado. "
                    "\nCursos encontrados:\n" +
                    "\n".join([f"- {c['descricao']} (Código: {c['codigo_do_curso']}), {c['nome_do_campus']}" for c in cursos_encontrados])
                )
            curso_escolhido = cursos_encontrados[0]
            codigo_curso = str(curso_escolhido["codigo_do_curso"])
            params["curso"] = codigo_curso
        
        todos_dados_disciplina = await buscar_disciplinas(
            config=config,
            curso=codigo_curso,
            campus=campus,
            disciplina=disciplina,
            curriculo="",
            periodo=periodo,
            fluxograma=False,
        )
        dados_disciplina = todos_dados_disciplina["data"] if isinstance(todos_dados_disciplina, dict) else todos_dados_disciplina
        if len(dados_disciplina) > 1:
            disciplinas_ambiguas = [f"""- "{d['nome']}" (código: {d['codigo_da_disciplina']}) pertencente a "{d['nome_do_setor']}" """ for d in dados_disciplina]
            raise ValueError(f"Foram encontrados múltiplas disciplinas semelhantes à informada.\n\nDisciplinas encontradas:\n\n" + "\n".join(disciplinas_ambiguas))
        
        params = {
            "disciplina": dados_disciplina[-1]["codigo_da_disciplina"],
            "turma": turma,
            "periodo-de": periodo,
            "periodo-ate": periodo
        }

        data = await make_request(url=f'{url}/aulas', params=params)

        print_tool_output(func_name, parametros_str, data)
        return data, todos_dados_disciplina["plano_de_curso"]
    
    except Exception:
        raise


if __name__ == "__main__":
    asyncio.run(
        run_tool(
            "src.tools.disciplina.buscar_plano_de_aulas.buscar_plano_de_aulas",
            config=RunnableConfig,
            disciplina="calculo diferencial e integral 1",
            campus="campina grande",
            curso="ciencia da computacao",
            periodo="2024.1",
            turma="2"
        )
    )
