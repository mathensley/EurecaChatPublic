from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState, Runtime
from langchain.chat_models import BaseChatModel
from langchain.messages import AIMessage, HumanMessage, RemoveMessage
from langchain_core.messages import BaseMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from ..helpers.context import Context
from ..prompts.summarizer_prompt import DEFAULT_SUMMARIZER_PROMPT


class SummarizerMiddleware(AgentMiddleware):
    """
    Middleware responsável por resumir o histórico de conversa quando ele passa do limite configurado.

    Identifica pares completos de interação entre usuário e agente, gera um resumo dos pares
    mais antigos e preserva os pares mais recentes, além de manter mensagens ainda não respondidas.
    """

    def __init__(self, model: BaseChatModel, summary_prompt: str = DEFAULT_SUMMARIZER_PROMPT, limit: int = 6, last_n_pairs: int = 2):
        """Inicializa o middleware de sumarização.

        Args:
            model: Modelo usado para gerar o resumo da conversa.
            summary_prompt: Prompt usado para orientar a geração do resumo.
            limit: Quantidade mínima de pares HumanMessage -> AIMessage para acionar a sumarização.
            last_n_pairs: Quantidade de pares mais recentes que devem ser preservados sem resumo.
        """
        if limit < 1:
            raise ValueError("limit must be greater than 0")
        if last_n_pairs < 0:
            raise ValueError("last_n_pairs must be greater than or equal to 0")
        if last_n_pairs >= limit:
            raise ValueError("last_n_pairs must be smaller than limit")
        self.model = model
        self.summary_prompt = summary_prompt
        self.limit = limit
        self.last_n_pairs = last_n_pairs
    
    async def abefore_agent(self, state: AgentState, runtime: Runtime[Context]) -> dict[str, Any] | None:
        """Processa as mensagens antes da execução do agente, podendo acionar a sumarização.

        Args:
            state: Estado atual do agente.
            runtime: Ambiente de execução do agente.

        Returns:
            Um estado atualizado com mensagens resumidas quando a sumarização for realizada.
        """
        messages = state["messages"]

        pairs = self._extract_human_ai_pairs(messages)
        if len(pairs) < self.limit:
            return None

        pairs_to_summarize = pairs[:-self.last_n_pairs] if self.last_n_pairs else pairs
        preserved_pairs = pairs[-self.last_n_pairs:] if self.last_n_pairs else []
        text_to_summarize = self._format_context_to_summarize(self._get_existing_summary_text(messages), pairs_to_summarize)
        if not text_to_summarize:
            return None

        summary = await self._summarize(text_to_summarize)
        if not summary:
            return None

        new_messages = self._build_new_messages(summary)
        preserved_messages = [*self._flatten_pairs(preserved_pairs), *self._get_unpaired_tail(messages, pairs)]

        return {
            "messages": [
                RemoveMessage(id=REMOVE_ALL_MESSAGES),
                *new_messages,
                *preserved_messages,
            ]
        }

    def _extract_human_ai_pairs(self, messages: list[BaseMessage]) -> list[tuple[HumanMessage, AIMessage]]:
        pairs = []
        pending_human = None

        for message in messages:
            if self._is_summary_message(message):
                continue

            if isinstance(message, HumanMessage):
                pending_human = message
                continue

            if pending_human is not None and self._is_final_ai_message(message):
                pairs.append((pending_human, message))
                pending_human = None

        return pairs


    def _is_final_ai_message(self, message: BaseMessage) -> bool:
        if not isinstance(message, AIMessage):
            return False
        if getattr(message, "tool_calls", None):
            return False
        return bool(self._message_content_to_text(message).strip())

    def _is_summary_message(self, message: BaseMessage) -> bool:
        return getattr(message, "additional_kwargs", {}).get("lc_source") == "summarization"

    def _get_existing_summary_text(self, messages: list[BaseMessage]) -> str:
        summaries = [
            self._message_content_to_text(message).strip()
            for message in messages
            if self._is_summary_message(message)
        ]
        return "\n\n".join(summary for summary in summaries if summary)

    def _format_context_to_summarize(self, existing_summary: str, pairs: list[tuple[HumanMessage, AIMessage]]) -> str:
        formatted_pairs = "\n\n---\n\n".join(
            f"Usuário perguntou:\n{self._message_content_to_text(human).strip()}\n\n"
            f"Resposta encontrada:\n{self._message_content_to_text(ai).strip()}"
            for human, ai in pairs
        )
        if existing_summary and formatted_pairs:
            return f"Resumo anterior:\n{existing_summary}\n\n---\n\n{formatted_pairs}"
        return existing_summary or formatted_pairs


    async def _summarize(self, text_to_summarize: str) -> str:
        response = await self.model.ainvoke(
            self.summary_prompt.format(messages=text_to_summarize).rstrip(),
            config={"metadata": {"lc_source": "summarization"}},
        )
        return self._message_content_to_text(response).strip()

    def _build_new_messages(self, summary: str) -> list[HumanMessage]:
        return [
            HumanMessage(
                content=f"Aqui está um resumo da conversa até então:\n\n{summary}",
                additional_kwargs={"lc_source": "summarization"},
            )
        ]

    def _flatten_pairs(self, pairs: list[tuple[HumanMessage, AIMessage]]) -> list[BaseMessage]:
        return [message for pair in pairs for message in pair]

    def _get_unpaired_tail(self, messages: list[BaseMessage], pairs: list[tuple[HumanMessage, AIMessage]]) -> list[BaseMessage]:
        if not pairs:
            return []

        last_ai_message = pairs[-1][1]
        last_ai_index = next(
            i
            for i in reversed(range(len(messages)))
            if messages[i] is last_ai_message
        )
        return [
            message
            for message in messages[last_ai_index + 1:]
            if not self._is_summary_message(message)
        ]

    def _message_content_to_text(self, message: BaseMessage | Any) -> str:
        if isinstance(message, str):
            return message
        content = getattr(message, "content", message)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(
                item.get("text", str(item)) if isinstance(item, dict) else str(item)
                for item in content
            )
        return str(content)
