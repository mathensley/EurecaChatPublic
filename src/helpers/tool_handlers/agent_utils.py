from typing import Any
from ...helpers.tool_handlers.campi_for_tools import campi

def format_student_info(estudante):
    dados_estudante = {
        "nome": estudante.get("nome"),
        "matricula": estudante.get("matricula_do_estudante"),
        "curso": estudante.get("nome_do_curso"),
        "campus": estudante.get("nome_do_campus"),
        "curriculo": estudante.get("codigo_do_curriculo"),
        "periodo_ingresso": estudante.get("periodo_de_ingresso"),
        "periodos_completados": estudante.get("periodos_completados"),
        "mc": estudante.get("mc", 0)
    }
    # Formatar informações
    user_info = f"""
    **## Informações do estudante que você está conversando atualmente:**
    - Nome: {dados_estudante['nome']}
    - Matrícula: {dados_estudante['matricula']}
    - Curso: {dados_estudante['curso']}
    - Campus: {dados_estudante['campus']}
    - Currículo: {dados_estudante['curriculo']}
    - Período de Ingresso: {dados_estudante['periodo_ingresso']}
    - Períodos Completados: {dados_estudante['periodos_completados']}
    - Média de Conclusão (MC): {dados_estudante['mc']}
    """
    
    return user_info

def format_professor_info(professor):
    dados_professor = professor.get("dados_professor", {})
    disciplinas_atuais = professor.get("disciplinas_atuais", [])

    disciplinas = []
    disciplinas_vistas = set()
    for disciplina in disciplinas_atuais:
        codigo = disciplina.get("codigo_da_disciplina")
        nome = disciplina.get("nome_da_disciplina")
        chave = (codigo, nome)

        if chave in disciplinas_vistas:
            continue

        disciplinas_vistas.add(chave)
        disciplinas.append(f"- {nome} ({codigo})")

    disciplinas_formatadas = "\n".join(disciplinas) if disciplinas else "- Nenhuma disciplina atual encontrada"

    user_info = f"""
    **## Informações do professor que você está conversando atualmente:**
    - Nome: {dados_professor.get("nome")}
    - Matrícula do docente: {dados_professor.get("matricula_do_docente")}
    - SIAPE: {dados_professor.get("siape")}
    - Email: {dados_professor.get("email")}

    **Disciplinas lecionando atualmente:**
{disciplinas_formatadas}
    """

    return user_info

def _periodo_key(turma: dict[str, Any]) -> tuple[int, ...]:
    periodo = str(turma.get("periodo", "0"))
    try:
        return tuple(int(parte) for parte in periodo.split("."))
    except ValueError:
        return (0,)


def _formatar_turma(turma: dict[str, Any]) -> dict[str, Any]:
    turma_formatada = turma.copy()
    docentes = turma_formatada.get("docentes", [])

    if len(docentes) <= 1:
        turma_formatada.pop("docentes", None)

    return turma_formatada


def get_nome_campus(codigo_campus: Any) -> str | None:
    codigo = str(codigo_campus)
    campus = next((item["campus"] for item in campi if item["codigo"] == codigo), None)
    return campus
