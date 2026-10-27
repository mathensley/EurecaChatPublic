import os
import logging

from application.db.token_usage.token_usage_crud import get_daily_total_tokens

logger = logging.getLogger("rate_limiter")

DAILY_TOKEN_LIMIT_USER = int(os.getenv("DAILY_TOKEN_LIMIT_USER", "300000"))
DAILY_TOKEN_LIMIT_ANON = int(os.getenv("DAILY_TOKEN_LIMIT_ANON", "150000"))


async def check_rate_limit(db_pool, identifier: str, id_type: str) -> tuple[bool, int, int]:
    """
    Verifica se o identificador ainda está dentro do limite diário de tokens.

    Retorna uma tupla (dentro_do_limite, consumido_hoje, limite).
    """
    limit = DAILY_TOKEN_LIMIT_USER if id_type == "user" else DAILY_TOKEN_LIMIT_ANON

    async with db_pool.acquire() as conn:
        consumed = await get_daily_total_tokens(conn, identifier)

    within_limit = consumed < limit

    if not within_limit:
        logger.warning(
            "rate_limit_exceeded",
            extra={
                "identifier": identifier,
                "id_type": id_type,
                "consumed": consumed,
                "limit": limit,
            },
        )

    return within_limit, consumed, limit
