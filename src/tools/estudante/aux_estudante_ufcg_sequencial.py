"""
Versão SEQUENCIAL do coletor de estudantes da API Eureca.
reduzir a carga na API e evitar sobrecarga.

Uso:
    python src/tools/estudante/aux_estudante_ufcg_sequencial.py
"""

import json
import logging
import sqlite3
import time
from typing import List

import requests
from requests.exceptions import ChunkedEncodingError, RequestException

from application.config import URL_SIG, URL_BASE
from .aux_estudante_norm import estudante_norm

logging.basicConfig(
    filename="log_estudantes_sequencial.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8",
)


MAX_PAGINAS_ESTUDANTES = 250

keys_to_remove = [
    "prac_atualizado",
    "prac_atualizado_em",
    "prac_cor",
    "prac_quilombola",
    "prac_indigena_aldeado",
    "prac_deficiente",
    "prac_deficiencias",
    "prac_deslocou_mudou",
    "ufpb",
    "prac_renda_per_capita_ate",
    "renda_per_capita",
    "indices_academicos",
]


session = requests.Session()


def log_to_file(mensagem):
    logging.info(mensagem)


def fetch_estudantes_page(url, codigo_curso, page, limit=100, retries=3):
    """
    Busca UMA página por vez.
    """

    for tentativa in range(retries):

        try:

            resp = session.get(
                f"{url}/estudantes",
                params={
                    "curso": codigo_curso,
                    "pagina": page,
                    "tamanho": limit,
                },
                timeout=(20, 200),
            )

            data = resp.json()

            if isinstance(data, list):
                return "END" if not data else data

            if isinstance(data, dict) and "errors" in data:
                return "END"

        except (ChunkedEncodingError, RequestException, ValueError) as e:

            log_to_file(f"Erro página {page}: {e}")

        time.sleep(min(2**tentativa, 8))

    return "ERROR"


def fetch_all_pages_curso(url, codigo_curso, descricao, limit=100):
    """
    Busca páginas SEQUENCIALMENTE.
    """

    todos_estudantes = []
    paginas_falhadas = []

    for page in range(1, MAX_PAGINAS_ESTUDANTES + 1):

        dados = fetch_estudantes_page(url, codigo_curso, page, limit)

        if dados == "END":

            print(f"CURSO {descricao} terminou " f"na página {page - 1}")

            break

        if dados == "ERROR":

            paginas_falhadas.append(page)

            log_to_file(f"Curso {descricao} | página {page} falhou")

            continue

        print(f"CURSO {descricao} | " f"página {page} | " f"qtd {len(dados)}")

        todos_estudantes.extend(dados)

        # pequena pausa para aliviar API
        time.sleep(0.3)

    # retry final
    if paginas_falhadas:

        log_to_file(
            f"Retry final de "
            f"{len(paginas_falhadas)} páginas "
            f"falhadas do curso {descricao}"
        )

        for p in paginas_falhadas:

            dados = fetch_estudantes_page(
                url, codigo_curso, p, limit, retries=8)

            if isinstance(dados, list):

                print(f"RECUPERADA página {p} | " f"{len(dados)} estudantes")

                todos_estudantes.extend(dados)

            else:

                log_to_file(f"Página {p} falhou definitivamente")

    return todos_estudantes


def get_periodos_calendarios():

    calendarios = []

    req_resp = session.get(f"{URL_BASE}/calendarios")

    if req_resp.status_code == 200:
        calendarios += json.loads(req_resp.text)

    req_resp = session.get(f"{URL_SIG}/calendarios")

    if req_resp.status_code == 200:
        calendarios += json.loads(req_resp.text)

    todos_periodos = [
        str(x)
        for x in sorted(
            set([float(calendario["periodo"]) for calendario in calendarios])
        )
    ]

    return todos_periodos


def periodo_to_tuple(p):

    if not p:
        return None

    p = str(p).strip()

    try:

        if "." in p:

            ano, semestre = p.split(".")

            return (int(ano), int(semestre))

        if len(p) >= 5:

            ano = int(p[:-1])
            semestre = int(p[-1])

            if semestre in (1, 2):
                return (ano, semestre)

    except (ValueError, TypeError):

        return None

    return None


def processar_estudante(estudante, todos_periodos, keys_a_remover, estudante_copy_keys):

    try:

        estudante["idade"] = int(estudante.get("idade") or 0)

        estudante["codigo_do_curriculo"] = estudante.get("codigo_do_curriculo")

        estudante["ano_de_conclusao_ensino_medio"] = int(
            estudante.get("ano_de_conclusao_ensino_medio") or 0
        )

        estudante["prac_renda_per_capita_ate"] = (
            estudante.get("renda_per_capita") or 0
        ) / 1528

        estudante["renda_per_capita_ate"] = float(
            estudante.get("prac_renda_per_capita") or 0
        )

        # ------------------ INDICES ACADÊMICOS ------------------------

        indices_academicos = estudante.get("indices_academicos") or {}

        estudante["mc"] = indices_academicos.get("MC", 0.0001)
        estudante["iea"] = indices_academicos.get("IEA", 0.0001)
        estudante["ira"] = indices_academicos.get("IRA", 0.0001)
        estudante["mcn"] = indices_academicos.get("MCN", 0.0001)
        estudante["iean"] = indices_academicos.get("IEAN", 0.0001)
        estudante["iech"] = indices_academicos.get("IECH", 0)
        estudante["iepl"] = indices_academicos.get("IEPL", 0.0001)
        estudante["iechp"] = indices_academicos.get("IECHP", 0)

        deficiencias = estudante.get("deficiencias")

        estudante["tem_deficiencia"] = (
            "sim" if deficiencias not in (None, "", []) else "nao"
        )

        situacao = estudante.get("situacao", "--").lower()

        if situacao not in ["ativo", "ativo - formando"]:

            if not estudante.get("periodo_de_evasao"):

                try:

                    indice_ingresso = todos_periodos.index(
                        estudante["periodo_de_ingresso"]
                    )

                except ValueError:

                    indice_ingresso = None

                periodos = estudante.get("periodos_completados", 0) or 0

                if indice_ingresso is not None and periodos > 0:

                    indice_final = indice_ingresso + periodos - 1

                    if 0 <= indice_final < len(todos_periodos):

                        estudante["periodo_de_evasao"] = todos_periodos[indice_final]

                    else:

                        estudante["periodo_de_evasao"] = None

        for key in keys_a_remover:
            estudante.pop(key, None)

        estudante = {
            k: ", ".join(v) if isinstance(v, list) else v for k, v in estudante.items()
        }

        estudante = estudante_norm(estudante)

        return tuple(estudante.get(col) for col in estudante_copy_keys)

    except Exception as e:

        log_to_file(f"Erro ao processar estudante: {e}")

        return None


def processar_curso(url, curso, todos_periodos, tabela, conn_db_estudante):

    codigo_curso = curso["codigo_do_curso"]
    descricao = curso["descricao"]

    dados_estudantes = fetch_all_pages_curso(
        url, codigo_curso, descricao, limit=100)

    if not dados_estudantes:

        print(f"Curso {codigo_curso} " f"({descricao}): sem dados.")

        return

    estudante_copy = dados_estudantes[0].copy()

    estudante_copy["idade"] = 0
    estudante_copy["codigo_do_curriculo"] = 0
    estudante_copy["ano_de_conclusao_ensino_medio"] = 0
    estudante_copy["prac_renda_per_capita_ate"] = 0
    estudante_copy["renda_per_capita_ate"] = 0
  
    estudante_copy = {
        k: v for k, v in estudante_copy.items() if k not in keys_to_remove
    }

    estudante_copy.update({
        "mc": 0.0001,
        "iea": 0.0001,
        "ira": 0.0001,
        "mcn": 0.0001,
        "iean": 0.0001,
        "iech": 0,
        "iepl": 0.0001,
        "iechp": 0,
        "tem_deficiencia": None,
        "cotista": None,
    })

    columns = ", ".join(estudante_copy.keys())

    placeholders = ", ".join(["?"] * len(estudante_copy.keys()))

    command = (
        f"INSERT OR IGNORE INTO {tabela} " f"({columns}) " f"VALUES ({placeholders});"
    )

    valores = []

    for estudante in dados_estudantes:

        row = processar_estudante(
            estudante, todos_periodos, keys_to_remove, list(
                estudante_copy.keys())
        )

        if row is not None:
            valores.append(row)

    if valores:

        with conn_db_estudante:

            conn_db_estudante.executemany(command, valores)

    print(
        f"Curso {descricao} concluído " f"— {len(valores)} estudantes inseridos.")

    log_to_file(
        f"Curso {descricao} concluído " f"— {len(valores)} estudantes inseridos."
    )


def aux_estudantes_ufcg_sequencial(URL):

    tabela = "estudantes_ufcg"

    conn_db_estudante = sqlite3.connect(f"{tabela}.sqlite")

    sql = f"""
    CREATE TABLE IF NOT EXISTS {tabela} (
        matricula_do_estudante TEXT PRIMARY KEY,
        codigo_do_curso INTEGER,
        nome_do_curso TEXT,
        turno_do_curso TEXT,
        codigo_do_curriculo INTEGER,
        campus INTEGER,
        nome_do_campus TEXT,
        codigo_do_setor INTEGER,
        nome_do_setor TEXT,
        estado_civil TEXT,
        sexo TEXT,
        idade INTEGER,
        situacao TEXT,
        motivo_de_evasao TEXT,
        periodo_de_evasao TEXT,
        forma_de_ingresso TEXT,
        periodo_de_ingresso TEXT,
        nacionalidade TEXT,
        local_de_nascimento TEXT,
        naturalidade TEXT,
        cor TEXT,
        deficiencias TEXT,
        ano_de_conclusao_ensino_medio INTEGER,
        tipo_de_ensino_medio TEXT,
        politica_afirmativa TEXT,
        creditos_do_cra INTEGER,
        notas_acumuladas REAL,
        periodos_completados INTEGER,
        creditos_tentados INTEGER,
        creditos_completados INTEGER,
        creditos_isentos INTEGER,
        creditos_falhados INTEGER,
        creditos_suspensos INTEGER,
        creditos_em_andamento INTEGER,
        velocidade_media REAL,
        taxa_de_sucesso REAL,
        renda_per_capita_ate REAL,
        mc REAL,
        iea REAL, 
        ira REAL,
        mcn REAL,
        iean REAL,
        iech REAL,
        iepl REAL,
        iechp REAL,
        tem_deficiencia TEXT,
        cotista TEXT
    );
    """

    conn_db_estudante.execute(sql)
    conn_db_estudante.commit()

    todos_periodos = get_periodos_calendarios()

    todos_periodos = sorted(
        todos_periodos, key=lambda p: (
            int(p.split(".")[0]), int(p.split(".")[1]))
    )

    if URL == URL_SIG:

        conn_db_estudante.execute(f"DELETE FROM {tabela}")

        conn_db_estudante.commit()

    req_cursos = session.get(f"{URL}/cursos", params={"status": "ATIVOS"})

    if req_cursos.status_code != 200:

        print(f"Erro ao buscar cursos: " f"{req_cursos.status_code}")

        conn_db_estudante.close()

        return

    dados_cursos = json.loads(req_cursos.content)

    print(f"Total de cursos: {len(dados_cursos)}")

    for curso in dados_cursos:

        try:

            processar_curso(URL, curso, todos_periodos,
                            tabela, conn_db_estudante)

            time.sleep(1)

        except Exception as e:

            descricao = curso.get("descricao", "desconhecido")

            print(f"Erro no curso {descricao}: {e}")

            log_to_file(f"Erro no curso {descricao}: {e}")

    conn_db_estudante.close()

    print("Ingestão concluída.")

    log_to_file("Ingestão concluída.")


if __name__ == "__main__":
    aux_estudantes_ufcg_sequencial(URL_SIG)