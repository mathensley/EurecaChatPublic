import json
import logging
import os
from uuid import UUID

import httpx
from quart import Blueprint, current_app, jsonify, request

from application import http_client
from application.core.utils.token_handler import (
    INVALID_TOKEN_STATUS_CODES,
    fetch_profile,
    get_info,
    parse_user_profile,
)
from application.db.chat_tab.chat_crud import (
    delete_chat_tab,
    get_chat_messages_by_chat_id,
    get_chat_tab_for_user,
    get_chat_tabs_by_cpf,
    update_chat_title,
)
from application.db.user.user_crud import get_user_or_create
from src.tools.eureca.eureca_bash.workdir import remover_work_dir


bp = Blueprint("api", __name__, url_prefix="/api")
logger = logging.getLogger("http")
TOKEN_URL = "https://eureca.sti.ufcg.edu.br/as-sig/tokens?horas-duracao=24"
SESSION_COOKIE_NAME = "eureca_token"


def _error(message: str, status: int):
    return jsonify({"error": message}), status


def _request_token() -> tuple[str | None, bool]:
    """Retorna o token e informa se ele veio do cookie de sessão."""
    value = request.headers.get("Authorization", "")
    scheme, _, token = value.partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        return token.strip(), False
    cookie_token = request.cookies.get(SESSION_COOKIE_NAME)
    return cookie_token, cookie_token is not None


def _bearer_token() -> str | None:
    token, _ = _request_token()
    return token


def _cookie_secure() -> bool:
    return os.getenv("COOKIE_SECURE", "false").lower() == "true"


def _disable_cache(response):
    response.headers["Cache-Control"] = "no-store"
    return response


def _clear_session_cookie(response):
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=_cookie_secure(),
        samesite="Lax",
    )
    return response


async def _identity():
    token = _bearer_token()
    if not token:
        return None

    profile = await get_info(token)
    external_id = profile.get("id") if profile else None
    if not external_id:
        return None
    return token, profile, str(external_id)


def _uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except (TypeError, ValueError):
        return None


def _attachment_names(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        parsed = value

    if isinstance(parsed, str):
        parsed = [parsed]
    if not isinstance(parsed, list):
        return []
    return [item.strip() for item in parsed if isinstance(item, str) and item.strip()]


@bp.get("/health/live")
async def live():
    return jsonify({
        "status": "ok",
        "service": "eureca-ai",
        "version": os.getenv("APP_VERSION", "local"),
    })


@bp.get("/health/ready")
async def ready():
    if (
        current_app.system is None
        or getattr(current_app, "db_pool", None) is None
        or getattr(current_app, "checkpointer_pool", None) is None
    ):
        return _error("Aplicação ainda está inicializando", 503)

    try:
        async with current_app.db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        async with current_app.checkpointer_pool.connection(timeout=5) as conn:
            await conn.execute("SELECT 1")
    except Exception:
        logger.exception("readiness_check_failed")
        return _error("Banco de dados indisponível", 503)

    return jsonify({
        "status": "ready",
        "service": "eureca-ai",
        "version": os.getenv("APP_VERSION", "local"),
        "components": {
            "database": "ok",
            "checkpointer": "ok",
            "agent": "ok",
        },
    })


@bp.post("/auth/login")
async def login():
    data = await request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    if not username or not password:
        return _error("Usuário e senha são obrigatórios", 400)

    client = http_client.async_client
    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=30.0)

    try:
        response = await client.post(
            TOKEN_URL,
            json={"credentials": {"username": username, "password": password}},
            headers={"Accept": "application/json"},
        )
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        logger.exception("external_login_failed")
        return _error("Serviço de autenticação temporariamente indisponível", 502)
    finally:
        if owns_client:
            await client.aclose()

    token = payload.get("token") if isinstance(payload, dict) else None
    if response.status_code >= 400 or not token:
        return _error("Usuário ou senha inválidos", 401)

    profile = await get_info(token)
    external_id = profile.get("id") if profile else None
    if not external_id:
        return _error("Não foi possível obter o perfil acadêmico", 502)

    async with current_app.db_pool.acquire() as conn:
        nome, cpf, matricula, _ = parse_user_profile(profile)
        await get_user_or_create(conn, nome, cpf, matricula)

    result = _disable_cache(jsonify({"data": {"user": profile}}))
    result.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=24 * 60 * 60,
        httponly=True,
        secure=_cookie_secure(),
        samesite="Lax",
        path="/",
    )
    return result


@bp.post("/auth/logout")
async def logout():
    result = _disable_cache(jsonify({"data": None}))
    return _clear_session_cookie(result)


@bp.get("/auth/me")
async def me():
    token, token_from_cookie = _request_token()
    if not token:
        return _disable_cache(jsonify({"data": None}))

    profile, status_code = await fetch_profile(token)
    external_id = profile.get("id") if profile else None
    if external_id:
        return _disable_cache(jsonify({"data": profile}))

    if status_code in INVALID_TOKEN_STATUS_CODES:
        result = jsonify({"data": None, "error": "Sessão inválida ou expirada"})
        result.status_code = 401
        _disable_cache(result)
        if token_from_cookie:
            _clear_session_cookie(result)
        return result

    result = jsonify({"error": "Serviço de autenticação temporariamente indisponível"})
    result.status_code = 502
    return _disable_cache(result)


@bp.get("/conversations")
async def conversations():
    identity = await _identity()
    if not identity:
        return _error("Sessão inválida ou expirada", 401)
    _, _, external_id = identity

    async with current_app.db_pool.acquire() as conn:
        tabs = await get_chat_tabs_by_cpf(conn, external_id)

    result = [
        {
            "id": str(tab["id"]),
            "title": tab["title"] or "Novo Chat",
            "createdAt": tab["created_at"].isoformat(),
            "updatedAt": tab["updated_at"].isoformat(),
        }
        for tab in tabs
    ]
    return jsonify({"data": result})


@bp.get("/conversations/<conversation_id>/messages")
async def conversation_messages(conversation_id: str):
    identity = await _identity()
    chat_id = _uuid(conversation_id)
    if not identity:
        return _error("Sessão inválida ou expirada", 401)
    if not chat_id:
        return _error("Identificador de conversa inválido", 400)
    _, _, external_id = identity

    async with current_app.db_pool.acquire() as conn:
        owned = await get_chat_tab_for_user(conn, chat_id, external_id)
        if not owned:
            return _error("Conversa não encontrada", 404)
        rows = await get_chat_messages_by_chat_id(conn, chat_id)

    messages = [
        {
            "id": str(row["id"]),
            "role": "user" if row["role"] == "human_message" else "assistant",
            "content": row["content"],
            "createdAt": row["created_at"].isoformat(),
            "attachments": _attachment_names(row["filename"]),
        }
        for row in rows
    ]
    return jsonify({"data": messages})


@bp.patch("/conversations/<conversation_id>")
async def rename_conversation(conversation_id: str):
    identity = await _identity()
    chat_id = _uuid(conversation_id)
    data = await request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()[:120]
    if not identity:
        return _error("Sessão inválida ou expirada", 401)
    if not chat_id or not title:
        return _error("Conversa ou título inválido", 400)
    _, _, external_id = identity

    async with current_app.db_pool.acquire() as conn:
        if not await get_chat_tab_for_user(conn, chat_id, external_id):
            return _error("Conversa não encontrada", 404)
        await update_chat_title(conn, chat_id, title)
    return jsonify({"data": {"id": conversation_id, "title": title}})


@bp.delete("/conversations/<conversation_id>")
async def remove_conversation(conversation_id: str):
    identity = await _identity()
    chat_id = _uuid(conversation_id)
    if not identity:
        return _error("Sessão inválida ou expirada", 401)
    if not chat_id:
        return _error("Identificador de conversa inválido", 400)
    _, _, external_id = identity

    async with current_app.db_pool.acquire() as conn:
        if not await get_chat_tab_for_user(conn, chat_id, external_id):
            return _error("Conversa não encontrada", 404)
        await delete_chat_tab(conn, chat_id)

    await current_app.checkpointer.adelete_thread(str(chat_id))
    await remover_work_dir(str(chat_id))
    return jsonify({"data": None})
