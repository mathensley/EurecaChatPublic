from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


def create_postgres_pool(
    db_uri: str,
    *,
    min_size: int = 1,
    max_size: int = 2,
) -> AsyncConnectionPool:
    """Cria o pool resiliente usado pelo checkpointer do LangGraph."""
    return AsyncConnectionPool(
        conninfo=db_uri,
        min_size=min_size,
        max_size=max_size,
        open=False,
        check=AsyncConnectionPool.check_connection,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
            "application_name": "eureca-checkpointer",
        },
    )


def get_postgres_saver(pool: AsyncConnectionPool) -> AsyncPostgresSaver:
    """Cria um saver que obtém uma conexão válida do pool a cada operação."""
    return AsyncPostgresSaver(pool)
