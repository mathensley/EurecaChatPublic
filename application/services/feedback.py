import os
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from application import http_client


class PhoenixFeedbackError(Exception):
    pass


async def save_feedback(payload: dict) -> None:
    api_key = os.getenv("PHOENIX_API_KEY", "").strip()
    if not api_key or api_key == "API_KEY":
        raise PhoenixFeedbackError("PHOENIX_API_KEY não configurada")

    client = http_client.async_client
    if client is None:
        raise PhoenixFeedbackError("Cliente HTTP não inicializado")

    base_url = os.getenv("PHOENIX_ENDPOINT", "http://phoenix:6006").rstrip("/")
    dataset_name = "Chat Feedbacks"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        datasets_response = await client.get(
            f"{base_url}/v1/datasets",
            params={"name": dataset_name, "limit": 2},
            headers=headers,
        )
        datasets_response.raise_for_status()
        datasets = datasets_response.json().get("data")
        if not isinstance(datasets, list):
            raise PhoenixFeedbackError("Resposta inválida ao consultar datasets no Phoenix")
        dataset = next((item for item in datasets if item.get("name") == dataset_name), None)
        if dataset is None:
            raise PhoenixFeedbackError(f'Dataset "{dataset_name}" não encontrado no Phoenix')

        metadata = {
            "source": "chat_feedback",
            "rating": payload["choice"],
            "comment": payload["feedback"],
            "feedback_id": payload["feedbackId"],
            "created_at": datetime.fromisoformat(payload["createdAt"])
            .astimezone(ZoneInfo("America/Sao_Paulo"))
            .isoformat(timespec="milliseconds"),
            "conversation_id": payload.get("conversationId"),
            "user_type": payload["userType"],
            "user_id": str(payload["userId"]) if payload.get("userId") is not None else None,
        }
        upload_response = await client.post(
            f"{base_url}/v1/datasets/upload",
            params={"sync": "true"},
            headers=headers,
            json={
                "action": "append",
                "name": dataset_name,
                "inputs": [{"question": payload["question"]}],
                "outputs": [{"observed_answer": payload["answer"]}],
                "metadata": [metadata],
                "example_ids": [payload["feedbackId"]],
            },
        )
        upload_response.raise_for_status()
        uploaded = upload_response.json().get("data")
        if not isinstance(uploaded, dict) or uploaded.get("dataset_id") != dataset.get("id"):
            raise PhoenixFeedbackError("Phoenix não confirmou a gravação no dataset esperado")
    except (httpx.HTTPError, ValueError, TypeError, AttributeError) as exc:
        raise PhoenixFeedbackError("Falha ao comunicar com o Phoenix") from exc
