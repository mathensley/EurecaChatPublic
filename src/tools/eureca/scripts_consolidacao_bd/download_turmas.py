import logging
import sqlite3
import time

import requests
from requests.exceptions import ChunkedEncodingError, RequestException

from application.config import URL_SIG


# ============================================================
# CONFIGURAÇÃO
# ============================================================

URL_TURMAS = f"{URL_SIG.rstrip('/')}/turmas"

TAMANHO_PAGINA = 100
MAX_RETRIES = 5
MAX_BACKOFF = 32
TIMEOUT = 300

DB_TURMAS = "turmas_ufcg.sqlite"
TABELA_TURMAS = "turmas_ufcg"


logging.basicConfig(
    filename="log_turmas_ufcg.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8",
)


# ============================================================
# API
# ============================================================

def buscar_pagina(pagina):
    """Busca uma página de turmas, com tentativas em caso de falha."""

    for tentativa in range(MAX_RETRIES):
        try:
            response = requests.get(
                URL_TURMAS,
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
# BANCO DE TURMAS
# ============================================================

def criar_banco():
    """Cria o banco e a tabela de turmas, caso ainda não existam."""

    with sqlite3.connect(DB_TURMAS) as conn:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABELA_TURMAS} (
                turma TEXT,
                codigo_da_disciplina INTEGER,
                periodo TEXT,
                numero_de_notas INTEGER,
                quantidade_de_creditos INTEGER,
                carga_horaria INTEGER,
                tipo TEXT,
                id_docente TEXT,
                nome_do_professor TEXT,
                PRIMARY KEY (codigo_da_disciplina, turma, periodo)
            )
            """
        )
        conn.commit()


def _nome_do_professor(turma):
    """Aceita as variações do nome do docente usadas nas respostas da API."""

    return (
        turma.get("nome_do_docente")
        or turma.get("nome_do_docuente")
        or turma.get("nome_docente")
    )


def inserir_turmas(turmas):
    """Insere ou atualiza no SQLite as turmas retornadas pela API."""

    if not turmas:
        return 0

    valores = [
        (
            turma.get("turma"),
            turma.get("codigo_da_disciplina"),
            turma.get("periodo"),
            turma.get("numero_de_notas"),
            turma.get("quantidade_de_creditos"),
            turma.get("carga_horaria"),
            turma.get("tipo"),
            turma.get("id_docente"),
            _nome_do_professor(turma),
        )
        for turma in turmas
    ]

    with sqlite3.connect(DB_TURMAS, timeout=30) as conn:
        conn.executemany(
            f"""
            INSERT OR REPLACE INTO {TABELA_TURMAS} (
                turma,
                codigo_da_disciplina,
                periodo,
                numero_de_notas,
                quantidade_de_creditos,
                carga_horaria,
                tipo,
                id_docente,
                nome_do_professor
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            valores,
        )
        conn.commit()

    return len(valores)


# ============================================================
# PRINCIPAL
# ============================================================

def download_turmas():
    print("============== DOWNLOAD DE TURMAS ==============")
    criar_banco()

    pagina = 1
    total = 0

    while True:
        turmas = buscar_pagina(pagina)

        if turmas is None:
            logging.error(f"Download interrompido na página {pagina}")
            print(f"Erro ao baixar a página {pagina}. Download interrompido.")
            break

        if not turmas:
            logging.info(
                f"API retornou página vazia | página={pagina} | total={total}"
            )
            print(
                f"Página {pagina} vazia (API retornou lista vazia). "
                f"Total baixado: {total}."
            )
            break

        quantidade = inserir_turmas(turmas)
        total += quantidade

        logging.info(
            f"Página {pagina} | {quantidade} turmas processadas | total={total}"
        )
        print(f"Página {pagina} | {quantidade} turmas | Total: {total}")

        if len(turmas) < TAMANHO_PAGINA:
            break

        pagina += 1

    print(f"\nDownload concluído. {total} turmas processadas.")


if __name__ == "__main__":
    download_turmas()
