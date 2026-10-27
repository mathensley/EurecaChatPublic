import logging, asyncio, re
from ..utils.run_tool import run_tool
from application.config import URL_SIG, URL_BASE
from ...helpers.func_utils import get_func_info
from ...helpers.request_utils import make_request
from ...helpers.print_tool_call import print_tool_output, print_tool_call
from ...helpers.tool_handlers.campi_for_tools import campi
from ...helpers.tool_handlers.fuzzy_matching import extract_most_similar, format_setor_results
from langchain_core.runnables import RunnableConfig
from .buscar_todos_setores import buscar_todos_setores


async def buscar_professores_setor(
    config: RunnableConfig,
    nome_da_unidade_academica: str,
    campus: str,
    periodo: str,
    requer_disciplina_professores: bool,
) -> list:
    """
    Use quando precisar de informações sobre dados dos professores e turmas das disciplinas dos professores.
    
    Args:
        nome_da_unidade_academica: nome da unidade academica, e passe a informação completa como "unidade academica de ...". (Caso queira de toda a UFCG passe o parâmetro com string vazia '').
        campus (str): O nome do campus ou o código numérico dele, pode ser um desses a seguir: Campina Grande, Cajazeiras, Sousa, Patos, Cuité, Sumé e Pombal. Use a string vazia quando não houver filtro de campus.
        periodo: período das disciplinas ministradas pelo professor. Se não for de interesse saber as disciplinas por professor não precisa informar esse parâmetro.
        requer_disciplina_professores (bool, optional): se desejar ver as disciplinas dos professores insira True. Se não quiser, não precisa informar. Defaults to False.

    Returns:
        Lista com as informações relevantes de professores do(s) setor(es) (centro(s)).
    """
    
    nome_da_unidade_academica = str(nome_da_unidade_academica)
    campus = str(campus)
    periodo = str(periodo)
    
    func_name, parametros_str = get_func_info()
    
    try:
        callbacks = config["configurable"].get("callbacks_sio")
        for cb in callbacks:
            if hasattr(cb, 'emit'):
                await cb.emit("status", {"resposta": "Buscando por professores"})
            break
    except:
        pass
    
    if (nome_da_unidade_academica == "") or (nome_da_unidade_academica == "" and campus == ""):
        return """É necessário informar o nome do centro, pois a quantidade de dados retornado é enorme."""
    
    try:
        print_tool_call(func_name, parametros_str)
        params = { "status": "ATIVO" }

        tem_seis_digitos = re.search(r"(?<!\d)\d{6}(?!\d)", nome_da_unidade_academica)
        if tem_seis_digitos:
            params["setor"] = tem_seis_digitos.group(0)
        else:
            codigo_campus = (
                campus if (campus.isdigit() or campus == "")
                else extract_most_similar(campus, campi, "campus")[0][0]["codigo"]
            )

            if nome_da_unidade_academica != "":
                setores_campus = await buscar_todos_setores(
                    config=config,
                    campus=codigo_campus,
                    filtro="UNID",
                    apenas_setor=False,
                )
                setores_campus = [unidade for unidade in setores_campus if "UNID" in unidade["descricao"]]
                matches = extract_most_similar(nome_da_unidade_academica, setores_campus, "descricao")
                print(matches)
                dados_setor = format_setor_results(matches)
                params['setor'] = dados_setor[-1]['codigo_do_setor']
                if len(dados_setor) > 1:
                    setores_ambiguos = [f"- {c['descricao']} (código: {c['codigo_do_setor']}), {c['nome_do_campus']}" for c in dados_setor]
                    raise ValueError("Foram encontrados múltiplas unidades semelhantes ao informado.\n\nUnidades encontradas:\n\n" + "\n".join(setores_ambiguos))

            
        professores = await make_request(url=f"{URL_SIG}/professores", params=params)
        if not professores: raise ValueError("Nenhum professor encontrado para essa unidade.")
        if not requer_disciplina_professores: return professores
        
        professores_dict = {p["matricula_do_docente"]: {**p, "aulas": []} for p in professores}
        prof_keys = professores_dict.keys()
        periodo = "2024.1" if periodo == "" else periodo

        try:
            params={ "setor": params.get("setor", ""), "periodo-de": periodo, "periodo-ate": periodo}
            turmas = await make_request(url=f"{URL_SIG}/turmas", params=params)
        except Exception:
            turmas = []

        if turmas:
            for turma in turmas:
                horarios = await _get_salas_horarios(
                    disciplina=turma["codigo_da_disciplina"],
                    turma=turma["turma"],
                    periodo=periodo
                )
                if horarios:
                    matricula = list(horarios.values())[0].get("matricula_do_docente")
                    if matricula in prof_keys:
                        professores_dict[matricula]["aulas"].append(horarios)
        
        data = list(professores_dict.values())

        print_tool_output(func_name, parametros_str, data)
        return data

    except Exception:
        raise


async def _get_salas_horarios(disciplina, turma, periodo, por_turma: bool = False):
    req = await make_request(
        url=f"{URL_SIG}/classes-por-professor",
        params={
            "disciplina": disciplina,
            "turma": turma,
            "periodo-de": periodo,
            "periodo-ate": periodo,
        }
    )

    salas = {}
    if not req: return salas

    get_dia = {
        1: "Domingo",
        2: "Segunda-feira",
        3: "Terça-feira",
        4: "Quarta-feira",
        5: "Quinta-feira",
        6: "Sexta-feira",
        7: "Sábado"
    }

    for turma_item in req:
        horarios = await make_request(
            url=f"{URL_SIG}/horarios",
            params={
                "disciplina": turma_item["codigo_da_disciplina"],
                "turma": turma_item["turma"],
                "periodo-de": periodo,
                "periodo-ate": periodo
            }
        )

        if not horarios: continue

        for horario in horarios:
            if (horario["codigo_da_disciplina"] == turma_item["codigo_da_disciplina"] and horario["turma"] == turma_item["turma"]):
                codigo_sala = horario["codigo_da_sala"]
                dia_nome = get_dia.get(horario["dia"], "Dia inválido")
                horario_str = f"{dia_nome}: {horario['hora_de_inicio']} às {horario['hora_de_termino']}"

                if codigo_sala not in salas:
                    tipo = horario["turma"] if por_turma else codigo_sala
                    salas[tipo] = {
                        "horarios": [horario_str],
                        "creditos": horario["quantidade_de_creditos"],
                        "carga_horaria": horario["carga_horaria"],
                        "disciplina": horario["nome_da_disciplina"],
                        "codigo_disciplina": horario["codigo_da_disciplina"],
                        "periodo": horario["periodo"],
                        "codigo_da_sala": codigo_sala,
                        "campus": horario["campus"],
                        "turma": horario["turma"],
                        #"matricula_do_docente": turma_item["matricula_do_docente"]
                    }
                else:
                    if horario_str not in salas[codigo_sala]["horarios"]:
                        salas[codigo_sala]["horarios"].append(horario_str)

    return salas



if __name__ == "__main__":
    asyncio.run(
        run_tool(
            "src.tools.curso.buscar_professores_setor.buscar_professores_setor",
            config=RunnableConfig,
            campus="campina grande",
            nome_da_unidade_academica="unidade academica de engenharia eletrica e informática",
            periodo="2025.1",
            requer_disciplina_professores=True
        )
    )
