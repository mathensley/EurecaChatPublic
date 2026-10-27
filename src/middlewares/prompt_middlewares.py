from typing import Any
from datetime import datetime
from collections.abc import Callable

from langchain.agents.middleware import AgentState, Runtime, ModelRequest, ModelResponse, wrap_model_call
from langchain.messages import SystemMessage

from src.prompts.agent_prompt import AGENT_PROMPT_V1

@wrap_model_call
async def add_context(request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]) -> ModelResponse:
    """Middleware to add context information to the system prompt before sending it to the model."""
    
    runtime_context = getattr(request.runtime, "context", None)

    current_date = (getattr(runtime_context, "current_time", None) or datetime.now().strftime("%d/%m/%Y"))
    current_period = getattr(runtime_context, "current_period", None) or "Não informado"
    user_role = getattr(runtime_context, "normalized_user_role", None) or getattr(runtime_context, "user_role", None) or "Não informado"
    user_indentifier = getattr(runtime_context, "user_indentifier", None) or "Não informado"
    user_name = getattr(runtime_context, "user_name", None) or "Não informado"
    user_cpf = getattr(runtime_context, "user_cpf", None) or "Não informado"

    system_prompt = AGENT_PROMPT_V1.format(
        date=current_date,
        periodo=current_period,
        user=(
            f"## USUÁRIO\n"
            f"- Nome: {user_name}\n"
            f"- CPF: {user_cpf}\n"
            f"- Perfil: {user_role}\n"
            f"- Identificador acadêmico: {user_indentifier}"
        )
    )

    new_system_message = SystemMessage(content=system_prompt)
    #print(f"\n\nNew system message in middleware:\n{new_system_message.content}\n\n")
    return await handler(request.override(system_message=new_system_message))

# @after_model
# async def get_context_from_response(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
