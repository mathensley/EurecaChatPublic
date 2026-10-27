import logging
from datetime import datetime
from uuid import UUID

from quart import Blueprint, jsonify, request

from application.services.feedback import PhoenixFeedbackError, save_feedback


bp = Blueprint("feedback", __name__, url_prefix="/api")
logger = logging.getLogger("http")


def _valid_text(value: object, *, max_length: int, allow_empty: bool = False) -> bool:
    return isinstance(value, str) and len(value) <= max_length and (allow_empty or bool(value.strip()))


@bp.post("/feedback")
async def create_feedback():
    payload = await request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Feedback inválido"}), 400

    try:
        UUID(payload.get("feedbackId"))
    except (TypeError, ValueError, AttributeError):
        return jsonify({"error": "Identificador de feedback inválido"}), 400

    try:
        created_at = datetime.fromisoformat(payload.get("createdAt"))
        if created_at.tzinfo is None:
            raise ValueError("Fuso horário obrigatório")
    except (TypeError, ValueError, AttributeError):
        return jsonify({"error": "Data do feedback inválida"}), 400

    if (
        not _valid_text(payload.get("question"), max_length=20_000, allow_empty=True)
        or not _valid_text(payload.get("answer"), max_length=200_000)
        or not _valid_text(payload.get("feedback"), max_length=4_000)
        or payload.get("choice") not in ("positive", "negative")
        or payload.get("userType") not in ("user", "anon")
        or (payload.get("conversationId") is not None and not _valid_text(payload["conversationId"], max_length=100))
        or (payload.get("userId") is not None and (
            isinstance(payload["userId"], bool)
            or not isinstance(payload["userId"], (str, int))
            or not _valid_text(str(payload["userId"]), max_length=100)
        ))
    ):
        return jsonify({"error": "Dados de feedback inválidos"}), 400

    try:
        await save_feedback(payload)
    except PhoenixFeedbackError:
        logger.exception("phoenix_feedback_failed")
        return jsonify({"error": "Não foi possível salvar o feedback"}), 502

    return jsonify({"data": None}), 201
