import asyncio
import logging
import uuid
from contextlib import suppress
from http.cookies import SimpleCookie

from src.tools.eureca.eureca_bash.workdir import remover_work_dir

from ..core.metrics import (
    observe_socket_event,
    socket_connected,
    socket_disconnected,
)
from ..core.utils.file_handler.attachment_storage import (
    ALLOWED_ATTACHMENT_EXTENSIONS,
    MAX_ATTACHMENT_BASE64_CHARS,
)
from ..services.chat_execution import execute_system
from .sessions import anon_sessions


socket_logger = logging.getLogger("socket")


def register_socket_handlers(sio, app) -> None:
    """Registra os eventos Socket.IO e mantém o estado por conexão."""

    @sio.on("connect")
    async def connect(sid, environ):
        scope = environ.get("asgi.scope", {})

        # Captura o ip do cliente n conexão
        forwarded_for = environ.get("HTTP_X_FORWARDED_FOR", "")
        client_ip = (
            forwarded_for.split(",")[0].strip()
            if forwarded_for
            else environ.get("REMOTE_ADDR", "unknown")
        )
        cookies = SimpleCookie()
        cookies.load(environ.get("HTTP_COOKIE", ""))
        auth_cookie = cookies.get("eureca_token")

        socket_logger.info(
            "client_connected",
            extra={
                "sid": sid,
                "type": scope.get("type"),
                "client_ip": client_ip,
                "has_auth_cookie": bool(auth_cookie),
            },
        )

        anon_sessions[sid] = {
            "thread_id": None,
            "is_anonymous": auth_cookie is None,
            "client_ip": client_ip,
            "task": None,
            "token": auth_cookie.value if auth_cookie else None,
        }
        socket_connected(len(anon_sessions))

    @sio.on("disconnect")
    async def disconnect(sid, reason=None):
        session = anon_sessions.pop(sid, None)
        socket_disconnected(len(anon_sessions))
        socket_logger.info(
            "client_disconnected",
            extra={
                "sid": sid,
                "reason": str(reason) if reason is not None else None,
                "is_anonymous": session.get("is_anonymous") if session else None,
                "has_thread": bool(session and session.get("thread_id")),
            },
        )
        if session and session["is_anonymous"]:
            task = session.get("task")
            if task and not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

        if session and session["is_anonymous"] and session["thread_id"]:
            socket_logger.info(
                "anonymous_checkpoint_deleted",
                extra={"thread_id": session["thread_id"]},
            )
            try:
                await app.checkpointer.adelete_thread(session["thread_id"])
            except Exception:
                # A limpeza de um chat anônimo é best-effort e não deve quebrar o
                # fluxo interno de desconexão do Socket.IO durante uma queda do DB.
                socket_logger.exception(
                    "anonymous_checkpoint_delete_failed",
                    extra={"thread_id": session["thread_id"]},
                )
            await remover_work_dir(session["thread_id"])

    @sio.on("new_chat")
    async def new_anonymous_chat(sid):
        """Descarta explicitamente a memória do chat anônimo atual."""
        session = anon_sessions.get(sid)
        if not session or not session.get("is_anonymous"):
            return {"ok": True}
        task = session.get("task")
        if task and not task.done():
            return {"ok": False, "error": "Há uma resposta em processamento"}
        thread_id = session.get("thread_id")
        if thread_id:
            await app.checkpointer.adelete_thread(thread_id)
            await remover_work_dir(thread_id)
            session["thread_id"] = None
        return {"ok": True}

    @sio.on("input_text")
    async def handle_input(sid, data):
        session = anon_sessions.get(sid)
        if not session:
            observe_socket_event("input_text", "rejected")
            return
        if not isinstance(data, dict):
            observe_socket_event("input_text", "rejected")
            await sio.emit(
                "erro",
                {"mensagem": "Formato de mensagem inválido."},
                room=sid,
            )
            return

        running_task = session.get("task")
        if running_task and not running_task.done():
            observe_socket_event("input_text", "busy")
            await sio.emit(
                "erro",
                {"mensagem": "Aguarde a resposta atual terminar."},
                room=sid,
            )
            return

        user_message = str(data.get("input_data") or "").strip()
        arquivos = data.get("arquivos", [])
        token = session.get("token")
        chat_id = data.get("chat_id")

        if not user_message or len(user_message) > 20_000:
            observe_socket_event("input_text", "rejected")
            await sio.emit(
                "erro",
                {"mensagem": "Mensagem vazia ou muito longa."},
                room=sid,
            )
            return
        if not isinstance(arquivos, list) or len(arquivos) > 3:
            observe_socket_event("input_text", "rejected")
            await sio.emit(
                "erro",
                {"mensagem": "Envie no máximo 3 arquivos."},
                room=sid,
            )
            return
        allowed_extensions = ALLOWED_ATTACHMENT_EXTENSIONS
        for arquivo in arquivos:
            if (
                not isinstance(arquivo, dict)
                or not str(arquivo.get("filename", "")).lower().endswith(allowed_extensions)
                or not isinstance(arquivo.get("content"), str)
                or len(arquivo["content"]) > MAX_ATTACHMENT_BASE64_CHARS
            ):
                observe_socket_event("input_text", "rejected")
                await sio.emit(
                    "erro",
                    {"mensagem": "Arquivo inválido ou maior que 5 MB."},
                    room=sid,
                )
                return

        # ip capturado no connect
        client_ip = session.get("client_ip", "unknown")

        if not token:
            if session.get("thread_id") is None:
                session["thread_id"] = f"anon_{uuid.uuid4()}"
            chat_tab_id = session["thread_id"]
        else:
            chat_tab_id = chat_id

        task = asyncio.create_task(
            execute_system(
                app,
                sio,
                sid,
                user_message,
                arquivos,
                token,
                chat_tab_id,
                client_ip,
            )
        )
        session["task"] = task
        observe_socket_event("input_text", "accepted")
