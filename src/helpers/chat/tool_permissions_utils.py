from collections.abc import Sequence

from langchain_core.tools import BaseTool

from src.helpers.context import Context


STUDENT_ONLY_TOOL_NAMES = {"estudante_info", "historico_estudante"}
PROFESSOR_ONLY_TOOL_NAMES = {"professor_info"}


def filter_tools_for_context(tools: Sequence[BaseTool], context: Context | None) -> list[BaseTool]:
    """Aplica em qualquer fluxo a mesma política de tools por tipo de usuário."""

    user_role = (
        context.normalized_user_role
        if context is not None and context.is_authenticated
        else "anon"
    )

    if user_role == "Aluno":
        blocked_names = PROFESSOR_ONLY_TOOL_NAMES
    elif user_role == "Professor":
        blocked_names = STUDENT_ONLY_TOOL_NAMES
    else:
        blocked_names = STUDENT_ONLY_TOOL_NAMES | PROFESSOR_ONLY_TOOL_NAMES

    return [tool for tool in tools if tool.name not in blocked_names]
