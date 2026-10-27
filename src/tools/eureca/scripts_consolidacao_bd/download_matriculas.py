import logging
import sqlite3
import threading
import time

import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.exceptions import ChunkedEncodingError, RequestException

from application.config import URL_SIG


# ============================================================
# CONFIGURAÇÃO
# ============================================================

URL_HISTORICO = (
    f"{URL_SIG}/matriculas/estudante-anonimizado"
)

MAX_THREADS = 2
MAX_RETRIES = 5
MAX_BACKOFF = 32

DB_ESTUDANTES = "estudantes_ufcg.sqlite"
DB_MATRICULAS = "matriculas_ufcg.sqlite"

TABELA_ESTUDANTES = "estudantes_ufcg"
TABELA_MATRICULAS = "matriculas_ufcg"

db_lock = threading.Lock()


logging.basicConfig(
    filename="log_matriculas_ufcg.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8",
)


# ============================================================
# BANCO DE ESTUDANTES
# ============================================================

def buscar_matriculas_estudantes():
    """
    Busca todas as matrículas existentes no banco de estudantes.
    """

    conn = sqlite3.connect(DB_ESTUDANTES)

    try:
        cursor = conn.execute(
            f"""
            SELECT matricula_do_estudante
            FROM {TABELA_ESTUDANTES}
            WHERE matricula_do_estudante IS NOT NULL
            """
        )

        matriculas = [
            str(row[0])
            for row in cursor.fetchall()
        ]

    finally:
        conn.close()

    # Remove duplicadas
    return list(dict.fromkeys(matriculas))


# ============================================================
# API
# ============================================================

def buscar_historico(matricula):
    """
    Busca o histórico completo de um estudante.
    """

    for tentativa in range(MAX_RETRIES):

        try:
            response = requests.get(
                URL_HISTORICO,
                params={
                    "estudante": matricula
                },
                timeout=300,
            )

            if response.status_code == 200:
                dados = response.json()

                if isinstance(dados, list):
                    logging.info(
                        f"Estudante {matricula} | "
                        f"{len(dados)} matrículas encontradas"
                    )

                    return dados

                logging.warning(
                    f"Resposta inesperada para estudante "
                    f"{matricula}: {type(dados)}"
                )

                return []

            logging.warning(
                f"Estudante {matricula} | "
                f"Status {response.status_code} | "
                f"Tentativa {tentativa + 1}/{MAX_RETRIES}"
            )

        except (
            ChunkedEncodingError,
            RequestException,
            ValueError,
        ) as e:

            logging.warning(
                f"Estudante {matricula} | "
                f"Erro tentativa {tentativa + 1}/"
                f"{MAX_RETRIES}: {e}"
            )

        time.sleep(
            min(2 ** tentativa, MAX_BACKOFF)
        )

    logging.error(
        f"Todas as tentativas falharam | "
        f"estudante={matricula}"
    )

    return []

# ============================================================
# BANCO DE MATRÍCULAS
# ============================================================

def criar_banco():
    """
    Cria o banco de matrículas.
    """

    conn = sqlite3.connect(DB_MATRICULAS)

    try:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABELA_MATRICULAS} (
                matricula_do_estudante TEXT,
                codigo_da_disciplina INTEGER,
                nome_da_disciplina TEXT,
                periodo TEXT,
                turma INTEGER,
                status TEXT,
                tipo TEXT,
                media_final REAL,
                dispensas TEXT,
                matricula_do_professor TEXT
            )
            """
        )

        conn.commit()

    finally:
        conn.close()


def inserir_matriculas(matriculas):
    """
    Insere as matrículas retornadas pela API.
    """

    if not matriculas:
        return 0

    valores = []

    for matricula in matriculas:

        valores.append(
            (
                matricula.get("matricula_do_estudante"),
                matricula.get("codigo_da_disciplina"),
                matricula.get("nome_da_disciplina"),
                matricula.get("periodo"),
                matricula.get("turma"),
                matricula.get("status"),
                matricula.get("tipo"),
                matricula.get("media_final"),
                matricula.get("dispensas"),
                matricula.get("matricula_do_docente")
            )
        )

    with db_lock:

        conn = sqlite3.connect(
            DB_MATRICULAS,
            timeout=30,
        )

        try:

            conn.executemany(
                f"""
                INSERT INTO {TABELA_MATRICULAS} (
                    matricula_do_estudante,
                    codigo_da_disciplina,
                    nome_da_disciplina,
                    periodo,
                    turma,
                    status,
                    tipo,
                    media_final,
                    dispensas,
                    matricula_do_professor
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                valores,
            )

            conn.commit()

        except sqlite3.Error as e:

            conn.rollback()

            logging.error(
                f"Erro ao inserir matrículas: {e}"
            )

            return 0

        finally:
            conn.close()

    return len(valores)


# ============================================================
# PROCESSAR ESTUDANTE
# ============================================================

def processar_estudante(matricula):
    """
    Busca o histórico de um estudante e salva suas matrículas.
    """

    historico = buscar_historico(matricula)

    if not historico:
        logging.info(
            f"Estudante {matricula} | "
            f"sem histórico"
        )

        return matricula, 0

    total = inserir_matriculas(historico)

    logging.info(
        f"Estudante {matricula} | "
        f"{total} matrículas inseridas"
    )

    return matricula, total


# ============================================================
# PRINCIPAL
# ============================================================

def download_matriculas():

    print(
        "============== DOWNLOAD DE MATRÍCULAS =============="
    )

    criar_banco()

    matriculas = buscar_matriculas_estudantes()

    print(
        f"{len(matriculas)} estudantes encontrados"
    )

    total = 0

    with ThreadPoolExecutor(
        max_workers=MAX_THREADS
    ) as executor:

        futures = {
            executor.submit(
                processar_estudante,
                matricula,
            ): matricula
            for matricula in matriculas
        }

        for future in as_completed(futures):

            matricula = futures[future]

            try:

                _, quantidade = future.result()

                total += quantidade

                print(
                    f"Estudante {matricula} | "
                    f"{quantidade} matrículas"
                )

            except Exception as e:

                logging.error(
                    f"Erro estudante {matricula}: {e}"
                )

                print(
                    f"Erro estudante {matricula}: {e}"
                )

    print(
        f"\nTotal de matrículas inseridas: {total}"
    )


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == "__main__":
    download_matriculas()