import asyncio
import os

from application.db.saver import create_postgres_pool, get_postgres_saver

def get_db_uri() -> str:
    user = os.environ["POSTGRES_USER"]
    password = os.environ["POSTGRES_PASSWORD"]
    host = os.environ["POSTGRES_HOST"]
    port = os.environ["POSTGRES_PORT"]
    db = os.environ["POSTGRES_DB"]
    return f"postgresql://{user}:{password}@{host}:{port}/{db}?sslmode=disable"

async def setup_checkpointer(db_uri: str) -> None:
    pool = create_postgres_pool(db_uri, min_size=1, max_size=1)
    await pool.open(wait=True)
    try:
        checkpointer = get_postgres_saver(pool)
        await checkpointer.setup()
    finally:
        await pool.close()

def main() -> None:
    asyncio.run(setup_checkpointer(get_db_uri()))

if __name__ == "__main__":
    main()
