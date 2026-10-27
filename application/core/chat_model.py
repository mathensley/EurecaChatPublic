import os
from typing import Any

from langchain_openai import ChatOpenAI


OPENAI_RESPONSES_MODELS = ("gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol", "gpt-6-luna", "gpt-6-sol")
DEFAULT_PROVIDER_URL = "https://api.deepinfra.com/v1/openai"


def _optional_env(name: str) -> str | None:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else None


def _is_provider_model(model: str) -> bool:
    """Para provedores em que os IDs usam namespace com "/", como openai/gpt-oss-20b."""
    return "/" in model


def _uses_responses_api(model: str) -> bool:
    return any(
        model == response_model or model.startswith(f"{response_model}-")
        for response_model in OPENAI_RESPONSES_MODELS
    )


def create_chat_model(model: str | None, *, temperature: float | None = None, **kwargs: Any) -> ChatOpenAI:
    if not model:
        raise ValueError("O modelo não foi configurado")

    model_kwargs: dict[str, Any] = {"model": model, **kwargs}
    if temperature is not None:
        model_kwargs["temperature"] = temperature

    if _is_provider_model(model):
        provider_url = _optional_env("PROVIDER_URL") or DEFAULT_PROVIDER_URL
        model_kwargs["base_url"] = provider_url
        model_kwargs["api_key"] = _optional_env("DEEPINFRA_API_TOKEN")
    elif _uses_responses_api(model):
        model_kwargs["use_responses_api"] = True

    return ChatOpenAI(**model_kwargs)
