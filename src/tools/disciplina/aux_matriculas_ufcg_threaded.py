import logging
import time
import threading
import requests
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.exceptions import ChunkedEncodingError, RequestException

from application.config import URL_SIG, URL_BASE


logging.basicConfig(
    filename="log_matriculas_com_threads.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8"
)

MAX_BACKOFF = 32  # segundos
MAX_PAGINAS = 500  # teto de segurança para paginação

db_lock = threading.Lock()

BD = "estudantes_ufcg"
ESTUDANTES_DB_PATH = f"{BD}.sqlite"
ESTUDANTES_TABELA = BD

_estudante_cache = {}
_cache_lock = threading.Lock()


def get_dados_estudante(matricula: str) -> dict:
    """
    Busca os dados do estudante no banco estudantes_ufcg.sqlite pelo número de matrícula.
    Usa cache em memória para evitar consultas repetidas.
    """
    with _cache_lock:
        if matricula in _estudante_cache:
            return _estudante_cache[matricula]

    try:
        conn = sqlite3.connect(ESTUDANTES_DB_PATH, timeout=30.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT * FROM {ESTUDANTES_TABELA} WHERE matricula_do_estudante = ?",
            (matricula,)
        )
        row = cursor.fetchone()
        conn.close()
        dados = dict(row) if row else {}
    except sqlite3.Error as e:
        logging.error(f"Erro ao buscar estudante {matricula}: {e}")
        dados = {}

    with _cache_lock:
        _estudante_cache[matricula] = dados

    return dados



def fetch_com_retry(URL, endpoint, params, retries=5):
    for tentativa in range(retries):
        try:
            resp = requests.get(
                f"{URL}/{endpoint}",
                params=params,
                timeout=300
            )

            if resp.status_code == 200:
                dados = resp.json()

                # caso normal
                if isinstance(dados, list):
                    return dados

                # API retornou erro 
                if isinstance(dados, dict) and (
                    "errors" in dados or "404" in str(dados.get("message", ""))
                ):
                    logging.info(
                        f"Sem dados | {endpoint} | params={params}"
                    )
                    return []

                # resposta inesperada
                logging.warning(
                    f"Resposta inesperada | {endpoint} | params={params}"
                )

            else:
                logging.warning(
                    f"Status {resp.status_code} | {endpoint} | params={params} "
                    f"(tentativa {tentativa + 1}/{retries})"
                )

        except (ChunkedEncodingError, RequestException, ValueError) as e:
            logging.error(
                f"Erro tentativa {tentativa+1}/{retries} | "
                f"{endpoint} | {e}"
            )

        time.sleep(min(2 ** tentativa, MAX_BACKOFF))

    logging.error(
        f"Todas tentativas falharam | {endpoint} | params={params}"
    )
    return []



def fetch_disciplinas_curso(URL, codigo_curso):
    """
    Busca todas as disciplinas de um curso paginando de 200 em 200.
    Limite de MAX_PAGINAS páginas para evitar loop infinito caso a API
    retorne sempre 200 itens sem nunca terminar.
    """
    disciplinas = []
    page = 1
    while page <= MAX_PAGINAS:
        dados = fetch_com_retry(URL, "disciplinas", {
            "curso": codigo_curso,
            "pagina": page,
            "tamanho": 200,
        })
        if not dados:
            break
        disciplinas.extend(dados)
        if len(dados) < 200:
            break
        page += 1
    else:
        logging.error(
            f"Curso {codigo_curso} — atingiu limite de {MAX_PAGINAS} páginas de disciplinas, "
            f"verifique se a API está em loop"
        )
    return disciplinas


def fetch_matriculas_disciplina(URL, codigo_curso, codigo_disciplina):
    """
    Busca todas as matrículas de uma disciplina num curso de uma vez,
    sem paginação, para contornar o bug de paginação da API.
    """
    return fetch_com_retry(URL, "matriculas", {
        "curso": codigo_curso,
        "disciplina": codigo_disciplina,
        "tamanho": 9999,
    })


def _get_colunas_tabela(db_path, tabela):
    """Retorna a lista de colunas da tabela conforme definidas no schema do SQLite."""
    conn = sqlite3.connect(db_path, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({tabela})")
    colunas = [row[1] for row in cursor.fetchall()]
    conn.close()
    return colunas


def inserir_matriculas(matriculas_raw, codigo_curso, COLUNAS, command, db_path, log_label):
    """Enriquece matrículas com dados do estudante e insere no banco."""
    valores = []
    for matricula in matriculas_raw:
        matricula = {
            k: ", ".join(v) if isinstance(v, list) else v
            for k, v in matricula.items()
        }

        numero_matricula = matricula.get("matricula_do_estudante")
        dados_estudante = get_dados_estudante(numero_matricula) if numero_matricula else {}

        registro = {
            **dados_estudante,
            **matricula,
            "codigo_do_curso": codigo_curso,
        }

        valores.append(tuple(registro.get(col) for col in COLUNAS))

    if not valores:
        return 0

    with db_lock:
        conn = sqlite3.connect(db_path, timeout=30.0)
        try:
            conn.executemany(command, valores)
            conn.commit()
            logging.info(f"{log_label} | {len(valores)} matrículas inseridas")
        except sqlite3.Error as e:
            logging.error(f"Erro ao inserir {log_label}: {e}")
            conn.rollback()
            return 0
        finally:
            conn.close()

    return len(valores)


def processar_curso(curso, URL, tabela, db_path):
    """
    Para cada curso:
      1. Busca todas as disciplinas via /disciplinas (paginação estável)
      2. Para cada disciplina, busca todas as matrículas de uma vez via
         /matriculas?curso=X&disciplina=Y&tamanho=9999 (evita bug de paginação)
      3. Enriquece cada matrícula com dados do estudante via estudantes_ufcg.sqlite
      4. Insere no banco
    """
    codigo_curso = curso["codigo_do_curso"]
    total_inseridos = 0

    COLUNAS = _get_colunas_tabela(db_path, tabela)
    columns = ", ".join(COLUNAS)
    placeholders = ", ".join(["?"] * len(COLUNAS))
    command = f"INSERT OR IGNORE INTO {tabela} ({columns}) VALUES ({placeholders});"

    # Buscar todas as disciplinas do curso
    disciplinas = fetch_disciplinas_curso(URL, codigo_curso)
    if not disciplinas:
        logging.warning(f"Curso {codigo_curso} — nenhuma disciplina encontrada")
        return codigo_curso, 0

    print(f"Curso {codigo_curso} | {len(disciplinas)} disciplinas encontradas")

    # Para cada disciplina, buscar e inserir matrículas
    for disciplina in disciplinas:
        codigo_disciplina = disciplina.get("codigo_da_disciplina") or disciplina.get("codigo")
        nome_disciplina = disciplina.get("nome_da_disciplina") or disciplina.get("nome", "")

        if not codigo_disciplina:
            logging.warning(f"Curso {codigo_curso} — disciplina sem código: {disciplina}")
            continue

        matriculas_raw = fetch_matriculas_disciplina(URL, codigo_curso, codigo_disciplina)

        if not matriculas_raw:
            logging.info(f"Curso {codigo_curso} | Disciplina {codigo_disciplina} — sem matrículas")
            continue

        log_label = f"Curso {codigo_curso} | Disciplina {codigo_disciplina} ({nome_disciplina})"
        print(f"{log_label} | {len(matriculas_raw)} matrículas")

        inseridos = inserir_matriculas(
            matriculas_raw, codigo_curso, COLUNAS, command, db_path, log_label
        )
        total_inseridos += inseridos

    return codigo_curso, total_inseridos


def aux_matriculas_ufcg(URL):
    """Popula banco de dados com matrículas iterando por curso > disciplina > matrículas."""

    print(" ============== MATRICULAS COM THREADS ==================")
    tabela = "matriculas_ufcg"
    db_path = f"{tabela}.sqlite"

    # Criar tabela
    conn_db = sqlite3.connect(db_path)
    sql = f"""
        CREATE TABLE IF NOT EXISTS {tabela} (
            matricula_do_estudante TEXT,
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
            tem_deficiencia TEXT,
            cotista TEXT,
            codigo_da_disciplina INTEGER,
            nome_da_disciplina TEXT,
            periodo TEXT,
            turma INTEGER,
            status TEXT,
            tipo TEXT,
            media_final REAL,
            dispensas REAL
        );
    """
    conn_db.execute(sql)
    conn_db.commit()

    if URL == URL_BASE:
        logging.info(f"Limpando tabela {tabela} (URL_BASE)")
        conn_db.execute(f"DELETE FROM {tabela}")
        conn_db.commit()
    else:
        logging.info(f"Modo incremental (URL != URL_BASE)")

    conn_db.close()

    # Buscar cursos ativos
    try:
        req_cursos = requests.get(f"{URL}/cursos", params={"status": "ATIVOS"}, timeout=60)
        req_cursos.raise_for_status()
        dados_cursos = req_cursos.json()
        print(f"{len(dados_cursos)} cursos ativos encontrados")
    except Exception as e:
        logging.error(f"Erro ao buscar cursos: {e}")
        return

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(processar_curso, curso, URL, tabela, db_path): curso
            for curso in dados_cursos
        }
        for future in as_completed(futures):
            try:
                codigo, total = future.result()
                print(f"Curso {codigo} finalizado com {total} matrículas")
            except Exception as e:
                logging.error(f"Erro ao processar curso: {e}")


def get_matriculas_ufcg(params):
    """Busca matrículas com filtros"""
    tabela = "matriculas_ufcg"
    db_path = f"{tabela}.sqlite"

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    where_clauses = []
    values = []

    if "periodo-de" in params and params["periodo-de"]:
        where_clauses.append("periodo >= ?")
        values.append(params["periodo-de"])

    if "periodo-ate" in params and params["periodo-ate"]:
        where_clauses.append("periodo <= ?")
        values.append(params["periodo-ate"])

    if "disciplina" in params and params["disciplina"]:
        where_clauses.append("codigo_da_disciplina = ?")
        values.append(params["disciplina"])

    if "curso" in params and params["curso"] and "disciplina" not in params:
        where_clauses.append("codigo_do_curso = ?")
        values.append(params["curso"])

    if "turma" in params and params["turma"]:
        where_clauses.append("turma = ?")
        values.append(params["turma"])

    query = f"SELECT * FROM {tabela}"
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    try:
        cursor.execute(query, values)
        rows = cursor.fetchall()
        matriculas = [dict(row) for row in rows]
    except sqlite3.Error as e:
        logging.error(f"Erro ao buscar matrículas: {e}")
        matriculas = []
    finally:
        conn.close()

    return matriculas


if __name__ == "__main__":
    aux_matriculas_ufcg(URL_SIG)