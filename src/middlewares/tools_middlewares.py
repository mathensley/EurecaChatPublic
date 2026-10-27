import logging

from typing import Any, Awaitable, Callable

from langgraph.types import Command
from langchain.agents.middleware import (
    ModelRequest,
    ModelResponse,
    ToolCallRequest,
    wrap_model_call,
    wrap_tool_call,
)
from langchain.messages import ToolMessage
from langchain_core.tools import BaseTool

from src.helpers.chat.tool_permissions_utils import filter_tools_for_context
from src.tools.eureca.eureca_database import descricao_tool_eureca


@wrap_model_call
async def context_based_tools(request: ModelRequest, handler: Callable[[ModelRequest], Awaitable[ModelResponse]]):
    """Filtra as tools do sistema baseado no nível de usuário"""

    tools = filter_tools_for_context(request.tools, getattr(request.runtime, "context", None))
    return await handler(request.override(tools=tools))


@wrap_model_call
async def describe_eureca_database_for_user(request: ModelRequest, handler: Callable[[ModelRequest], Awaitable[ModelResponse]]) -> ModelResponse:
    """Apresenta ao modelo somente as colunas permitidas para o perfil atual."""

    context = getattr(request.runtime, "context", None)
    role = context.normalized_user_role if context is not None and context.is_authenticated else "anon"
    tools = [
        tool.model_copy(update={"description": descricao_tool_eureca(role)})
        if isinstance(tool, BaseTool) and tool.name == "eureca_database"
        else tool
        for tool in request.tools
    ]
    return await handler(request.override(tools=tools))


@wrap_tool_call
async def handle_tool_errors(request: ToolCallRequest, handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]]) -> ToolMessage | Command[Any]:
    """Converte erros de tool em ToolMessage para o agente corrigir a chamada."""

    try:
        return await handler(request)
    except Exception as e:
        tool_name = request.tool_call.get("name")
        tool_args = request.tool_call.get("args")
        logging.exception(
            "Erro na ferramenta `%s` com os argumentos `%s`: %s",
            tool_name,
            tool_args,
            e,
        )
        return ToolMessage(
            content=(
                f"A ferramenta `{tool_name}` não conseguiu concluir a chamada com os argumentos informados.\n\n"
                f"```{e}```\n\n"
                "Use esta mensagem para corrigir os argumentos e chamar a ferramenta novamente quando possível. "
                "Não exponha este erro bruto diretamente ao usuário."
            ),
            name=tool_name,
            tool_call_id=request.tool_call["id"],
            status="error",
        )