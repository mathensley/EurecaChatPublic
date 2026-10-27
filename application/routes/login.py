from quart import Blueprint, request, jsonify, current_app

from ..core.utils.token_handler import get_info, parse_user_profile
from ..db.user.user_crud import get_user_or_create

bp = Blueprint("login", __name__)

@bp.route('/login_enter', methods=["GET"])
async def login_enter():
    try:
        token = request.headers.get("token-de-autenticacao")

        if not token:
            return jsonify({"error": "Token não fornecido!"}), 400
        
        user_info = await get_info(token)

        if not user_info:
            return jsonify({"error": "Falha ao obter perfil do usuário"}), 502
        
        nome, cpf, matricula, _ = parse_user_profile(user_info)

        if not cpf:
            return jsonify({"error": "Token inválido ou erro na requisição"}), 403
        
        async with current_app.db_pool.acquire() as conn:
            await get_user_or_create(conn, nome, cpf, matricula)

        return jsonify(user_info), 200
    
    except Exception as e:
        current_app.logger.exception(f"Erro interno em /login_enter, {str(e)}")
        return jsonify({"error": "Erro interno no login"}), 503
