import asyncio
import uuid
from pathlib import Path

from langchain_core.runnables import RunnableConfig

from application.config import URL_SIG
from src.helpers.tool_handlers.tool_requests import (
    buscar_curriculo_curso,
    buscar_curso_por_nome_ou_codigo,
)
from src.helpers.tool_handlers.tool_utils import formatar_fluxo_disciplinas
from src.tools.utils.run_tool import run_tool
from src.tools.eureca.eureca_bash.workdir import _extrai_exports_dir, criar_url_download

from .buscar_disciplinas import _buscar_disciplinas, _buscar_uma_disciplina
from .fluxograma_pdf import gerar_pdf_fluxograma


def _normalizar_semestre(semestre: int | None) -> int | None:
    if semestre is None or semestre == "":
        return None

    try:
        semestre_normalizado = int(semestre)
    except (TypeError, ValueError) as exc:
        raise ValueError("O semestre deve ser um número inteiro maior ou igual a 1.") from exc

    if semestre_normalizado < 1 or str(semestre_normalizado) != str(semestre).strip():
        raise ValueError("O semestre deve ser um número inteiro maior ou igual a 1.")

    return semestre_normalizado


def _filtrar_por_semestre(disciplinas: list[dict], semestre: int) -> list[dict]:
    disciplinas_do_semestre = [
        disciplina
        for disciplina in disciplinas
        if str(disciplina.get("semestre_ideal", "")).strip() == str(semestre)
    ]
    if disciplinas_do_semestre:
        return disciplinas_do_semestre

    semestres_disponiveis = sorted(
        {
            int(valor)
            for disciplina in disciplinas
            if str(disciplina.get("semestre_ideal", "")).strip().isdigit()
            and (valor := str(disciplina["semestre_ideal"]).strip()) != "0"
        }
    )
    disponiveis = ", ".join(map(str, semestres_disponiveis)) or "nenhum"
    raise ValueError(f"Nenhuma disciplina encontrada para o {semestre}º semestre. Semestres disponíveis: {disponiveis}.")


async def buscar_fluxograma(
    config: RunnableConfig,
    curso: str,
    campus: str,
    disciplina: str,
    curriculo: str,
    semestre: int | None = None,
) -> dict | list[dict] | str:
    """Busca o fluxograma de um curso ou suas disciplinas por nome ou semestre.

    Use esta função para obter todas as disciplinas do fluxograma de um curso,
    as disciplinas recomendadas para um semestre ideal ou uma disciplina específica
    pertencente ao curso. Não possui informações sobre oferta, horários, turmas ou vagas.

    Args:
        curso: Nome ou código numérico do curso. É obrigatório, inclusive ao pesquisar uma disciplina específica.
        campus: Nome ou código do campus. Use ``""`` quando não houver filtro.
        disciplina: Nome ou código da disciplina. Use ``""`` para retornar o fluxograma completo ou filtrar somente pelo semestre.
        curriculo: Código do currículo. Use ``""`` para selecionar o currículo mais recente do curso.
        semestre: Semestre ideal da grade, como um inteiro de 1 a N. Quando informado, retorna uma lista de disciplinas em vez do fluxograma textual completo.

    Returns:
        No fluxograma completo, um dicionário contendo todo o texto formatado e o PDF para download. Quando houver filtros, uma lista com a disciplina ou as disciplinas correspondentes.
    """

    curso = str(curso).strip() if curso is not None else ""
    campus = str(campus).strip() if campus is not None else ""
    disciplina = str(disciplina).strip() if disciplina else ""
    curriculo = str(curriculo).strip() if curriculo else ""
    semestre_normalizado = _normalizar_semestre(semestre)

    if not curso:
        raise ValueError("É necessário informar o curso para buscar o fluxograma.")

    try:
        callbacks = config["configurable"].get("callbacks_sio")
        for callback in callbacks:
            if hasattr(callback, "emit"):
                await callback.emit("status", {"resposta": "Buscando pelo fluxograma"})
            break
    except Exception:
        pass

    url = URL_SIG
    cursos_encontrados, params = await buscar_curso_por_nome_ou_codigo(curso, campus, url)

    if len(cursos_encontrados) > 1:
        cursos_ambiguos = [f"- {item['descricao']} (código: {item['codigo_do_curso']}), " f"{item['nome_do_campus']}" for item in cursos_encontrados]
        raise ValueError("Foram encontrados múltiplos cursos semelhantes ao informado.\n\nCursos encontrados:\n\n" + "\n".join(cursos_ambiguos))

    params["curso"] = str(cursos_encontrados[0]["codigo_do_curso"])
    curriculos = await buscar_curriculo_curso(params["curso"], url)
    codigos_curriculo = [str(item["codigo_do_curriculo"]) for item in curriculos]
    params["curriculo"] = (curriculo if curriculo in codigos_curriculo else max(codigos_curriculo, key=int))

    disciplinas = await _buscar_disciplinas(
        params,
        f"{url}/disciplinas",
        f"{url}/disciplinas-por-curriculo",
        f"{url}/pre-requisito-disciplinas",
    )

    if disciplina:
        resultado = _buscar_uma_disciplina(disciplina, disciplinas)
        if semestre_normalizado is not None:
            resultado = _filtrar_por_semestre(resultado, semestre_normalizado)
    elif semestre_normalizado is not None:
        resultado = _filtrar_por_semestre(disciplinas, semestre_normalizado)
    else:
        fluxograma = formatar_fluxo_disciplinas(disciplinas)
        exports_dir = Path(await _extrai_exports_dir(config))
        nome_arquivo = f"fluxograma_{uuid.uuid4().hex}.pdf"
        caminho_pdf = exports_dir / nome_arquivo
        curso_encontrado = cursos_encontrados[0]

        await asyncio.to_thread(
            gerar_pdf_fluxograma,
            disciplinas,
            caminho_pdf,
            curso=str(curso_encontrado.get("descricao") or curso),
            campus=str(curso_encontrado.get("nome_do_campus") or campus or "-"),
            curriculo=params["curriculo"],
        )

        url_download = criar_url_download(exports_dir.parent, nome_arquivo)
        resultado = {
            "fluxograma": fluxograma,
            "arquivo_pdf": {
                "tipo": "arquivo",
                "nome_arquivo": nome_arquivo,
                "url_download": url_download,
                "total_disciplinas": len(disciplinas),
                "observacao": (
                    "O fluxograma completo também está disponível em PDF: "
                    f"[{nome_arquivo}]({url_download})."
                ),
            },
        }

    return resultado


if __name__ == "__main__":
    asyncio.run(
        run_tool(
            "src.tools.disciplina.buscar_fluxograma.buscar_fluxograma",
            config=RunnableConfig,
            curso="108095",
            campus="campina",
            disciplina="",
            curriculo="",
            semestre=None,
        )
    )
