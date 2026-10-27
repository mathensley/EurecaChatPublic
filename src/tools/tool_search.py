import json
from collections.abc import Sequence
from typing import Annotated

from langchain.tools import ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from langgraph.types import Command

from src.helpers.chat.tool_permissions_utils import filter_tools_for_context
from src.helpers.chat.tool_search_utils import (
    TOOL_SELECTOR_STATE_KEY,
    ToolSearchIndex,
)
from src.helpers.context import Context
from src.helpers.func_utils import get_func_info
from src.helpers.print_tool_call import print_tool_call, print_tool_output


TOOL_SEARCH_NAME = "tool_search"
TOOL_SEARCH_DESCRIPTION = """
Descobre e carrega as ferramentas adequadas para atender à solicitação atual.
Use quando nenhuma ferramenta carregada tratar exatamente do dado ou da ação
necessária. Escreva uma query semântica curta, mas autossuficiente, contendo o
objetivo ativo e o contexto relevante recuperado da conversa; por exemplo:
"consultar início do próximo semestre no calendário acadêmico" ou "obter
fluxograma e disciplinas de Engenharia Civil". Não use apenas referências vagas
como "isso", "a primeira" ou "continue".

A busca retorna as ferramentas mais semanticamente relacionadas e suas
definições ficarão disponíveis na próxima chamada ao modelo. Se o resultado não
servir, chame tool_search novamente com uma query mais específica. Cada nova
busca substitui as ferramentas descobertas pela busca anterior; esta ferramenta
permanece sempre disponível.
""".strip()

TOOL_SEARCH_SYSTEM_PROMPT = """
## Descoberta dinâmica de ferramentas

As ferramentas de domínio são carregadas sob demanda. A ferramenta `tool_search`
permanece disponível o tempo todo:

- Se nenhuma ferramenta carregada atender exatamente à solicitação atual, chame `tool_search` antes de tentar responder.
- Formule uma query autossuficiente com o objetivo atual. Resolva referências curtas usando o histórico antes de escrever a query.
- Depois da busca, use as ferramentas carregadas para concluir a tarefa.
- Se a primeira busca não encontrar uma ferramenta adequada, refine a query e chame `tool_search` novamente.
- Uma nova busca substitui o conjunto descoberto anteriormente. Não faça nova busca quando as ferramentas já carregadas forem suficientes.
""".strip()


def create_tool_search(
    index: ToolSearchIndex,
    available_tools: Sequence[BaseTool],
    *,
    max_tools: int | None,
    always_include: set[str],
) -> BaseTool:
    """Cria a tool de descoberta ligada ao índice deste middleware."""

    @tool(TOOL_SEARCH_NAME, description=TOOL_SEARCH_DESCRIPTION)
    async def tool_search(
        query: Annotated[
            str,
            (
                "Consulta semântica curta autossuficiente que descreve o dado ou ação necessária e inclui o contexto relevante da conversa."
            ),
        ],
        runtime: ToolRuntime[Context],
    ) -> Command:
        func_name, parametros_str = get_func_info(skip_args={"runtime", "available_tools", "index", "max_tools", "always_include"})

        print_tool_call(func_name, parametros_str)
        permitted_tools = filter_tools_for_context(
            available_tools,
            runtime.context,
        )
        searchable_names = {
            candidate.name
            for candidate in permitted_tools
            if candidate.name not in always_include
        }
        results = await index.search(
            query,
            allowed_tool_names=searchable_names,
            k=max_tools,
        )
        selected_names = [result.name for result in results]
        output = {
            "query": query,
            "tools": selected_names,
            "message": (
                "As definições dessas ferramentas estarão disponíveis na próxima chamada ao modelo."
                if selected_names
                else "Nenhuma ferramenta está disponível; refine a query."
            ),
        }
        print_tool_output(func_name, parametros_str, output)
        content = json.dumps(output, ensure_ascii=False)
        return Command(
            update={
                TOOL_SELECTOR_STATE_KEY: selected_names,
                "messages": [
                    ToolMessage(
                        content=content,
                        tool_call_id=runtime.tool_call_id or TOOL_SEARCH_NAME,
                        name=TOOL_SEARCH_NAME,
                    )
                ],
            }
        )
    
    return tool_search
