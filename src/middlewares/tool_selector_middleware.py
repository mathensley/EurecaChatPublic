from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from langchain.agents.middleware import (
    AgentMiddleware,
    AgentState,
    ExtendedModelResponse,
    ModelRequest,
    ModelResponse,
)
from langchain.chat_models.base import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool
from langgraph.types import Command
from typing_extensions import NotRequired

from src.helpers.chat.tool_search_utils import (
    SQLiteToolSearchIndex,
    TOOL_SELECTOR_STATE_KEY,
    get_selected_tool_names,
)
from src.helpers.chat.tool_selector_utils import (
    DEFAULT_SELECTOR_MAX_MESSAGE_CHARS,
    ToolSelectorLLMMode,
    ToolSelectorStrategy,
    create_prompt_tool_selection_response,
    create_tool_selection_response,
    is_new_user_turn,
    merge_tool_groups,
    normalize_selector_llm_mode,
    normalize_selector_strategy,
    partition_always_include_tools,
    prepare_selection_request,
    process_selection_response,
    require_base_tools,
)
from src.prompts.tool_selector_prompt import DEFAULT_SELECTOR_PROMPT
from src.prompts.tool_selector_tools_prompt import DEFAULT_TOOL_CATALOG_PROMPT
from src.tools.tool_search import (
    TOOL_SEARCH_NAME,
    TOOL_SEARCH_SYSTEM_PROMPT,
    create_tool_search,
)


class ToolSelectorState(AgentState):
    tool_selector_tools: NotRequired[list[str]]


class ToolSelectorMiddleware(AgentMiddleware[ToolSelectorState]):
    """Seleciona tools usando uma estratégia configurável."""

    state_schema = ToolSelectorState

    def __init__(
        self,
        model: str | BaseChatModel | None = None,
        max_tools: int | None = 5,
        strategy: str = "LLM",
        llm_mode: str = "SCHEMA",
        max_message_chars: int = DEFAULT_SELECTOR_MAX_MESSAGE_CHARS,
        always_include: Sequence[str] | None = None,
        available_tools: Sequence[BaseTool] | None = None,
    ) -> None:
        """Inicializa o seletor e prepara os recursos exigidos pela estratégia.

        Args:
            model: Modelo usado pela estratégia ``LLM``. Quando omitido, utiliza
                o modelo presente na requisição do agente.
            max_tools: Quantidade máxima de tools selecionadas. As tools de
                ``always_include`` não entram nesse limite. ``None`` desativa o
                limite.
            strategy: Estratégia de seleção. Atualmente, ``LLM`` seleciona antes
                da primeira chamada ao modelo após cada mensagem do usuário e
                ``TOOL_CALL`` disponibiliza a descoberta dinâmica por meio da
                tool ``tool_search``.
            llm_mode: Forma de apresentar o catálogo na estratégia ``LLM``:
                ``SCHEMA`` inclui as descrições no schema estruturado e ``PROMPT``
                inclui o catálogo no prompt.
            max_message_chars: Limite de caracteres aplicado individualmente às
                mensagens usadas como contexto pela estratégia ``LLM``.
            always_include: Nomes das tools que devem permanecer sempre
                disponíveis, independentemente da seleção e de ``max_tools``.
            available_tools: Catálogo completo de tools. É obrigatório para
                ``TOOL_CALL`` e usado para criar o índice de busca na
                inicialização.

        Raises:
            ValueError: Se algum limite for inválido, se ``always_include`` contiver tools inexistentes ou se ``TOOL_CALL`` não receber um catálogo de tools.
        """
        if max_tools is not None and max_tools < 1:
            raise ValueError("max_tools deve ser maior que zero ou None")
        if max_message_chars < 1:
            raise ValueError("max_message_chars deve ser maior que zero")
        
        self.model = init_chat_model(model) if isinstance(model, str) else model
        self.max_tools = max_tools
        self.strategy: ToolSelectorStrategy = normalize_selector_strategy(strategy)
        self.llm_mode: ToolSelectorLLMMode = normalize_selector_llm_mode(llm_mode)
        self.max_message_chars = max_message_chars
        self.always_include = tuple(dict.fromkeys(always_include or ()))
        self._always_include_set = set(self.always_include)
        self.available_tools = list(available_tools or ())
        self.tools: list[BaseTool] = []
        self._tool_search: BaseTool | None = None

        self._validate_always_include()

        if self.strategy == "TOOL_CALL":
            if not self.available_tools:
                raise ValueError(
                    "A estratégia TOOL_CALL requer available_tools para criar "
                    "o índice antes da aplicação iniciar"
                )
            index = SQLiteToolSearchIndex(self.available_tools)
            self._tool_search = create_tool_search(
                index,
                self.available_tools,
                max_tools=self.max_tools,
                always_include=self._always_include_set,
            )
            # Middlewares podem registrar tools adicionais no create_agent.
            self.tools = [self._tool_search]

    async def awrap_model_call(self, request: ModelRequest, handler: Callable[[ModelRequest], Awaitable[ModelResponse]]) -> ModelResponse | ExtendedModelResponse:
        if self.strategy == "LLM":
            return await self._awrap_model_call_llm(request, handler)
        if self.strategy == "TOOL_CALL":
            return await self._awrap_model_call_tool_call(request, handler)
        raise NotImplementedError(
            f"A estratégia {self.strategy} ainda não foi implementada"
        )

    async def _awrap_model_call_llm(self, request: ModelRequest, handler: Callable[[ModelRequest], Awaitable[ModelResponse]]) -> ModelResponse | ExtendedModelResponse:
        """Seleciona uma vez por mensagem do usuário e reutiliza durante o ciclo."""

        request_tools = require_base_tools(request.tools)
        selectable_tools, always_tools = partition_always_include_tools(request_tools, self._always_include_set)

        if not is_new_user_turn(request.messages):
            selected_names = set(get_selected_tool_names(request.state))
            selected_tools = [tool for tool in selectable_tools if tool.name in selected_names]
            model_tools = merge_tool_groups(always_tools, selected_tools)
            print("\nFerramentas reutilizadas nesta interação: ", [tool.name for tool in model_tools], "\n")
            return await handler(request.override(tools=model_tools))

        if not selectable_tools:
            model_response = await handler(request.override(tools=always_tools))
            return self._with_llm_selection_state(model_response, [])

        selection_request = prepare_selection_request(
            request.override(tools=selectable_tools),
            model=self.model,
            tool_selector_prompt=DEFAULT_SELECTOR_PROMPT,
            tool_catalog_prompt=(DEFAULT_TOOL_CATALOG_PROMPT if self.llm_mode == "PROMPT" else None),
            max_tools=self.max_tools,
            max_message_chars=self.max_message_chars,
        )
        if selection_request is None:
            model_response = await handler(request.override(tools=always_tools))
            return self._with_llm_selection_state(model_response, [])

        type_adapter = (
            create_prompt_tool_selection_response()
            if self.llm_mode == "PROMPT"
            else create_tool_selection_response(selection_request.available_tools)
        )
        schema = type_adapter.json_schema()
        structured_model = selection_request.model.with_structured_output(schema)
        print("\nMensagem do seletor de tools: ", selection_request.model_messages, "\n")
        response = await structured_model.ainvoke(selection_request.model_messages)
        print("\nResposta do seletor de tools: ", response, "\n")
        selected_tools = process_selection_response(response, selection_request.available_tools, self.max_tools)
        print("\nFerramentas selecionadas: ", [tool.name for tool in selected_tools], "\n")
        model_tools = merge_tool_groups(always_tools, selected_tools)
        model_response = await handler(request.override(tools=model_tools))
        return self._with_llm_selection_state(model_response, [tool.name for tool in selected_tools])

    async def _awrap_model_call_tool_call(self, request: ModelRequest, handler: Callable[[ModelRequest], Awaitable[ModelResponse]]) -> ModelResponse:
        """Expõe a busca e as tools carregadas por ela no estado da conversa."""

        request_tools = require_base_tools(request.tools)
        search_tools = [tool for tool in request_tools if tool.name == TOOL_SEARCH_NAME]
        if not search_tools and self._tool_search is not None:
            search_tools = [self._tool_search]

        domain_tools = [tool for tool in request_tools if tool.name != TOOL_SEARCH_NAME]
        selectable_tools, always_tools = partition_always_include_tools(domain_tools, self._always_include_set)
        selected_names = set(get_selected_tool_names(request.state))
        selected_tools = [tool for tool in selectable_tools if tool.name in selected_names]

        model_tools = merge_tool_groups(search_tools, always_tools, selected_tools)
        system_message = self._with_tool_search_instructions(request.system_message)
        print("\nFerramentas disponíveis após tool_search: ", [tool.name for tool in model_tools], "\n")
        return await handler(request.override(tools=model_tools, system_message=system_message))

    def _validate_always_include(self) -> None:
        if TOOL_SEARCH_NAME in self._always_include_set:
            raise ValueError("tool_search já é incluída automaticamente e não deve estar em always_include")
        if not self.available_tools or not self._always_include_set:
            return
        available_names = {tool.name for tool in self.available_tools}
        missing_names = sorted(self._always_include_set - available_names)
        if missing_names:
            raise ValueError(
                "Tools em always_include não foram encontradas: "
                f"{missing_names}. Disponíveis: {sorted(available_names)}"
            )

    @staticmethod
    def _with_llm_selection_state(model_response: ModelResponse, selected_names: list[str]) -> ModelResponse | ExtendedModelResponse:
        if not isinstance(model_response, ModelResponse):
            return model_response
        return ExtendedModelResponse(
            model_response=model_response,
            command=Command(update={TOOL_SELECTOR_STATE_KEY: selected_names})
        )

    @staticmethod
    def _with_tool_search_instructions(system_message: SystemMessage | None) -> SystemMessage:
        if system_message is None:
            return SystemMessage(content=TOOL_SEARCH_SYSTEM_PROMPT)

        content_blocks: list[Any] = list(system_message.content_blocks)
        if any(
            isinstance(block, dict)
            and TOOL_SEARCH_SYSTEM_PROMPT in str(block.get("text", ""))
            for block in content_blocks
        ):
            return system_message
        content_blocks.append({"type": "text", "text": TOOL_SEARCH_SYSTEM_PROMPT})
        return SystemMessage(content=content_blocks)
