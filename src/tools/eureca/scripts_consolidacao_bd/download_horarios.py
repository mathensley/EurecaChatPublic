import logging
import sqlite3
import time

import requests
from requests.exceptions import ChunkedEncodingError, RequestException

from application.config import URL_SIG


# ============================================================
# CONFIGURAÇÃO
# ============================================================

URL_HORARIOS = f"{URL_SIG.rstrip('/')}/horarios"

TAMANHO_PAGINA = 100
MAX_RETRIES = 5
MAX_BACKOFF = 32
TIMEOUT = 300

DB_HORARIOS = "horarios_ufcg.sqlite"
TABELA_HORARIOS = "horarios_ufcg"


logging.basicConfig(
    filename="log_horarios_ufcg.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8",
)


# ============================================================
# API
# ============================================================

def buscar_pagina(pagina):
    """Busca uma página de horários, repetindo a chamada em caso de falha."""

    for tentativa in range(MAX_RETRIES):
        try:
            response = requests.get(
                URL_HORARIOS,
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
# BANCO DE HORÁRIOS
# ============================================================

def criar_banco():
    """Cria o banco e a tabela de horários, caso ainda não existam."""

    with sqlite3.connect(DB_HORARIOS) as conn:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABELA_HORARIOS} (
                turma TEXT,
                codigo_da_disciplina INTEGER,
                nome_da_disciplina TEXT,
                codigo_do_setor INTEGER,
                nome_do_setor TEXT,
                campus INTEGER,
                nome_do_campus TEXT,
                quantidade_de_creditos INTEGER,
                carga_horaria INTEGER,
                periodo TEXT,
                dia INTEGER,
                hora_de_inicio TEXT,
                hora_de_termino TEXT,
                codigo_da_sala TEXT,
                PRIMARY KEY (
                    codigo_da_disciplina,
                    turma,
                    periodo,
                    dia,
                    hora_de_inicio,
                    hora_de_termino,
                    codigo_da_sala
                )
            )
            """
        )
        conn.commit()


def inserir_horarios(horarios):
    """Insere ou atualiza no SQLite os horários retornados pela API."""

    if not horarios:
        return 0

    valores = [
        (
            horario.get("turma"),
            horario.get("codigo_da_disciplina"),
            horario.get("nome_da_disciplina"),
            horario.get("codigo_do_setor"),
            horario.get("nome_do_setor"),
            horario.get("campus"),
            horario.get("nome_do_campus"),
            horario.get("quantidade_de_creditos"),
            horario.get("carga_horaria"),
            horario.get("periodo"),
            horario.get("dia"),
            horario.get("hora_de_inicio"),
            horario.get("hora_de_termino"),
            horario.get("codigo_da_sala"),
        )
        for horario in horarios
    ]

    with sqlite3.connect(DB_HORARIOS, timeout=30) as conn:
        conn.executemany(
            f"""
            INSERT OR REPLACE INTO {TABELA_HORARIOS} (
                turma,
                codigo_da_disciplina,
                nome_da_disciplina,
                codigo_do_setor,
                nome_do_setor,
                campus,
                nome_do_campus,
                quantidade_de_creditos,
                carga_horaria,
                periodo,
                dia,
                hora_de_inicio,
                hora_de_termino,
                codigo_da_sala
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            valores,
        )
        conn.commit()

    return len(valores)


# ============================================================
# PRINCIPAL
# ============================================================

def download_horarios():
    print("============== DOWNLOAD DE HORÁRIOS ==============")
    criar_banco()

    pagina = 1
    total = 0

    while True:
        horarios = buscar_pagina(pagina)

        if horarios is None:
            logging.error(f"Download interrompido na página {pagina}")
            print(f"Erro ao baixar a página {pagina}. Download interrompido.")
            break

        if not horarios:
            logging.info(f"Página {pagina} vazia. Download finalizado.")
            break

        quantidade = inserir_horarios(horarios)
        total += quantidade

        logging.info(
            f"Página {pagina} | {quantidade} horários processados | total={total}"
        )
        print(f"Página {pagina} | {quantidade} horários | Total: {total}")

        if len(horarios) < TAMANHO_PAGINA:
            break

        pagina += 1

    print(f"\nDownload concluído. {total} horários processados.")


if __name__ == "__main__":
    download_horarios()
