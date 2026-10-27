import re
import logging, asyncio
from collections import defaultdict
from ...helpers.tool_handlers.tool_requests import buscar_curso_por_nome_ou_codigo
from ...helpers.tool_handlers.tool_utils import validar_turma
from ..utils.run_tool import run_tool
from application.config import URL_BASE, URL_SIG
from ...helpers.request_utils import make_request
from .buscar_disciplinas import buscar_disciplinas
from ..curso.buscar_calendarios import buscar_calendarios
from langchain_core.runnables import RunnableConfig


async def buscar_horarios_turmas_vagas_disciplina(
    config: RunnableConfig,
    curso: str,
    disciplina: str,
    campus: str,
    turma: str,
    periodo: str,
) -> list:
    """
    Use quando precisar de informações sobre datas, os **horários**, as **turmas** e **vagas** de uma disciplina.

    Args:
        curso (str): O nome do curso por escrito ou o código numérico dele. É obrigatório fornecer o curso.
        disciplina (str): O nome da disciplina ou o código numérico dela. É obrigatório fornecer a disciplina. Se você tiver o código da disciplina no contexto ou na mensagem do usuário, prefira utilizar o código em vez do nome.
        campus (str): O nome do campus ou o código numérico dele, pode ser um desses a seguir: Campina Grande, Cajazeiras, Sousa, Patos, Cuité, Sumé e Pombal. Use a string vazia quando não houver filtro.
        turma (str): Número da turma. Para obter todas as turmas, use a string vazia "".
        periodo (str): Período do curso. Use a string vazia para o período mais recente.
        
    Returns:
        list: informações relevantes de horários das disciplinas.
    """
    
    curso=str(curso)
    campus=str(campus)
    disciplina=str(disciplina)
    turma=str(turma)
    periodo=str(periodo)
    try:
        callbacks = config["configurable"].get("callbacks_sio")
        for cb in callbacks:
            if hasattr(cb, 'emit'):
                await cb.emit("status", {"resposta": "Buscando horários, turmas e vagas na disciplina"})
            break
    except:
        pass
    
    try:
        url = URL_SIG if periodo == "" or float(periodo) > 2024.2 else URL_BASE
        validou_turma, mensagem = validar_turma(turma_usada=turma)
        if not validou_turma: return mensagem

        params = {"campus": None}
        tem_seis_digitos = re.search(r"(?<!\d)\d{6}(?!\d)", curso)
        if tem_seis_digitos:
            codigo_curso = tem_seis_digitos.group(0)
            params["curso"] = codigo_curso
        else:
            try:
                cursos_encontrados, params = await buscar_curso_por_nome_ou_codigo(curso,campus,url)
            except Exception as e:
                return f"Não foi possível encontrar o curso '{curso}'. Erro: {str(e)}"

            if not cursos_encontrados:
                return f"Nenhum curso encontrado para '{curso}'."

            if len(cursos_encontrados) > 1:
                cursos_ambiguos = [f"- {c['descricao']} (Código: {c['codigo_do_curso']}), {c['nome_do_campus']}" for c in cursos_encontrados]

                return (
                    "Encontrei múltiplos cursos semelhantes. Qual deles você deseja?\n\n"
                    + "\n".join(cursos_ambiguos)
                    + "\n\nVocê pode informar o código ou o nome completo."
                )
            
            params["curso"] = str(cursos_encontrados[0]["codigo_do_curso"])
        
        if periodo == "":
            calendario = await buscar_calendarios(
                config=config,
                periodo="",
                todos_calendarios=False,
                proximo_periodo=False,
            )
            if calendario:
                periodo = calendario[-1].get("periodo") # período mais recente

        todos_dados_disciplina = await buscar_disciplinas(
            config=config,
            curso=params["curso"],
            campus=params.get("campus") or "",
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
        disciplina_escolhida = dados_disciplina[-1]["nome"]
        horarios = await make_request(url=f'{url}/horarios', params=params)
        
        filtros_horarios = []
        turmas_map = {}
        dias = {"2": "Segunda-feira", "3": "Terça-feira", "4": "Quarta-feira", "5": "Quinta-feira", "6": "Sexta-feira", "7": "Sábado"}

        for horario in horarios:
            turma = horario['turma']
            sala = horario['codigo_da_sala']
            dia = str(horario['dia'])
            dia_nome = dias.get(dia, f"Dia {dia}")
            horario_formatado = f"{horario['hora_de_inicio']}h às {horario['hora_de_termino']}h"

            if turma not in turmas_map:
                turmas_map[turma] = { 'turma': turma, 'sala': sala, 'horarios': {} }
                filtros_horarios.append(turmas_map[turma])
            
            turmas_map[turma]['nome_da_disciplina'] = disciplina_escolhida
            turmas_map[turma]['horarios'][dia_nome] = horario_formatado
            turmas_map[turma]['vagas'] = await _buscar_turmas_por_cursos(dados_disciplina[-1]["codigo_da_disciplina"], turma, periodo, url)

        params = {
            "periodo-de": periodo,
            "periodo-ate": periodo,
            "disciplina": dados_disciplina[-1]["codigo_da_disciplina"]
        }
        response = await make_request(f'{url}/turmas', params=params)
        dados_adicionais = {turma["turma"]: turma for turma in response}
        for horario in filtros_horarios:
            if horario["turma"] in dados_adicionais:
                horario.update(dados_adicionais[horario["turma"]])

        return filtros_horarios, todos_dados_disciplina["plano_de_curso"]
    
    except Exception:
        raise


async def _buscar_turmas_por_cursos(codigo_da_disciplina: int, turma: str, periodo: str, url: str) -> dict:
    """Função auxiliar que obtém as vagas reservadas por curso em uma turma específica ou em todas as turmas"""

    params = {
        "disciplina": codigo_da_disciplina,
        "periodo-de": periodo,
        "periodo-ate": periodo
    }

    try:
        turmas = await make_request(url=f"{url}/turmas-por-cursos", params=params)
        if not turmas:
            return ["Não foi possível obter os dados das vagas das turmas desta disciplina nessa turma. Teremos essas informações em breve."]
    except Exception:
        return ["Não foi possível obter os dados das vagas das turmas desta disciplina nessa turma. Teremos essas informações em breve."]
    
    vagas_por_curso = defaultdict(lambda: {
        "vagas_disponiveis": 0,
        "vagas_totais": 0,
        "vagas_preenchidas": 0
    })

    for turma_info in turmas:
        if turma and str(turma_info.get("turma")) != str(turma): continue

        for vaga in turma_info.get("vagas", []):
            cod_curso = vaga["codigo_do_curso"]
            disponiveis = vaga.get("vagas_disponiveis") or 0
            totais = vaga.get("vagas_totais") or 0
            preenchidas = totais - disponiveis
            vagas_por_curso[cod_curso]["vagas_disponiveis"] += disponiveis
            vagas_por_curso[cod_curso]["vagas_totais"] += totais
            vagas_por_curso[cod_curso]["vagas_preenchidas"] += preenchidas

    resultado = []
    for codigo_do_curso, dados in vagas_por_curso.items():
        curso = await make_request(url=f"{url}/cursos", params={"curso": codigo_do_curso})
        descricao = curso[0].get("descricao", "Curso desconhecido") if isinstance(curso, list) and curso else "Curso desconhecido"
        resultado.append({
            "ofertadas_para": descricao,
            "vagas_totais": dados["vagas_totais"],
            "vagas_disponiveis": dados["vagas_disponiveis"],
            "vagas_preenchidas": dados["vagas_preenchidas"],
        })
    
    todas_ofertas = {
        "vagas_totais_geral": 0,
        "vagas_disponiveis_geral": 0,
        "vagas_totais_preenchidas_geral": 0
    }

    for oferta in resultado:
        todas_ofertas["vagas_totais_geral"] += oferta["vagas_totais"]
        todas_ofertas["vagas_disponiveis_geral"] += oferta["vagas_disponiveis"]
        todas_ofertas["vagas_totais_preenchidas_geral"] += oferta["vagas_preenchidas"]
    todas_ofertas["ofertas_para_os_cursos"] = resultado

    return todas_ofertas


if __name__ == "__main__":
    asyncio.run(
        run_tool(
            "src.tools.disciplina.buscar_horarios_turmas_vagas_disciplina.buscar_horarios_turmas_vagas_disciplina",
            config=RunnableConfig,
            campus="CAMPINA GRANDE", 
            curso='computação',
            turma="",
            periodo="2026.1",
            disciplina="programação concorrente",
        )
    )
