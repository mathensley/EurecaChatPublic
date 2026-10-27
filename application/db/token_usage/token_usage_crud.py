"""CRUD operations for the token_usage table."""

import logging

logger = logging.getLogger("token_usage")

async def record_token_usage(conn, identifier: str, id_type: str, input_tokens: int, output_tokens: int, total_tokens: int):
    await conn.execute("""
        INSERT INTO token_usage (identifier, id_type, input_tokens, output_tokens, total_tokens, date, last_updated)
        VALUES ($1, $2, $3, $4, $5, (NOW() AT TIME ZONE 'America/Recife')::DATE, CURRENT_TIMESTAMP)
        ON CONFLICT (identifier, date)
        DO UPDATE SET
            input_tokens  = token_usage.input_tokens  + EXCLUDED.input_tokens,
            output_tokens = token_usage.output_tokens + EXCLUDED.output_tokens,
            total_tokens  = token_usage.total_tokens  + EXCLUDED.total_tokens,
            last_updated  = CURRENT_TIMESTAMP
    """, identifier, id_type, input_tokens, output_tokens, total_tokens)


async def get_daily_total_tokens(conn, identifier: str) -> int:
    row = await conn.fetchrow(
        """
        SELECT COALESCE(total_tokens, 0) AS daily_total
        FROM token_usage
        WHERE identifier = $1
          AND date = (NOW() AT TIME ZONE 'America/Recife')::DATE
        """,
        identifier,
    )
    return int(row["daily_total"]) if row else 0