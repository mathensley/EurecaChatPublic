from typing import Any

from langchain_core.callbacks import AsyncCallbackHandler
from langgraph.prebuilt import ToolNode

from src.middlewares.prompt_middlewares import add_context
from src.middlewares.tools_middlewares import (
    context_based_tools,
    describe_eureca_database_for_user,
    handle_tool_errors
)
from src.middlewares.tool_selector_middleware import ToolSelectorMiddleware
from src.middlewares.log_agent_middleware import LogAgentMiddleware
from src.middlewares.summarizer_middleware import SummarizerMiddleware
from src.prompts.summarizer_prompt import DEFAULT_SUMMARIZER_PROMPT
from src.helpers.chat.chat_msgs_utils import (
    FINAL_RESPONSE_MARKER,
    TOOL_PREAMBLE_MARKER,
    extract_text_content,
    strip_transport_markers,
)

from src.tools.disciplina import *
from src.tools.curso import *
from src.tools.estudante import *
from src.tools.busca_portal_ufcg import busca_portal_ufcg
from src.tools.eureca.eureca_database import EURECA_DATABASE_TOOL
from src.tools.eureca.eureca_bash.execute_bash import execute_bash

TOOLS = [
    buscar_fluxograma,
    buscar_horarios_turmas_vagas_disciplina,
    buscar_plano_curso_disciplina,
    buscar_grade_curricular_curso,
    buscar_calendarios,
    # busca_portal_ufcg,
    estudante_info,
    historico_estudante,
    professor_info,
    execute_bash,
    EURECA_DATABASE_TOOL
]


class SocketIOStreamingHandler(AsyncCallbackHandler):
    OPENING_MARKERS = {
        FINAL_RESPONSE_MARKER: "final",
        TOOL_PREAMBLE_MARKER: "step",
    }
    CLOSING_MARKERS = ("</final_response>", "</tool_preamble>")

    def __init__(self, sid, socketio):
        self.sid = sid
        self.sio = socketio
        self._llm_runs: dict[str, dict[str, Any]] = {}
        self._step_sequence = 0

    async def emit(self, event, data):
        # As tools existentes usam ``status`` para publicar uma descrição amigável
        # da consulta. No cliente isso é uma etapa, não a resposta do assistente.
        if event == "status":
            text = extract_text_content(data.get("resposta")) if isinstance(data, dict) else ""
            if not text:
                return
            self._step_sequence += 1
            await self._emit_step(
                step_id=f"tool:{self._step_sequence}",
                text=text,
                append=False,
            )
            return
        await self.sio.emit(event, data, room=self.sid)

    async def _emit_step(self, step_id: str, text: str, append: bool):
        await self.sio.emit(
            "etapa",
            {
                "id": step_id,
                "resposta": text,
                "modo": "append" if append else "replace",
            },
            room=self.sid,
        )

    async def _emit_classified_text(self, state: dict[str, Any], text: str) -> None:
        """Emite texto já classificado sem deixar tags de transporte vazarem."""
        state["suffix_buffer"] += text
        for marker in (*self.OPENING_MARKERS, *self.CLOSING_MARKERS):
            state["suffix_buffer"] = state["suffix_buffer"].replace(marker, "")

        suffix_size = max(
            (
                size
                for marker in self.CLOSING_MARKERS
                for size in range(1, min(len(state["suffix_buffer"]), len(marker) - 1) + 1)
                if state["suffix_buffer"].endswith(marker[:size])
            ),
            default=0,
        )
        if suffix_size:
            visible_text = state["suffix_buffer"][:-suffix_size]
            state["suffix_buffer"] = state["suffix_buffer"][-suffix_size:]
        else:
            visible_text = state["suffix_buffer"]
            state["suffix_buffer"] = ""

        if not visible_text:
            return
        if state["mode"] == "final":
            await self.sio.emit("token", {"resposta": visible_text}, room=self.sid)
        else:
            state["emitted_step_text"] += visible_text
            await self._emit_step(state["step_id"], visible_text, append=True)

    @staticmethod
    def _response_has_tool_calls(response: Any) -> bool:
        for generations in getattr(response, "generations", []) or []:
            for generation in generations or []:
                message = getattr(generation, "message", None)
                if message is not None and getattr(message, "tool_calls", None):
                    return True
                generation_info = getattr(generation, "generation_info", None) or {}
                if generation_info.get("finish_reason") == "tool_calls":
                    return True
        return False

    async def on_llm_new_token(self, token: str | list[str | dict[str, Any]], **kwargs):
        run_id = str(kwargs.get("run_id") or "unknown")
        state = self._llm_runs.setdefault(
            run_id,
            {
                "text": "",
                "mode": "unknown",
                "step_id": f"model:{run_id}",
                "prefix_buffer": "",
                "suffix_buffer": "",
                "emitted_step_text": "",
            },
        )

        text = extract_text_content(token)
        if not text:
            return
        state["text"] += text

        if state["mode"] != "unknown":
            await self._emit_classified_text(state, text)
            return

        state["prefix_buffer"] += text
        stripped_prefix = state["prefix_buffer"].lstrip()

        for marker, mode in self.OPENING_MARKERS.items():
            if not stripped_prefix.startswith(marker):
                continue
            state["mode"] = mode
            visible_text = stripped_prefix[len(marker):].lstrip()
            state["prefix_buffer"] = ""
            if mode == "final":
                await self.sio.emit("resposta_inicio", {}, room=self.sid)
            await self._emit_classified_text(state, visible_text)
            return

        # Continua aguardando enquanto o prefixo ainda pode formar uma tag válida.
        if not stripped_prefix or any(
            marker.startswith(stripped_prefix) for marker in self.OPENING_MARKERS
        ):
            return

        # Texto sem marcador nunca abre a caixa de resposta durante a geração.
        # Ele fica nas etapas e só é promovido no encerramento, se realmente for
        # uma resposta sem tool call.
        state["mode"] = "step"
        visible_text = state["prefix_buffer"]
        state["prefix_buffer"] = ""
        await self._emit_classified_text(state, visible_text)

    async def on_llm_end(self, response, **kwargs):
        run_id = str(kwargs.get("run_id") or "unknown")
        state = self._llm_runs.pop(run_id, None)
        if not state or not state["text"]:
            return

        has_tool_calls = self._response_has_tool_calls(response)
        visible_text = strip_transport_markers(state["text"])

        if state["mode"] == "final" and has_tool_calls:
            # Se o modelo marcou um preâmbulo como resposta final, a tool call
            # permite desfazer a caixa e reclassificar o texto como etapa.
            await self.sio.emit(
                "resposta_reclassificada",
                {"id": state["step_id"], "resposta": visible_text},
                room=self.sid,
            )
            return

        if state["mode"] != "final" and not has_tool_calls:
            # Fallback para modelos que esquecerem o marcador: remove a etapa,
            # mas deixa o evento ``resposta_final`` preencher a caixa somente
            # depois que a geração tiver terminado.
            await self.sio.emit(
                "resposta_inicio",
                {"etapa_id": state["step_id"]},
                room=self.sid,
            )
            return

        if state["mode"] != "final" and has_tool_calls:
            state["suffix_buffer"] = ""
            remaining_text = visible_text[len(state["emitted_step_text"]):]
            if remaining_text:
                await self._emit_step(state["step_id"], remaining_text, append=True)


def build_middlewares(summary_config: dict[str, Any] | None = None, tool_selector_config: dict[str, Any] | None = None, debug_agent: bool = False):
    """Constrói a lista de middlewares usados pelo agente.

    Args:
        summary_config: Configuração opcional para habilitar o SummarizerMiddleware.
            Quando informado, pode conter os seguintes argumentos: 'model', 'summary_prompt', 'limit'
            e 'last_n_pairs'. O 'summary_prompt' padrão é aplicado caso não seja sobrescrito.
        tool_selector_config: Configuração opcional para habilitar o ToolSelectorMiddleware.
            Quando informado, pode conter argumentos como 'model', 'strategy',
            'llm_mode', 'max_tools', 'max_message_chars' e 'always_include'.

    Returns:
        Lista de middlewares que serão passados para o agente.
    """
    middlewares = [
        handle_tool_errors,
        context_based_tools,
        describe_eureca_database_for_user,
        add_context,
    ]

    if summary_config is not None:
        summary_config = {
            "summary_prompt": DEFAULT_SUMMARIZER_PROMPT,
            **summary_config,
        }
        middlewares.append(SummarizerMiddleware(**summary_config))

    if tool_selector_config is not None:
        normalized_tools = list(ToolNode(TOOLS).tools_by_name.values())
        selector_config = {
            "available_tools": normalized_tools,
            **tool_selector_config,
        }
        middlewares.append(ToolSelectorMiddleware(**selector_config))

    middlewares.append(LogAgentMiddleware(debug=debug_agent))
    return middlewares
