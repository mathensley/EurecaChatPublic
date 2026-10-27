import json, logging
from datetime import timezone
from uuid import UUID
from quart import Blueprint, request, jsonify, current_app

from application.config import title_model
from application.db.chat_tab.chat_crud import (
    delete_chat_tab,
    get_chat_messages_by_chat_id,
    get_chat_tab_for_user,
    get_chat_tabs_by_cpf,
)

from ..core.utils.title import generate_chat_title
from ..core.utils.token_handler import get_info
from src.tools.eureca.eureca_bash.workdir import remover_work_dir

bp = Blueprint("chat", __name__)


def _request_token(data):
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    if data and data.get("token"):
        return data["token"]
    token_cookie = request.cookies.get("eureca_token")
    if token_cookie:
        return token_cookie
    try:
        profile = json.loads(request.cookies.get("profile", "{}"))
        return profile.get("token")
    except (TypeError, json.JSONDecodeError):
        return None


async def _owner(data, chat_id):
    token = _request_token(data)
    profile = await get_info(token) if token else None
    external_id = profile.get("id") if profile else None
    try:
        parsed_id = UUID(str(chat_id))
    except (TypeError, ValueError):
        return None, None
    if not external_id:
        return None, parsed_id
    async with current_app.db_pool.acquire() as conn:
        owned = await get_chat_tab_for_user(conn, parsed_id, str(external_id))
    return owned, parsed_id

@bp.route('/resumir', methods=["POST"])
async def resumir():
    data = await request.get_json()

    if not data or 'texto' not in data:
        return jsonify({"erro": "Campo 'texto' é obrigatório"}), 400

    texto = data['texto']

    try:
        resumo = await generate_chat_title(text=texto, llm=title_model)
        return jsonify({"resumo": resumo['titulo']}), 200
    except Exception as e:
        logging.error(e)
        return jsonify({"erro": f"Erro ao gerar resumo: {str(e)}"}), 500

@bp.route('/update_title', methods=["POST"])
async def update_title():
    data = await request.get_json()
    chat_id = data.get('chat_id')
    title = data.get('title')

    if not chat_id or not title:
        return jsonify({"error": "Faltou chat_id ou title"}), 400

    owned, parsed_id = await _owner(data, chat_id)
    if not owned:
        return jsonify({"error": "Chat não encontrado"}), 404

    async with current_app.db_pool.acquire() as conn:
        await conn.execute("UPDATE chat_tabs SET title=$1 WHERE id=$2", title[:120], parsed_id)

    return jsonify({"ok": True})

@bp.route('/delete_chat', methods=["POST"])
async def delete_chat():
    data = await request.get_json()
    chat_id = data.get("chat_id")

    if not chat_id:
        return jsonify({"error": "chat_id não fornecido"}), 400

    owned, parsed_id = await _owner(data, chat_id)
    if not owned:
        return jsonify({"error": "Chat não encontrado"}), 404
    
    async with current_app.db_pool.acquire() as conn:
        await delete_chat_tab(conn, parsed_id)
    
    await current_app.checkpointer.adelete_thread(str(parsed_id)) # também deleta os checkpoints do PostgresSaver
    await remover_work_dir(str(parsed_id))

    return jsonify({"msg": f"Chat {chat_id} deletado"}), 200

@bp.route("/get_chat", methods=["POST"])
async def get_chat():
    data = await request.json
    chat_id = data.get("chat_id")
    token = data.get("token")

    if not token:
        return jsonify({"data": []})

    try:
        parsed_id = UUID(str(chat_id))
    except (TypeError, ValueError):
        return jsonify({"data": []})
    
    user_info = await get_info(token)
    cpf = str(user_info.get("id")) if user_info and user_info.get("id") else None

    if not cpf:
        return jsonify({"data": []})
    
    async with current_app.db_pool.acquire() as conn:
        # garantir que o chat pertence ao usuário
        rows = await conn.fetch("""
            SELECT ct.id
            FROM chat_tabs ct
            JOIN users u ON ct.user_id = u.id
            WHERE ct.id = $1 AND u.cpf = $2
        """, parsed_id, cpf)

        if not rows:
            return jsonify({"data": []})

        messages = await get_chat_messages_by_chat_id(conn, parsed_id)
        
    result = []
    for msg in messages:
        timestamp = msg["created_at"].isoformat()
        if msg["role"] == "human_message":
            try:
                filenames = json.loads(msg["filename"]) if msg["filename"] else []
            except json.JSONDecodeError:
                filenames = []
            result.append({"human_message": msg["content"], "timestamp": timestamp, "arquivos": [{"name": nome} for nome in filenames]})
        elif msg["role"] == "ai_message":
            result.append({"ai_message": msg["content"], "timestamp": timestamp})
    return jsonify({"data": result})

@bp.route("/get_historico", methods=["POST"])
async def get_historico():
    data = await request.get_json()
    token = data.get("token")

    if not token:
        return jsonify({"error": "Token não fornecido!"}), 400

    user_info = await get_info(token)
    cpf = str(user_info.get("id")) if user_info and user_info.get("id") else None

    if not cpf:
        return jsonify({"error": "Token inválido ou erro na requisição"}), 403
    
    async with current_app.db_pool.acquire() as conn:
        tabs = await get_chat_tabs_by_cpf(conn, cpf)

    if not tabs:
        return jsonify([])
    
    result = [
        {
            "chat_id": str(tab["id"]), 
            "title": tab["title"],
            "updated_at": (
                tab["updated_at"]
                .astimezone(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
                if tab["updated_at"] else None
            )
        }
        for tab in tabs
    ]
    return jsonify(result)
