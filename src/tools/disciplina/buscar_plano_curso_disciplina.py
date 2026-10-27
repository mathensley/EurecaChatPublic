from collections import defaultdict
import logging

import httpx
from application.config import URL_BASE, URL_SIG
from application.http_client import close_client, init_client
from ...helpers.request_utils import make_request
from ...helpers.tool_handlers.tool_requests import buscar_curso_por_nome_ou_codigo
from ...helpers.tool_handlers.tool_utils import validar_turma
from .buscar_disciplinas import buscar_disciplinas
from langchain_core.runnables import RunnableConfig


async def buscar_plano_curso_disciplina(
    config: RunnableConfig,
    curso: str,
    disciplina: str,
    campus: str,
    turma: str,
    curriculo: str,
    periodo: str,
) -> list | dict:
    """
    Use quando precisar de informações sobre planos de curso de uma disciplina:
    ementa, conteúdo, objetivos, metodologia, avaliação ou bibliografia.

    Args:
        curso: Nome ou código do curso.
        disciplina: Nome da disciplina.
        campus: Nome ou código do campus.
        turma: Número da turma.
        curriculo: Ano do currículo.
        periodo: Período letivo (ex.: 2025.1).

    Returns:
        Lista com dados do plano de curso ou mensagem amigável caso não encontre.
    """

    curso = str(curso)
    disciplina = str(disciplina)
    campus = str(campus)
    turma = str(turma)
    curriculo = str(curriculo)
    periodo = str(periodo)
    
    try:
        callbacks = config["configurable"].get("callbacks_sio")
        for cb in callbacks:
            if hasattr(cb, 'emit'):
                await cb.emit("status", {"resposta": "Buscando por plano de curso"})
            break
    except:
        pass

    try:
        url = URL_SIG

        validou_turma, mensagem = validar_turma(turma_usada=turma)
        if not validou_turma:
            return mensagem

        try:
            cursos_encontrados, params = await buscar_curso_por_nome_ou_codigo(
                curso, campus, url
            )
        except Exception:
            url_alternativa = URL_BASE if url == URL_SIG else URL_SIG
            cursos_encontrados, params = await buscar_curso_por_nome_ou_codigo(
                curso, campus, url_alternativa
            )
            url = url_alternativa

        if len(cursos_encontrados) > 1:
            raise ValueError(
                "Foram encontrados múltiplos cursos semelhantes ao informado.\n"
                "Cursos encontrados:\n"
                + "\n".join(
                    [
                        f"- {c['descricao']} "
                        f"(Código: {c['codigo_do_curso']}), "
                        f"{c['nome_do_campus']}"
                        for c in cursos_encontrados
                    ]
                )
            )

        curso_escolhido = cursos_encontrados[0]
        codigo_curso = str(curso_escolhido["codigo_do_curso"])

        todos_dados_disciplina = await buscar_disciplinas(
            config=config,
            curso=codigo_curso,
            campus=params["campus"],
            disciplina=disciplina,
            curriculo=curriculo,
            periodo=periodo,
            fluxograma=False,
        )

        dados_disciplina = todos_dados_disciplina["data"] if isinstance(todos_dados_disciplina, dict) else todos_dados_disciplina
        if len(dados_disciplina) > 1:
            raise ValueError(
                "Foram encontradas múltiplas disciplinas semelhantes à informada.\n"
                "Disciplinas encontradas:\n"
                + "\n".join(
                    [
                        f"- {d['nome']} "
                        f"(Código: {d['codigo_da_disciplina']})"
                        for d in dados_disciplina
                    ]
                )
            )

        params = {
            #"curso": codigo_curso,
            "disciplina": dados_disciplina[-1]["codigo_da_disciplina"],
            "turma": turma,
            "periodo-de": periodo,
            "periodo-ate": periodo
        }

        data = await make_request(
                url=f"{url}/planos-de-curso",
                params=params
            )
        
        if data is None:
            return {
                    "mensagem": (
                        f"Não foram encontradas informações de plano de curso para "
                        f"{disciplina} no curso {curso}, campus {campus}, "
                        f"período {periodo}."
                    )
            }

        disciplinas = defaultdict(list)

        for item in data:
            codigo_disc = item["codigo_da_disciplina"]
            item = {chave: valor for chave, valor in item.items() if valor is not None}
            disciplinas[codigo_disc].append(item)

        result = []
        for _, itens in disciplinas.items():
            contagem = defaultdict(int)

            for item in itens:
                contagem[item["periodo"]] += 1

            periodo_dominante = max(contagem, key=contagem.get)
            filtrados = [
                item for item in itens
                if item["periodo"] == periodo_dominante
            ]
            result.extend(filtrados)

        return result

    except Exception:
        raise


# teste local
import importlib
import asyncio


async def run(tool_path, *args, **kwargs):
    await init_client()
    try:
        module_name, func_name = tool_path.rsplit(".", 1)
        mod = importlib.import_module(module_name)
        func = getattr(mod, func_name)
        result = await func(*args, **kwargs)
        print(result)
    finally:
        await close_client()


if __name__ == "__main__":
    asyncio.run(
        run(
            "src.tools.disciplina.buscar_plano_curso_disciplina.buscar_plano_curso_disciplina",
            config=RunnableConfig,
            disciplina="teoria da computação",
            campus="",
            curso="cc",
            turma="",
            curriculo="",
            periodo="2026.1",
        )
    )
