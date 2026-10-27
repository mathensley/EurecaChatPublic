import logging
from typing import Any, Literal, Optional
from typing_extensions import NotRequired

from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.graph.state import StateGraph, END
from langgraph.graph import MessagesState
from langgraph.runtime import Runtime
from langgraph.types import Checkpointer, Command

from langchain.agents import create_agent
from langchain.chat_models import BaseChatModel
from langchain.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from ..helpers.chat.chat_msgs_utils import (
    guardrail_dict, build_guardrail_system_prompt, build_guardrail_user_prompt,
    strip_guardrail_messages, get_guardrail_fallback_message, get_messages_before_index,
    get_final_agent_response, has_new_summary_message, compact_agent_messages_for_graph,
    extract_text_content, strip_transport_markers, EMPTY_AGENT_RESPONSE
)
from ..helpers.chat.eureca_chat_utils import *
from ..helpers.context import Context
from ..helpers.chat.tool_search_utils import TOOL_SELECTOR_STATE_KEY
from ..prompts.agent_prompt import AGENT_PROMPT_V1


class GuardrailDecision(BaseModel):
    decision: Literal["allow", "block"]
    reason: Literal[
        "in_scope",
        "out_of_scope",
        "prompt_injection",
        "sensitive_internal_request",
        "unsafe_tool_request",
        "unsafe_output_request",
        "abusive_or_spam",
    ]
    confidence: float = Field(ge=0, le=1)

class AgentState(MessagesState):
    # context: str
    summary: NotRequired[str]
    guardrail: dict[str, Any]
    tool_selector_tools: NotRequired[list[str]]


# CRIAR INSTÂNCIA DE CHAT DO EURECA (único agente especializado)
class EurecaChat:

    def __init__(self, agent_model: BaseChatModel, guardrail_model: BaseChatModel | None = None,
                 summary_config: dict[str, Any] | None = None, tool_selector_config: dict[str, Any] | None = None,
                 checkpointer: Optional[Checkpointer] = None, debug_agent: bool = False): # debug_agent é temporário
        # Models
        self.agent_model = agent_model
        self.guardrail_model = guardrail_model or agent_model
        self.guardrail_classifier = self.guardrail_model.with_structured_output(GuardrailDecision, method="function_calling")
        self.summary_config = summary_config
        self.tool_selector_config = tool_selector_config
        self.debug_agent = debug_agent

        # Memória
        self.checkpointer = checkpointer

        # Instancia do agente principal
        self.agent = create_agent(
            name="EurecaChatAgent",
            system_prompt=AGENT_PROMPT_V1,
            model=self.agent_model,
            tools=TOOLS,
            middleware=build_middlewares(self.summary_config, self.tool_selector_config, debug_agent=debug_agent),
            context_schema=Context,
        )


    async def check_user_message(self, state: AgentState, runtime: Runtime[Context]):
        messages = []
        latest_human_index = None
        try:
            messages = list(state["messages"])
            if not messages or not isinstance(messages[-1], HumanMessage):
                return Command(goto="AgentNode", update={"guardrail": guardrail_dict("allow", "in_scope", 1.0)})
            latest_human_index = len(messages) - 1

            guardrail_messages = [
                SystemMessage(content=build_guardrail_system_prompt(runtime.context)),
                HumanMessage(content=build_guardrail_user_prompt(messages, latest_human_index)),
            ]

            #print("\n\nMensagem do checador: ", guardrail_messages, "\n\n")
            result = await self.guardrail_classifier.ainvoke([*guardrail_messages])
            if isinstance(result, dict):
                result = GuardrailDecision.model_validate(result)
            #print("\n\nDecisão do checador: ", result, "\n\n")
            result_dict = result.model_dump()

            if result.decision == "allow":
                cleaned_messages = strip_guardrail_messages(messages)
                if len(cleaned_messages) != len(messages):
                    return Command(
                        goto="AgentNode",
                        update={
                            "messages": [
                                RemoveMessage(id=REMOVE_ALL_MESSAGES),
                                *cleaned_messages,
                            ],
                            "guardrail": result_dict,
                        },
                    )
                return Command(goto="AgentNode", update={"guardrail": result_dict})

            return Command(
                goto=END,
                update={
                    "messages": [
                        RemoveMessage(id=REMOVE_ALL_MESSAGES),
                        *get_messages_before_index(messages, latest_human_index),
                        HumanMessage(
                            content="Mensagem bloqueada",
                            additional_kwargs={"lc_source": "guardrail", "guardrail_reason": result.reason}
                        ),
                        AIMessage(
                            content=get_guardrail_fallback_message(result.reason),
                            additional_kwargs={"lc_source": "guardrail", "guardrail_reason": result.reason}
                        ),
                    ],
                    "guardrail": result_dict,
                },
            )
        except Exception as e:
            #print("\n\nErro ao processar a mensagem no guardrail: ", e, "\n\n")
            logging.exception("Erro ao processar a mensagem no guardrail: %s", e)
            sanitized_messages = []
            if latest_human_index is not None:
                sanitized_messages = [
                    RemoveMessage(id=REMOVE_ALL_MESSAGES),
                    *get_messages_before_index(messages, latest_human_index),
                    HumanMessage(
                        content="Mensagem bloqueada",
                        additional_kwargs={"lc_source": "guardrail", "guardrail_reason": "guardrail_error"})
                ]
            return Command(
                goto=END,
                update={
                    "messages": [
                        *sanitized_messages,
                        AIMessage(
                            content="Houve um problema para validar sua mensagem. Tente novamente ou tente reformular melhor a sua pergunta.",
                            additional_kwargs={"lc_source": "guardrail", "guardrail_reason": "guardrail_error"},
                        )
                    ],
                    "guardrail": guardrail_dict("block", "guardrail_error", 0.0),
                },
            )


    async def agent_node(self, state: AgentState, config: RunnableConfig):
        try:
            current_messages = list(state["messages"])

            result = await self.agent.ainvoke(state, config=config)

            selector_state_update = {}
            if (isinstance(result, dict) and isinstance(result.get(TOOL_SELECTOR_STATE_KEY), list)):
                selector_state_update[TOOL_SELECTOR_STATE_KEY] = result[TOOL_SELECTOR_STATE_KEY]

            if isinstance(result, dict) and "messages" in result:
                messages = result["messages"]
                #print("\n\nMensagens retornadas pelo agente:", messages, "\n\n")
                message = get_final_agent_response(messages)
                if message is None:
                    return {
                        **selector_state_update,
                        "messages": [
                            AIMessage(
                                content=EMPTY_AGENT_RESPONSE,
                                additional_kwargs={"lc_source": "agent_fallback"},
                            )
                        ],
                    }

                final_message = AIMessage(content=strip_transport_markers(extract_text_content(message.content)))
                if has_new_summary_message(current_messages, messages):
                    compacted_messages = compact_agent_messages_for_graph(messages)
                    if compacted_messages and isinstance(compacted_messages[-1], AIMessage):
                        compacted_messages = compacted_messages[:-1]
                    return {
                        **selector_state_update,
                        "messages": [
                            RemoveMessage(id=REMOVE_ALL_MESSAGES),
                            *compacted_messages,
                            final_message,
                        ],
                    }
                return {**selector_state_update, "messages": [final_message]}
            return {
                **selector_state_update,
                "messages": [
                    AIMessage(
                        content=EMPTY_AGENT_RESPONSE,
                        additional_kwargs={"lc_source": "agent_fallback"},
                    )
                ],
            }
        except Exception as e:
            logging.exception("Erro ao processar a mensagem no agente: %s", e)
            return {"messages": [AIMessage(content="Ocorreu um erro interno ao processar sua mensagem. Tente novamente.")]}


    def build(self):
        graph = StateGraph(AgentState, context_schema=Context)
        graph.add_node("CheckUserMessage", self.check_user_message, destinations=("AgentNode", END))
        graph.add_node("AgentNode", self.agent_node)

        graph.add_edge("AgentNode", END)
        graph.set_entry_point("CheckUserMessage")

        return graph.compile(checkpointer=self.checkpointer)
