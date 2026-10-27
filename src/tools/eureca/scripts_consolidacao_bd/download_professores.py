"""
Faz o cruzamento de dados entre a API de desenvolvimento do SIGAA
e a API eureca. Ao final gera um banco de dados professor_disciplina

docentes_ufcg.sqlite   # banco auxiliar usado para construir professor_disciplina
Tabela: docentes_ufcg
Fonte : https://api.dev.sti.ufcg.edu.br/docente/v1/docentes
        com paginação por limit/offset até lista vazia.

professor_disciplina.sqlite
Tabela: professor_disciplina
Fonte : https://eureca.sti.ufcg.edu.br/das-sig/v1/classes-por-professor/professor-anonimizado
             para cada docente, enriquecida com nome, siape, unidade, sexo.

Uso:
    python -m src.tools.professor.aux_professor_ufcg

Variáveis de ambiente:
    ACCESS_TOKEN – Bearer token da API do ambiente de desenvolvimento do SIGAA 
    API_KEY – x-api-key da API ambiente de desenvolvimento do SIGAA

NOTA: ACCESS_TOKEN expira em 24 horas

NÃO TEMOS MAIS AS CREDENCIAIS PRA EXECUTAR O SCRIPT!
"""

import os
from pathlib import Path
import time
import logging
import sqlite3
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from dotenv import load_dotenv

load_dotenv()


logging.basicConfig(
    filename="log_professores_ufcg.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8",
)


def _log(msg: str) -> None:
    logging.info(msg)
    print(msg)


ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", "")  
API_KEY      = os.getenv("API_KEY", "")       

DOCENTE_API_URL   = "https://api.dev.sti.ufcg.edu.br/docente/v1/docentes"
CLASSES_API_URL   = (
    "https://eureca.sti.ufcg.edu.br/das-sig/v1/"
    "classes-por-professor/professor-anonimizado"
)

HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "x-api-key": API_KEY,
}


SQLITE_DIR = os.getenv("SQLITE_DIR", ".")

DB_DOCENTES = os.path.join(SQLITE_DIR, "docentes_ufcg.sqlite")
DB_PROFESSOR_DISCIPLINA = os.path.join(SQLITE_DIR, "professor_disciplina.sqlite")


PAGE_LIMIT          = 100      # registros por página na API de docentes
CLASSES_PAGE_SIZE   = 200      # registros por página na API de classes
MAX_WORKERS_CLASSES = 8        # threads para buscar classes em paralelo
MAX_RETRIES         = 5        # tentativas por requisição com back-off

db_write_lock = threading.Lock()

def _get_with_retry(url, params, headers, retries=MAX_RETRIES):
    for attempt in range(retries):
        try:
            resp = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=60
            )

            if resp.status_code == 200:
                return resp.json()

            print("STATUS:", resp.status_code)
            print("BODY:", resp.text)
            print("HEADERS ENVIADOS:", headers)

        except Exception as exc:
            print(exc)

        time.sleep(2**attempt)

    return None


# Banco de DOCENTES do serviço SIGAA (API) 
def _create_docentes_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS docentes_ufcg (
            id_docente        INTEGER PRIMARY KEY,
            nome              TEXT,
            cpf               TEXT,
            sexo              TEXT,
            nome_identificacao TEXT,
            email             TEXT,
            siape             INTEGER,
            digito_siape      TEXT,
            id_ativo          INTEGER,
            id_situacao       INTEGER,
            id_unidade        INTEGER,
            unidade           TEXT,
            id_cargo          INTEGER,
            cargo             TEXT,
            regime_trabalho   INTEGER,
            data_admissao     INTEGER,
            id_institucional  INTEGER
        );
        """
    )
    conn.commit()


def _fetch_all_docentes() -> list[dict]:
    """Pagina a API de docentes até receber lista vazia."""
    todos: list[dict] = []
    offset = 0

    while True:
        dados = _get_with_retry(
            DOCENTE_API_URL,
            params={"limit": PAGE_LIMIT, "offset": offset},
            headers=HEADERS,
        )

        if not dados:
            _log(f"[INFO] Sem dados em offset={offset}. Paginação encerrada.")
            break

        if not isinstance(dados, list):
            _log(f"[WARN] Resposta inesperada em offset={offset}: {type(dados)}")
            break

        todos.extend(dados)
        _log(f"[INFO] offset={offset} → {len(dados)} docentes recebidos (total: {len(todos)})")

        if len(dados) < PAGE_LIMIT:
            # última página
            break

        offset += PAGE_LIMIT

    return todos


def _docente_to_row(d: dict) -> tuple:
    return (
        d.get("id-docente"),
        d.get("nome"),
        d.get("cpf"),
        d.get("sexo"),
        d.get("nome-identificacao"),
        d.get("email"),
        d.get("siape"),
        d.get("digito-siape"),
        d.get("id-ativo"),
        d.get("id-situacao"),
        d.get("id-unidade"),
        d.get("unidade"),
        d.get("id-cargo"),
        d.get("cargo"),
        d.get("regime-trabalho"),
        d.get("data-admissao"),
        d.get("id-institucional"),
    )


def download_professores() -> list[dict]:
    """
    Busca todos os docentes na API e persiste no SQLite.
    Retorna a lista de dicts brutos para reuso na ingestão de disciplinas.
    """
    _log("Ingestão de docentes")
    docentes = _fetch_all_docentes()

    if not docentes:
        _log("Nenhum docente retornado pela API.")
        return []

    conn = sqlite3.connect(DB_DOCENTES)
    _create_docentes_table(conn)


    conn.execute("DELETE FROM docentes_ufcg")
    conn.commit()

    rows = [_docente_to_row(d) for d in docentes]
    conn.executemany(
        """
        INSERT OR REPLACE INTO docentes_ufcg (
            id_docente, nome, cpf, sexo, nome_identificacao, email,
            siape, digito_siape, id_ativo, id_situacao, id_unidade,
            unidade, id_cargo, cargo, regime_trabalho, data_admissao,
            id_institucional
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        rows,
    )
    conn.commit()
    conn.close()
    _log(f"{len(rows)} docentes persistidos em {DB_DOCENTES}")
    return docentes


# Banco de professor_disciplina obtido a partir da união de 2 fontes:
# Banco de docentes_ufcg.sqlite e  do endpoint /classes-por-professor/professor-anonimizado

def _create_professor_disciplina_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS professor_disciplina (
            turma                   INTEGER,
            codigo_da_disciplina    INTEGER,
            nome_da_disciplina      TEXT,
            periodo                 TEXT,
            matricula_do_docente    INTEGER,
            carga_horaria_especifica INTEGER,
            nome                    TEXT,
            siape                   INTEGER,
            unidade                 TEXT,
            sexo                    TEXT,
            PRIMARY KEY (codigo_da_disciplina, turma, periodo, matricula_do_docente)
        );
        """
    )
    conn.commit()


# Busca todas as turmas de um professor paginando a API de classes.
# Retorna lista de registros de turma.
def _fetch_classes_for_professor(id_docente: int) -> list[dict]:
    """
    Busca todas as turmas de um professor paginando a API de classes.
    Retorna lista de registros de turma.
    """
    todas: list[dict] = []
    pagina = 1

    while True:
        dados = _get_with_retry(
            CLASSES_API_URL,
            params={"professor": id_docente, "pagina": pagina, "tamanho": CLASSES_PAGE_SIZE},
            headers={}, 
        )

        if not dados or not isinstance(dados, list):
            break

        todas.extend(dados)

        if len(dados) < CLASSES_PAGE_SIZE:
            break

        pagina += 1

    return todas


def _processar_professor_disciplinas(
    docente: dict,
    conn: sqlite3.Connection,
) -> int:
    """
    Para um docente, busca suas turmas e insere no banco professor_disciplina.
    Retorna o número de linhas inseridas.
    """
    id_docente = docente.get("id-docente")
    nome       = docente.get("nome")
    siape      = docente.get("siape")
    unidade    = docente.get("unidade")
    sexo       = docente.get("sexo")

    turmas = _fetch_classes_for_professor(id_docente)

    if not turmas:
        return 0

    rows = []
    for turma_rec in turmas:
        turma_num         = turma_rec.get("turma")
        codigo_disciplina = turma_rec.get("codigo_da_disciplina")
        nome_disciplina   = turma_rec.get("nome_da_disciplina")
        periodo           = turma_rec.get("periodo")

        docentes_turma = turma_rec.get("docentes", [])
        for doc in docentes_turma:
            matricula  = doc.get("matricula_do_docente")
            carga_hor  = doc.get("carga_horaria_especifica")

            # só persiste linhas do docente corrente
            if matricula != id_docente:
                continue

            rows.append((
                turma_num,
                codigo_disciplina,
                nome_disciplina,
                periodo,
                matricula,
                carga_hor,
                nome,
                siape,
                unidade,
                sexo,
            ))

    if rows:
        with db_write_lock:
            with conn:
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO professor_disciplina (
                        turma, codigo_da_disciplina, nome_da_disciplina,
                        periodo, matricula_do_docente, carga_horaria_especifica,
                        nome, siape, unidade, sexo
                    ) VALUES (?,?,?,?,?,?,?,?,?,?)
                    """,
                    rows,
                )

    return len(rows)


def download_professor_disciplina(docentes: list[dict]) -> None:
    """
    Para cada docente, busca suas turmas/disciplinas e persiste
    no banco professor_disciplina.sqlite com dados enriquecidos.
    """
    _log("Ingestão de professor_disciplina")

    conn = sqlite3.connect(DB_PROFESSOR_DISCIPLINA, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    _create_professor_disciplina_table(conn)

    # limpa e reinsere (ingestão completa)
    with db_write_lock:
        conn.execute("DELETE FROM professor_disciplina")
        conn.commit()

    total_linhas = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS_CLASSES) as executor:
        futures = {
            executor.submit(_processar_professor_disciplinas, doc, conn): doc.get("id-docente")
            for doc in docentes
        }

        for future in as_completed(futures):
            id_doc = futures[future]
            try:
                n = future.result()
                if n:
                    total_linhas += n
                    _log(f"Docente {id_doc} → {n} turmas inseridas")
            except Exception as exc:
                _log(f"Docente {id_doc}: {exc}")

    conn.close()
    _log(f"professor_disciplina: {total_linhas} registros em {DB_PROFESSOR_DISCIPLINA}")



# Funções de leitura (para uso por outras tools)
def get_docentes_ufcg(params: dict = {}) -> list[dict]:
    """
    Lê a tabela docentes_ufcg com filtros opcionais.

    Parâmetros suportados:
        sexo    – "M" ou "F"
        unidade – fragmento do nome da unidade (LIKE)
        siape   – número siape exato
    """
    conn = sqlite3.connect(DB_DOCENTES)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    where, values = [], []
    for key, value in params.items():
        if value == "":
            continue
        if key == "sexo":
            where.append("sexo = ?")
            values.append(value)
        elif key == "unidade":
            where.append("unidade LIKE ?")
            values.append(f"%{value}%")
        elif key == "siape":
            where.append("siape = ?")
            values.append(value)

    query = f"""
    SELECT *
    FROM professor_disciplina
    WHERE {' AND '.join(where)}
    """

    cursor.execute(query, values)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_professor_disciplina(params: dict = {}) -> list[dict]:
    """
    Lê a tabela professor_disciplina com filtros opcionais.
    Se 'periodo' não for informado, usa o período mais recente disponível.

    Parâmetros suportados:
        periodo              – ex: "2026.1"
        codigo_da_disciplina – código numérico
        matricula_do_docente – matrícula/id do docente
        unidade              – fragmento da unidade (LIKE)
    """

    # print("==== DEBUG SQLITE ====")
    # print("DB_PROFESSOR_DISCIPLINA =", DB_PROFESSOR_DISCIPLINA)
    # print("ABS =", Path(DB_PROFESSOR_DISCIPLINA).resolve())
    # print("EXISTS =", Path(DB_PROFESSOR_DISCIPLINA).exists())

    conn = sqlite3.connect(DB_PROFESSOR_DISCIPLINA)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
    SELECT name
    FROM sqlite_master
    WHERE type='table'
    """)

    #print("TABLES =", [r[0] for r in cursor.fetchall()])

    # Se período não informado, descobre o mais recente
    periodo_param = params.get("periodo", "").strip()
    if not periodo_param:
        cursor.execute(
            "SELECT periodo FROM professor_disciplina ORDER BY periodo DESC LIMIT 1"
        )
        row = cursor.fetchone()
        if row:
            periodo_param = row["periodo"]
            _log(f"Período não informado; usando mais recente: {periodo_param}")

    where, values = [], []

    if periodo_param:
        where.append("periodo = ?")
        values.append(periodo_param)

    for key, value in params.items():
        if key == "periodo" or value == "":
            continue
        if key == "codigo_da_disciplina":
            where.append("codigo_da_disciplina = ?")
            values.append(value)
        elif key == "matricula_do_docente":
            where.append("matricula_do_docente = ?")
            values.append(value)
        elif key == "unidade":
            where.append("unidade LIKE ?")
            values.append(f"%{value}%")

    query = (
        f"SELECT * FROM professor_disciplina WHERE {' AND '.join(where)}"
        if where
        else "SELECT * FROM professor_disciplina"
    )
    cursor.execute(query, values)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


if __name__ == "__main__":
    pass
    #Ingere docentes → popula docentes_ufcg.sqlite
    # docentes = download_professores()

    # # Para cada docente, busca disciplinas e popula professor_disciplina.sqlite
    # if docentes:
    #     download_professor_disciplina(docentes)
   
    