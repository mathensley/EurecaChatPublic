from dataclasses import dataclass
from collections.abc import Iterable, Sequence
from typing import Annotated, Any, Literal, Union, cast

from langchain.agents.middleware import ModelRequest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_core.tools import BaseTool
from pydantic import Field, TypeAdapter
from typing_extensions import TypedDict

from src.helpers.chat.chat_msgs_utils import (
    extract_text_content,
    get_messages_before_index,
    is_summary_message,
    strip_guardrail_messages,
    strip_transport_markers,
)
from src.prompts.tool_selector_tools_prompt import TOOL_SELECTOR_DESCRIPTIONS


ToolSelectorStrategy = Literal["LLM", "SIMILARITY", "TOOL_CALL"]
ToolSelectorLLMMode = Literal["SCHEMA", "PROMPT"]

VALID_TOOL_SELECTOR_STRATEGIES = {"LLM", "SIMILARITY", "TOOL_CALL"}
VALID_TOOL_SELECTOR_LLM_MODES = {"SCHEMA", "PROMPT"}
DEFAULT_SELECTOR_MAX_MESSAGE_CHARS = 4_000


@dataclass
class SelectionRequest:
    """Representa uma solicitação de seleção de tools/modelos/mensagens formatadas corretamente para o modelo seletor."""

    available_tools: list[BaseTool]
    model: BaseChatModel
    model_messages: list[BaseMessage]


def require_base_tools(tools: Sequence[BaseTool | dict[str, Any]]) -> list[BaseTool]:
    base_tools: list[BaseTool] = []
    for tool in tools:
        if not isinstance(tool, BaseTool):
            raise TypeError(
                "ToolSelectorMiddleware aceita apenas instâncias de BaseTool"
            )
        base_tools.append(tool)
    return base_tools


def partition_always_include_tools(tools: Sequence[BaseTool], always_include: set[str]) -> tuple[list[BaseTool], list[BaseTool]]:
    selectable_tools = [tool for tool in tools if tool.name not in always_include]
    always_tools = [tool for tool in tools if tool.name in always_include]
    return selectable_tools, always_tools


def merge_tool_groups(*groups: Iterable[BaseTool]) -> list[BaseTool]:
    merged: list[BaseTool] = []
    seen_names: set[str] = set()
    for group in groups:
        for tool in group:
            if tool.name in seen_names:
                continue
            seen_names.add(tool.name)
            merged.append(tool)
    return merged


def is_new_user_turn(messages: Sequence[BaseMessage]) -> bool:
    """Indica se a chamada atual é a primeira após uma nova mensagem do usuário."""
    conversation = strip_guardrail_messages(list(messages))
    return bool(conversation) and isinstance(conversation[-1], HumanMessage) and not (is_summary_message(conversation[-1]))


def normalize_selector_strategy(strategy: str) -> ToolSelectorStrategy:
    normalized_strategy = strategy.strip().upper().replace("-", "_")
    if normalized_strategy not in VALID_TOOL_SELECTOR_STRATEGIES:
        raise ValueError(
            f"Estratégia desconhecida: {strategy}. "
            f"Use uma destas opções: {sorted(VALID_TOOL_SELECTOR_STRATEGIES)}"
        )
    return cast(ToolSelectorStrategy, normalized_strategy)


def normalize_selector_llm_mode(llm_mode: str) -> ToolSelectorLLMMode:
    normalized_mode = llm_mode.strip().upper()
    if normalized_mode not in VALID_TOOL_SELECTOR_LLM_MODES:
        raise ValueError(
            f"Modo de seleção LLM desconhecido: {llm_mode}. "
            f"Use uma destas opções: {sorted(VALID_TOOL_SELECTOR_LLM_MODES)}"
        )
    return cast(ToolSelectorLLMMode, normalized_mode)


def prepare_selection_request(
    request: ModelRequest,
    *,
    model: BaseChatModel | None,
    tool_selector_prompt: str,
    tool_catalog_prompt: str | None,
    max_tools: int | None,
    max_message_chars: int,
) -> SelectionRequest | None:
    if not request.tools:
        return None

    available_tools = require_base_tools(request.tools)

    messages = strip_guardrail_messages(request.messages)
    latest_user_index = _get_latest_user_message_index(messages)
    if latest_user_index is None:
        raise AssertionError(
            "Nenhuma mensagem de usuário foi encontrada para selecionar tools"
        )

    system_message = tool_selector_prompt
    if tool_catalog_prompt is not None:
        system_message += "\n\n" + build_tool_catalog_prompt(
            available_tools, tool_catalog_prompt
        )
    if max_tools is not None:
        system_message += (
            f"\n\nSelecione no máximo {max_tools} ferramentas e coloque as mais "
            "relevantes primeiro."
        )

    return SelectionRequest(
        available_tools=available_tools,
        model=model or request.model,
        model_messages=[
            SystemMessage(content=system_message),
            HumanMessage(
                content=_format_conversation(
                    messages,
                    latest_user_index,
                    max_message_chars,
                )
            ),
        ],
    )


def create_tool_selection_response(tools: list[BaseTool]) -> TypeAdapter[Any]:
    """Cria o schema estruturado com os nomes e descrições das tools."""
    if not tools:
        raise AssertionError("É necessário fornecer ao menos uma tool")

    literals = [
        Annotated[Literal[tool.name], Field(description=tool.description)]
        for tool in tools
    ]
    selected_tool_type = Union[tuple(literals)]  # type: ignore[valid-type]  # noqa: UP007

    class ToolSelectionResponse(TypedDict):
        tools: Annotated[
            list[selected_tool_type],  # type: ignore[valid-type]
            Field(
                description=(
                    "Nomes das ferramentas necessárias para a intenção atual, "
                    "em ordem de relevância."
                )
            ),
        ]

    return TypeAdapter(ToolSelectionResponse)


def create_prompt_tool_selection_response() -> TypeAdapter[Any]:
    """Cria um schema genérico; os nomes válidos ficam no prompt complementar."""

    class ToolSelectionResponse(TypedDict):
        tools: Annotated[
            list[str],
            Field(
                description=(
                    "Nomes exatos das ferramentas selecionadas a partir do catálogo "
                    "fornecido na mensagem de sistema, em ordem de relevância."
                )
            ),
        ]

    return TypeAdapter(ToolSelectionResponse)


def build_tool_catalog_prompt(
    available_tools: list[BaseTool],
    prompt_template: str,
) -> str:
    catalog_entries = []
    for tool in available_tools:
        description = TOOL_SELECTOR_DESCRIPTIONS.get(tool.name)
        if description is None:
            description = tool.description.strip()[:800]
        catalog_entries.append(f"### `{tool.name}`\n{description}")

    return prompt_template.format(tool_catalog="\n\n".join(catalog_entries))


def process_selection_response(
    response: Any,
    available_tools: list[BaseTool],
    max_tools: int | None,
) -> list[BaseTool]:
    if hasattr(response, "model_dump"):
        response = response.model_dump()
    if not isinstance(response, dict):
        raise TypeError(
            "O modelo seletor deve retornar um objeto com a propriedade 'tools'"
        )

    selected_names = response.get("tools")
    if not isinstance(selected_names, list) or not all(
        isinstance(name, str) for name in selected_names
    ):
        raise TypeError("A propriedade 'tools' deve ser uma lista de nomes")

    tools_by_name = {tool.name: tool for tool in available_tools}
    invalid_names = [name for name in selected_names if name not in tools_by_name]
    if invalid_names:
        raise ValueError(
            f"O modelo selecionou tools inválidas: {sorted(set(invalid_names))}"
        )

    unique_names = list(dict.fromkeys(selected_names))
    if max_tools is not None:
        unique_names = unique_names[:max_tools]
    return [tools_by_name[name] for name in unique_names]


def _get_latest_user_message_index(messages: list[BaseMessage]) -> int | None:
    return next(
        (
            index
            for index in reversed(range(len(messages)))
            if isinstance(messages[index], HumanMessage)
            and not is_summary_message(messages[index])
        ),
        None,
    )


def _format_conversation(
    messages: list[BaseMessage], latest_user_index: int, max_message_chars: int
) -> str:
    history = get_messages_before_index(messages, latest_user_index)
    latest_user_message = messages[latest_user_index]

    history_text = _format_messages(history, max_message_chars) or "(sem histórico)"
    latest_content = _message_content(latest_user_message, max_message_chars)
    return (
        "Analise a conversa abaixo seguindo as regras da mensagem de sistema.\n\n"
        "<HISTORICO_DA_CONVERSA>\n"
        f"{history_text}\n"
        "</HISTORICO_DA_CONVERSA>\n\n"
        "<ULTIMA_MENSAGEM_DO_USUARIO>\n"
        f"{latest_content}\n"
        "</ULTIMA_MENSAGEM_DO_USUARIO>"
    )


def _format_messages(messages: list[BaseMessage], max_message_chars: int) -> str:
    formatted_messages = [
        _format_message(message, max_message_chars) for message in messages
    ]
    return "\n\n".join(message for message in formatted_messages if message)


def _format_message(message: BaseMessage, max_message_chars: int) -> str:
    role = _message_role(message)
    content = _message_content(message, max_message_chars)

    if not content:
        return ""
    return f"[{role}]\n{content}"


def _message_role(message: BaseMessage) -> str:
    if is_summary_message(message):
        return "resumo da conversa"
    if isinstance(message, HumanMessage):
        return "usuário"
    if isinstance(message, AIMessage):
        return "assistente"
    return getattr(message, "type", message.__class__.__name__)


def _message_content(message: BaseMessage, max_message_chars: int) -> str:
    content = strip_transport_markers(extract_text_content(message.content))
    return content[:max_message_chars]
