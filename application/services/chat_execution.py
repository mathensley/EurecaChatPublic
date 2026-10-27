import asyncio
import json
import logging
import uuid

from langchain_core.messages import AIMessage, HumanMessage
from openinference.instrumentation import using_attributes

from src.helpers.chat.chat_msgs_utils import extract_text_content
from src.helpers.chat.eureca_chat_utils import SocketIOStreamingHandler
from src.helpers.context import Context
from src.tools.eureca.eureca_bash.workdir import remover_work_dir

from ..core.current_period import local_now
from ..core.metrics import chat_finished, chat_started
from ..core.utils.file_handler.attachment_storage import salvar_arquivos_no_sandbox
from ..core.utils.file_handler.handler import construir_mensagem_com_arquivos
from ..core.utils.rate_limiter import check_rate_limit
from ..core.utils.token_handler import get_info, parse_user_profile
from ..core.utils.token_usage_callback import TokenCounterCallback
from ..db.chat_tab.chat_crud import (
    add_chat_message,
    create_chat_tab,
    get_chat_tab_for_user,
    update_at_by_chat_tab_id,
    update_chat_tab_context,
)
from ..db.token_usage.token_usage_crud import record_token_usage
from ..db.user.user_crud import get_user_by_cpf
from ..socket.sessions import anon_sessions


socket_logger = logging.getLogger("socket")


async def execute_system(app, sio, sid, user_message, arquivos, token, chat_tab_id, client_ip="unknown"):
    auth_label, metrics_started_at = chat_started(bool(token))
    metrics_status = "rejected"
    try:
        context = ""
        new_context = None
        user_role = None
        user_identifier = None
        matricula = None
        cpf = None
        nome = None
        user = None

        token_counter = TokenCounterCallback()

        if token:
            session = anon_sessions.get(sid)
            user_info = session.get("user_info") if session else None
            if user_info is None:
                user_info = await get_info(token)
                if session and user_info:
                    session["user_info"] = user_info
            if not user_info or not user_info.get("id"):
                if session:
                    session["token"] = None
                    session["is_anonymous"] = True
                await sio.emit(
                    "erro",
                    {"mensagem": "Sessão inválida ou expirada."},
                    room=sid,
                )
                return
            nome, cpf, user_identifier, user_role = parse_user_profile(user_info)
            matricula = user_identifier

            if session:
                old_anon_thread = (
                    session.get("thread_id") if session.get("is_anonymous") else None
                )
                session["is_anonymous"] = False
                session["thread_id"] = None
                if old_anon_thread:
                    await app.checkpointer.adelete_thread(old_anon_thread)
                    await remover_work_dir(old_anon_thread)

            cached_user = session.get("user") if session else None
            if cached_user is None:
                async with app.db_pool.acquire() as conn:
                    stored_user = await get_user_by_cpf(conn, cpf)
                if not stored_user:
                    await sio.emit("erro", {"mensagem": ("Cadastro local não encontrado. Faça login novamente no sistema.")}, room=sid)
                    return
                user = dict(stored_user)
                if session:
                    session["user"] = user
            else:
                user = cached_user

            nome = user["nome"]
            cpf = user["cpf"]
            user_identifier = user["matricula"]
            matricula = user_identifier

        current_period = await app.current_period_cache.get_current_period()
        current_date = local_now().strftime("%d/%m/%Y")

        runtime_context = Context(
            token=token,
            user_role=user_role or "anon",
            user_indentifier=user_identifier,
            user_name=nome,
            user_cpf=cpf,
            current_time=current_date,
            current_period=current_period,
        )

        # ── RATE LIMIT ──────────────────────────────────────────────────
        rl_identifier = matricula or cpf or client_ip
        rl_id_type    = "user" if token else "ip"
        # within_limit, consumed, limit = await check_rate_limit(app.db_pool, rl_identifier, rl_id_type)
        # if not within_limit:
        #     socket_logger.warning(
        #         "rate_limit_blocked",
        #         extra={"identifier": rl_identifier, "id_type": rl_id_type, "consumed": consumed, "limit": limit}
        #     )
        #     await sio.emit(
        #         "resposta_final",
        #         {"resposta": (
        #             "Você atingiu o limite diário de uso do EurecaAI. "
        #             "Tente novamente amanhã."
        #         )},
        #         room=sid
        #     )
        #     return
        # ───────────────────────────────────────────────────────────────────

        if token:
            if not chat_tab_id:
                if not matricula and not cpf:
                    await sio.emit(
                        "resposta_final",
                        {"resposta": "Usuário inválido"},
                        room=sid,
                    )
                    return

                async with app.db_pool.acquire() as conn:
                    initial_title = user_message[:60].strip() or "Novo Chat"
                    chat_tab = await create_chat_tab(conn, user["id"], initial_title)
                    chat_db_id = chat_tab["id"]
                    chat_tab_id = str(chat_db_id)
            else:
                try:
                    chat_db_id = uuid.UUID(str(chat_tab_id))
                except (TypeError, ValueError):
                    await sio.emit(
                        "erro",
                        {"mensagem": "Conversa inválida."},
                        room=sid,
                    )
                    return

            async with app.db_pool.acquire() as conn:
                owned_chat = await get_chat_tab_for_user(conn, chat_db_id, cpf)
                if not owned_chat:
                    await sio.emit(
                        "erro",
                        {"mensagem": "Conversa não encontrada."},
                        room=sid,
                    )
                    return
                context = owned_chat["context"] or ""

        socket_stream_handler = SocketIOStreamingHandler(sid=sid, socketio=sio)

        config = {
            "run_name": "EurecaChat",
            "configurable": {
                "thread_id": chat_tab_id,
                "callbacks_sio": [socket_stream_handler],
            }, # thread_id é o id do chat_tab gerado ao ser criado no BD, caso não tenha usuário logado é um id gerado temporariamente
            "token": token,
            "user_role": user_role,
            "user_attributes": user_identifier,
            "callbacks_sio": [socket_stream_handler],
            "callbacks": [token_counter, socket_stream_handler],
            "current_context": context,
        }

        await sio.emit("status", {"resposta": "Processando a pergunta"}, room=sid)

        filename = []
        if arquivos and isinstance(arquivos, list) and len(arquivos) > 0:
            arquivos_salvos = await salvar_arquivos_no_sandbox(chat_tab_id, arquivos)
            filename = [
                arquivo["filename"]
                for arquivo in arquivos
                if arquivo.get("filename")
            ]
            caminhos_workspace = "\n".join(
                f"- {arquivo['nome_original']}: {arquivo['caminho_workspace']}"
                for arquivo in arquivos_salvos
            )
            await sio.emit("status", {"resposta": "Lendo arquivos..."}, room=sid)
            file_message = await asyncio.to_thread(
                construir_mensagem_com_arquivos,
                (
                    f"{user_message}\n\n"
                    "Arquivos anexados disponíveis no sandbox desta conversa "
                    "para uso pelas ferramentas:\n"
                    f"{caminhos_workspace}"
                ),
                arquivos,
            )
            text_blocks = [
                block.get("text", "")
                for block in file_message.content
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            if len(" ".join(text_blocks).split()) > 30000:
                inputs = {
                    "messages": [
                        HumanMessage(
                            content=(
                                "Você recebeu um PDF grande de mais. Por favor, "
                                "responda que o arquivo PDF extrapolou o limite e "
                                "que deve enviar um arquivo menor."
                            )
                        )
                    ]
                }
            else:
                inputs = {"messages": [file_message]}
        else:
            inputs = {"messages": [HumanMessage(content=user_message)]}

        response = ""

        trace_metadata = {
            "sid": sid,
            "authenticated": bool(token),
            "user_role": user_role,
            "has_files": bool(arquivos),
            "files_count": len(arquivos) if arquivos else 0,
        }

        with using_attributes(
            session_id=str(chat_tab_id),
            user_id=str(matricula) if matricula else None,
            metadata=trace_metadata,
            tags=["eureca-chat", "socketio", "langgraph"],
        ):
            last_ai_msg = None
            async for chunk in app.system.astream(
                inputs,
                config,
                stream_mode="values",
                context=runtime_context,
            ):
                msgs = chunk.get("messages")
                if not isinstance(msgs, list) or not msgs:
                    continue

                last_msg = msgs[-1]
                #last_msg.pretty_print()
                new_context = chunk.get("context")

                if isinstance(last_msg, AIMessage) and last_msg.content:
                    response = extract_text_content(last_msg.content)
                    last_ai_msg = last_msg

            response = response or "Desculpe, não consegui processar sua solicitação."

        # ── REGISTRO DE USO DE TOKENS ──────────────────────────────────────
        socket_logger.info(
            "token_usage_captured",
            extra={
                "input_tokens": token_counter.input_tokens,
                "output_tokens": token_counter.output_tokens,
                "total_tokens": token_counter.total_tokens,
            },
        )

        async with app.db_pool.acquire() as conn:
            await record_token_usage(
                conn,
                rl_identifier,
                rl_id_type,
                token_counter.input_tokens,
                token_counter.output_tokens,
                token_counter.total_tokens,
            )
        # ───────────────────────────────────────────────────────────────────

        if token:
            async with app.db_pool.acquire() as conn:
                await add_chat_message(
                    conn,
                    chat_db_id,
                    "human_message",
                    user_message,
                    json.dumps(filename),
                )
                await add_chat_message(
                    conn,
                    chat_db_id,
                    "ai_message",
                    response,
                    None,
                )
                await update_at_by_chat_tab_id(conn, chat_db_id)
                if new_context:
                    await update_chat_tab_context(conn, chat_db_id, new_context)
            await sio.emit(
                "resposta_final",
                {"resposta": response, "chat_id": chat_tab_id},
                room=sid,
            )
        else:
            await sio.emit(
                "resposta_final",
                {"resposta": response, "chat_id": chat_tab_id},
                room=sid,
            )

        metrics_status = "success"

    except asyncio.CancelledError:
        metrics_status = "cancelled"
        raise
    except Exception as e:
        metrics_status = "error"
        socket_logger.error(
            "unexpected_error",
            extra={"error": str(e)},
            exc_info=True,
        )
        await sio.emit(
            "resposta_final",
            {
                "resposta": (
                    "Não foi possível processar sua solicitação agora. "
                    "Se o problema continuar, tente mais tarde."
                )
            },
            room=sid,
        )
    finally:
        chat_finished(auth_label, metrics_status, metrics_started_at)
