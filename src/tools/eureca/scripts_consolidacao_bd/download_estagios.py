import logging
import sqlite3
import time

import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.exceptions import ChunkedEncodingError, RequestException


# ============================================================
# CONFIGURAÇÃO
# ============================================================

URL = "https://eureca.sti.ufcg.edu.br/das-sig/v1/estagios"

DB_PATH = "estagios_ufcg.sqlite"
TABELA = "estagios_ufcg"

TAMANHO_PAGINA = 100
MAX_THREADS = 1
MAX_BACKOFF = 32


logging.basicConfig(
    filename="log_estagios_ufcg.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8"
)


# API

def fetch_pagina(page, retries=5):
    """Busca uma página de estágios."""

    for tentativa in range(retries):

        try:
            response = requests.get(
                URL,
                params={
                    "pagina": page,
                    "tamanho": TAMANHO_PAGINA
                },
                timeout=300
            )

            if response.status_code == 200:

                dados = response.json()

                if isinstance(dados, list):
                    return page, dados

                logging.warning(
                    f"Resposta inesperada | página={page}"
                )

            else:
                logging.warning(
                    f"Status {response.status_code} | "
                    f"página={page} | "
                    f"tentativa={tentativa + 1}/{retries}"
                )

        except (
            ChunkedEncodingError,
            RequestException,
            ValueError
        ) as e:

            logging.error(
                f"Erro | página={page} | "
                f"tentativa={tentativa + 1}/{retries} | "
                f"{e}"
            )

        time.sleep(
            min(2 ** tentativa, MAX_BACKOFF)
        )

    logging.error(
        f"Todas as tentativas falharam | "
        f"página={page}"
    )

    return page, None


# BANCO

def criar_tabela(conn):

    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABELA} (
            id INTEGER PRIMARY KEY,
            matricula_do_estudante TEXT,
            id_concedente INTEGER,
            cidade_concedente TEXT,
            uf_concedente TEXT,
            matricula_do_docente TEXT,
            nome_docente TEXT,
            obrigatorio BOOLEAN,
            inicio_vigencia TEXT,
            final_vigencia TEXT,
            carga_semanal INTEGER,
            status TEXT,
            bolsa_mensal REAL,
            auxilio_transporte_diario REAL
        )
    """)

    # CREATE TABLE IF NOT EXISTS não atualiza uma tabela que já existia.
    # Adiciona as colunas novas sem apagar os registros do banco antigo.
    colunas_esperadas = {
        "matricula_do_estudante": "TEXT",
        "id_concedente": "INTEGER",
        "cidade_concedente": "TEXT",
        "uf_concedente": "TEXT",
        "matricula_do_docente": "TEXT",
        "nome_docente": "TEXT",
        "obrigatorio": "BOOLEAN",
        "inicio_vigencia": "TEXT",
        "final_vigencia": "TEXT",
        "carga_semanal": "INTEGER",
        "status": "TEXT",
        "bolsa_mensal": "REAL",
        "auxilio_transporte_diario": "REAL",
    }
    colunas_existentes = {
        linha[1]
        for linha in conn.execute(f"PRAGMA table_info({TABELA})")
    }

    for coluna, tipo in colunas_esperadas.items():
        if coluna not in colunas_existentes:
            conn.execute(
                f"ALTER TABLE {TABELA} ADD COLUMN {coluna} {tipo}"
            )

    conn.commit()


def inserir_estagios(conn, estagios):

    if not estagios:
        return 0

    valores = [
        (
            estagio.get("id"),
            estagio.get("matricula_do_estudante"),
            estagio.get("id_concedente"),
            estagio.get("cidade_concedente"),
            estagio.get("uf_concedente"),
            estagio.get("matricula_do_docente"),
            estagio.get("nome_docente"),
            estagio.get("obrigatorio"),
            estagio.get("inicio_vigencia"),
            estagio.get("final_vigencia"),
            estagio.get("carga_semanal"),
            estagio.get("status"),
            estagio.get("bolsa_mensal"),
            estagio.get("auxilio_transporte_diario")
        )
        for estagio in estagios
    ]

    conn.executemany(
        f"""
        INSERT OR IGNORE INTO {TABELA} (
            id,
            matricula_do_estudante,
            id_concedente,
            cidade_concedente,
            uf_concedente,
            matricula_do_docente,
            nome_docente,
            obrigatorio,
            inicio_vigencia,
            final_vigencia,
            carga_semanal,
            status,
            bolsa_mensal,
            auxilio_transporte_diario
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        valores
    )

    conn.commit()

    return len(valores)


# PRINCIPAL

def download_estagios():

    print("============== DOWNLOAD DE ESTÁGIOS ==============")

    with sqlite3.connect(DB_PATH) as conn:

        criar_tabela(conn)

        pagina = 1
        total = 0

        with ThreadPoolExecutor(
            max_workers=MAX_THREADS
        ) as executor:

            while True:

                future = executor.submit(
                    fetch_pagina,
                    pagina
                )

                pagina_baixada, estagios = future.result()

                # Erro depois de todas as tentativas
                if estagios is None:

                    print(
                        f"Erro ao baixar página "
                        f"{pagina_baixada}"
                    )

                    logging.error(
                        f"Download interrompido na "
                        f"página {pagina_baixada}"
                    )

                    break

                # API retornou []
                if not estagios:

                    print(
                        f"Página {pagina_baixada} vazia. "
                        f"Fim dos dados."
                    )

                    logging.info(
                        f"Página {pagina_baixada} vazia. "
                        f"Download finalizado."
                    )

                    break

                quantidade = inserir_estagios(
                    conn,
                    estagios
                )

                total += quantidade

                print(
                    f"Página {pagina_baixada} | "
                    f"{quantidade} estágios | "
                    f"Total: {total}"
                )

                logging.info(
                    f"Página {pagina_baixada} | "
                    f"{quantidade} estágios"
                )

                pagina += 1

    print(
        f"\nDownload concluído. "
        f"{total} registros processados."
    )


# EXECUÇÃO

if __name__ == "__main__":
    download_estagios()
