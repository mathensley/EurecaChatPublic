import os, logging
from pathlib import Path

import psycopg


MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def get_db_uri() -> str:
    user = os.environ["POSTGRES_USER"]
    password = os.environ["POSTGRES_PASSWORD"]
    host = os.environ["POSTGRES_HOST"]
    port = os.environ["POSTGRES_PORT"]
    db = os.environ["POSTGRES_DB"]
    return f"postgresql://{user}:{password}@{host}:{port}/{db}?sslmode=disable"


def ensure_schema_migrations_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    conn.commit()


def get_applied_versions(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM schema_migrations")
        rows = cur.fetchall()
    return {row[0] for row in rows}


def apply_migration(conn, migration_path: Path) -> None:
    sql = migration_path.read_text(encoding="utf-8")
    version = migration_path.name

    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)",
                (version,),
            )


def main() -> None:
    if not MIGRATIONS_DIR.exists():
        print("Diretorio de migrations nao encontrado. Pulando.")
        return

    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        print("Nenhuma migration encontrada. Pulando.")
        return

    db_uri = get_db_uri()

    with psycopg.connect(db_uri) as conn:
        ensure_schema_migrations_table(conn)
        applied_versions = get_applied_versions(conn)

        for migration_path in migration_files:
            if migration_path.name in applied_versions:
                print(f"Migration ja aplicada: {migration_path.name}")
                continue

            print(f"Aplicando migration: {migration_path.name}")
            apply_migration(conn, migration_path)

    print("Migrations finalizadas com sucesso.")


if __name__ == "__main__":
    main()