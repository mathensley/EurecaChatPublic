from langchain.agents.middleware import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
)
from collections.abc import Callable
from typing import Any

class LogAgentMiddleware(AgentMiddleware):
    def __init__(self, debug: bool = False):
        # Mantém compatibilidade com os pontos que ainda passam essa opção.
        # Este middleware agora sempre mostra as tools de cada chamada.
        self.debug = debug

    async def awrap_model_call(self, request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]) -> ModelResponse:
        #print("\n\nTools: " + ", ".join([self._get_tool_name(tool) for tool in request.tools]) + "\n\n")
        return await handler(request)

    @staticmethod
    def _get_tool_name(tool: Any) -> str:
        if not isinstance(tool, dict):
            return tool.name

        if "name" in tool:
            return tool["name"]

        return tool["function"]["name"]
