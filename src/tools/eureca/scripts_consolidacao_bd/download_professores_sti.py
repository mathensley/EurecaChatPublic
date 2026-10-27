import json
import logging
import sqlite3
import time

import requests
from requests.exceptions import ChunkedEncodingError, RequestException

from application.config import URL_SIG


# ============================================================
# CONFIGURAÇÃO
# ============================================================

URL_PROFESSORES = f"{URL_SIG.rstrip('/')}/professores"

TAMANHO_PAGINA = 100
MAX_RETRIES = 5
MAX_BACKOFF = 32
TIMEOUT = 300

DB_PROFESSORES = "professores_ufcg.sqlite"
TABELA_PROFESSORES = "professores_ufcg"


logging.basicConfig(
    filename="log_professores_sti_ufcg.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8",
)


# ============================================================
# API
# ============================================================

def buscar_pagina(pagina):
    """Busca uma página de professores, repetindo a chamada em caso de falha."""

    for tentativa in range(MAX_RETRIES):
        try:
            response = requests.get(
                URL_PROFESSORES,
                params={
                    "pagina": pagina,
                    "tamanho": TAMANHO_PAGINA,
                },
                timeout=TIMEOUT,
            )

            if response.status_code == 200:
                dados = response.json()

                if isinstance(dados, list):
                    return dados

                logging.warning(
                    f"Resposta inesperada | página={pagina} | "
                    f"tipo={type(dados).__name__}"
                )
            else:
                logging.warning(
                    f"Status {response.status_code} | página={pagina} | "
                    f"tentativa={tentativa + 1}/{MAX_RETRIES}"
                )

        except (ChunkedEncodingError, RequestException, ValueError) as erro:
            logging.warning(
                f"Erro | página={pagina} | "
                f"tentativa={tentativa + 1}/{MAX_RETRIES} | {erro}"
            )

        time.sleep(min(2 ** tentativa, MAX_BACKOFF))

    logging.error(f"Todas as tentativas falharam | página={pagina}")
    return None


# ============================================================
# BANCO DE PROFESSORES
# ============================================================

def criar_banco():
    """Cria o banco e a tabela de professores, caso ainda não existam."""

    with sqlite3.connect(DB_PROFESSORES) as conn:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABELA_PROFESSORES} (
                matricula_do_docente INTEGER PRIMARY KEY,
                nome TEXT,
                codigo_do_setor INTEGER,
                campus INTEGER,
                status TEXT,
                titulacao TEXT
            )
            """
        )
        conn.commit()


def inserir_professores(professores):
    """Insere ou atualiza no SQLite os professores retornados pela API."""

    if not professores:
        return 0

    valores = [
        (
            professor.get("matricula_do_docente"),
            professor.get("nome"),
            professor.get("codigo_do_setor"),
            professor.get("campus"),
            professor.get("status"),
            json.dumps(professor.get("titulacao"), ensure_ascii=False),
        )
        for professor in professores
    ]

    with sqlite3.connect(DB_PROFESSORES, timeout=30) as conn:
        conn.executemany(
            f"""
            INSERT OR REPLACE INTO {TABELA_PROFESSORES} (
                matricula_do_docente,
                nome,
                codigo_do_setor,
                campus,
                status,
                titulacao
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            valores,
        )
        conn.commit()

    return len(valores)


# ============================================================
# PRINCIPAL
# ============================================================

def download_professores():
    print("============== DOWNLOAD DE PROFESSORES ==============")
    criar_banco()

    pagina = 1
    total = 0

    while True:
        professores = buscar_pagina(pagina)

        if professores is None:
            logging.error(f"Download interrompido na página {pagina}")
            print(f"Erro ao baixar a página {pagina}. Download interrompido.")
            break

        if not professores:
            logging.info(f"Página {pagina} vazia. Download finalizado.")
            break

        quantidade = inserir_professores(professores)
        total += quantidade

        logging.info(
            f"Página {pagina} | {quantidade} professores processados | "
            f"total={total}"
        )
        print(f"Página {pagina} | {quantidade} professores | Total: {total}")

        if len(professores) < TAMANHO_PAGINA:
            break

        pagina += 1

    print(f"\nDownload concluído. {total} professores processados.")


if __name__ == "__main__":
    download_professores()
