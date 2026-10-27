import logging, asyncio
from collections import defaultdict
from ..utils.run_tool import run_tool
from ...helpers.func_utils import get_func_info
from application.config import URL_BASE, URL_SIG
from ...helpers.request_utils import make_request
from .buscar_disciplinas import buscar_disciplinas
from ...helpers.tool_handlers.tool_utils import validar_turma
from ...helpers.tool_handlers.tool_requests import buscar_curso_por_nome_ou_codigo
from langchain_core.runnables import RunnableConfig


async def buscar_plano_de_curso_disciplina(
    config: RunnableConfig,
    curso: str,
    disciplina: str,
    campus: str,
    turma: str,
    periodo: str,
) -> list:
    """
    Use quando precisar de informações sobre os planos de curso de uma disciplina como: ementa, conteúdo, objetivos, metodologia, avaliação ou bibliografia.
    
    Args:
        curso (str): O nome do curso por escrito ou o código numérico dele.
        disciplina (str): Nome ou código da disciplina.
        campus (str): Nome ou código do campus. Use a string vazia quando não houver filtro.
        turma (str): Número da turma. Use a string vazia quando não houver filtro.
        periodo (str): Período do curso. Use a string vazia para o período mais recente.

    Returns:
        list: Informações a respeito de ementa, objetivos, conteúdos, metodologia, avaliação ou bibliografia.
    """

    curso=str(curso)
    campus=str(campus)
    disciplina=str(disciplina)
    turma = str(turma)
    periodo=str(periodo)
    
    try:
        callbacks = config["configurable"].get("callbacks_sio")
        for cb in callbacks:
            if hasattr(cb, 'emit'):
                await cb.emit("status", {"resposta": "Buscando por plano de curso"})
            break
    except:
        pass

    try:
        func_name, parametros_str = get_func_info()
        print(f"🔍 Chamando {func_name}({parametros_str})")

        validou_turma, mensagem = validar_turma(turma_usada=turma)
        if not validou_turma: return mensagem

        url = URL_SIG if periodo == "" or float(periodo) > 2024.2 else URL_BASE
        cursos_encontrados, params = await buscar_curso_por_nome_ou_codigo(curso, campus, url)
        if len(cursos_encontrados) > 1:
            cursos_ambiguos = [f"- {c['descricao']} (Código: {c['codigo_do_curso']}), {c['nome_do_campus']}" for c in cursos_encontrados]
            raise ValueError("Foram encontrados múltiplos cursos semelhantes ao informado.\n\nCursos encontrados:\n\n" + "\n".join(cursos_ambiguos))
        
        params["curso"] = str(cursos_encontrados[0]["codigo_do_curso"])
        todos_dados_disciplina = await buscar_disciplinas(
            config=config,
            curso=params["curso"],
            campus=params["campus"],
            disciplina=disciplina,
            curriculo="",
            periodo=periodo,
            fluxograma=False,
        )
        dados_disciplina = todos_dados_disciplina["data"] if isinstance(todos_dados_disciplina, dict) else todos_dados_disciplina
        if len(dados_disciplina) > 1:
            disciplinas_ambiguas = [f"""- "{d['nome']}" (código: {d['codigo_da_disciplina']}) pertencente a "{d['nome_do_setor']}" do campus de "{d['nome_do_campus']}" """ for d in dados_disciplina]
            raise ValueError(f"Foram encontrados múltiplas disciplinas semelhantes à informada.\n\nDisciplinas encontradas:\n\n" + "\n".join(disciplinas_ambiguas))
        
        params = {
            "disciplina": dados_disciplina[-1]["codigo_da_disciplina"],
            "turma": turma,
            "periodo-de": periodo,
            "periodo-ate": periodo
        }
        
        try:
            return await make_request(url=f'{url}/planos-de-curso', params=params)
        except Exception:
            params["periodo-de"] = "2023.1"
        
        data = await make_request(url=f'{URL_BASE}/planos-de-curso', params=params)
        disciplinas = defaultdict(list)
        
        for item in data:
            disciplinas[item['codigo_da_disciplina']].append(item)
        
        result = []
        for _, itens in disciplinas.items():
            contagem = defaultdict(int)
            for item in itens:
                contagem[item['periodo']] += 1
            periodo_dominante = max(contagem, key=contagem.get)
            filtrados = [item for item in itens if item['periodo'] == periodo_dominante]
            result.extend(filtrados)

        return result
    
    except Exception:
        raise


if __name__ == "__main__":
    asyncio.run(
        run_tool(
            "src.tools.disciplina.buscar_plano_de_curso_disciplina.buscar_plano_de_curso_disciplina",
            config=RunnableConfig,
            disciplina="teoria da computação",
            campus="campina grande",
            curso="108095",
            turma="",
            periodo="2025.1",
        )
    )
