import asyncio
import logging


socket_logger = logging.getLogger("socket")


async def cleanup_old_token_usage(db_pool):
    """Deleta registros de token_usage com mais de 30 dias."""
    while True:
        await asyncio.sleep(60 * 60 * 24)  # roda 1x por dia
        try:
            async with db_pool.acquire() as conn:
                deleted = await conn.execute(
                    """
                    DELETE FROM token_usage
                    WHERE date < (NOW() AT TIME ZONE 'America/Recife')::DATE - INTERVAL '30 days'
                    """
                )
                socket_logger.info(
                    "token_usage_cleanup",
                    extra={"result": deleted},
                )
        except Exception as e:
            socket_logger.error(
                "token_usage_cleanup_error",
                extra={"error": str(e)},
            )
