import datetime
import time
import threading
from typing import List
import requests, json
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed

from application.config import URL_SIG, URL_BASE
from requests.exceptions import ChunkedEncodingError, RequestException
from .aux_estudante_norm import estudante_norm

import logging

logging.basicConfig(
    filename="log_estudantes_threaded.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8"
)

MAX_WORKERS_CURSOS = 4    # Threads simultâneas por curso
MAX_WORKERS_PAGINAS = 6   # Threads simultâneas para páginas dentro de um curso
MAX_PAGINAS_ESTUDANTES = 500 # limite de segurança para evitar loop infinito

# Lock para escrita segura no sqlite
db_write_lock = threading.Lock()

keys_to_remove = [
    "cra",
    "iech",
    "iepl",
    "iea",
    "mcn",
    "iean",
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
]


def log_to_file(mensagem):
    logging.info(mensagem)

def fetch_estudantes_page(url, codigo_curso, page, limit=200, retries=5):
    for tentativa in range(retries):
        try:
            resp = requests.get(
                f"{url}/estudantes",
                params={
                    "curso": codigo_curso,
                    "pagina": page,
                    "tamanho": limit,
                },
                timeout=300,
            )

            data = resp.json()

            if isinstance(data, list):
                return data

            # fim da paginação / página inválida
            if isinstance(data, dict) and "errors" in data:
                return "END"

            # resposta inesperada -> retry
            time.sleep(2 ** tentativa)

        except (ChunkedEncodingError, RequestException, ValueError):
            time.sleep(2 ** tentativa)

    return "ERROR"

def fetch_all_pages_curso(url, codigo_curso, descricao, limit=100):
    todos_estudantes = []
    page = 1

    while page <= MAX_PAGINAS_ESTUDANTES:
        paginas_a_buscar = list(
            range(page, page + MAX_WORKERS_PAGINAS)
        )

        with ThreadPoolExecutor(
            max_workers=MAX_WORKERS_PAGINAS
        ) as executor:
            futures = {
                executor.submit(
                    fetch_estudantes_page,
                    url,
                    codigo_curso,
                    p,
                    limit
                ): p
                for p in paginas_a_buscar
            }

            resultados = {}
            for future in as_completed(futures):
                p = futures[future]
                try:
                    resultados[p] = future.result()
                except Exception as e:
                    resultados[p] = "ERROR"
                    log_to_file(
                        f"Erro inesperado página {p}: {e}"
                    )

        encontrou_fim = False

        for p in paginas_a_buscar:
            dados = resultados.get(p)

            if dados == "END":
                print(
                    f"CURSO {descricao} terminou na página {p-1}"
                )
                encontrou_fim = True
                break

            if dados == "ERROR":
                continue

            print(
                f"CURSO {descricao} | página {p} | qtd {len(dados)}"
            )
            todos_estudantes.extend(dados)

        if encontrou_fim:
            break

        page += MAX_WORKERS_PAGINAS

    else:
        log_to_file(
            f"Curso {codigo_curso} atingiu limite "
            f"de {MAX_PAGINAS_ESTUDANTES} páginas"
        )
        print(
            f"Curso {codigo_curso} atingiu limite "
            f"de {MAX_PAGINAS_ESTUDANTES} páginas"
        )

    return todos_estudantes

def get_periodos_calendarios():
    calendarios = []
    req_resp = requests.get(f"{URL_BASE}/calendarios")
    if req_resp.status_code == 200:
        calendarios += json.loads(req_resp.text)

    req_resp = requests.get(f"{URL_SIG}/calendarios")
    if req_resp.status_code == 200:
        calendarios += json.loads(req_resp.text)

    todos_periodos = [
        str(x)
        for x in sorted(
            set(
                [float(calendario["periodo"]) for calendario in calendarios]
                + [
                    1975.1, 1975.2, 1976.1, 1976.2, 1977.1, 1977.2,
                    1978.1, 1978.2, 1979.1, 1979.2, 1980.1, 1980.2,
                    1981.1, 1981.2, 1982.1, 1982.2, 1983.1, 1983.2,
                    1984.1, 1984.2, 1985.1, 1985.2, 1986.1, 1986.2,
                    1987.1, 1987.2, 1988.1, 1988.2, 1989.1, 1989.2,
                    1990.1, 1990.2, 1991.1, 1991.2, 1992.1, 1992.2,
                    1993.1, 1993.2, 1994.1, 1994.2, 1995.1, 1995.2,
                    1996.1, 1996.2, 1997.1, 1997.2, 1998.1, 1998.2,
                    1999.1, 1999.2, 2000.1, 2000.2, 2001.1, 2001.2,
                    2002.1, 2002.2, 2003.1, 2003.2, 2026.1, 2026.2,
                ]
            )
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


def processar_estudante(
    estudante,
    todos_periodos,
    keys_a_remover,
    estudante_copy_keys
):
    """
    Aplica transformações e normalizações em um estudante.
    """
    try:
        estudante["idade"] = int(estudante.get("idade") or 0)

        estudante["codigo_do_curriculo"] = estudante.get(
            "codigo_do_curriculo"
        )

        estudante["ano_de_conclusao_ensino_medio"] = int(
            estudante.get("ano_de_conclusao_ensino_medio") or 0
        )

        estudante["prac_renda_per_capita_ate"] = (
            estudante.get("renda_per_capita") or 0
        ) / 1528

        estudante["renda_per_capita_ate"] = float(
            estudante.get("prac_renda_per_capita") or 0
        )

        estudante["mc"] = estudante.get(
            "notas_acumuladas",
            0.0001
        ) / (estudante.get("creditos_do_cra", 1) or 1)

        deficiencias = estudante.get("deficiencias")
        estudante["tem_deficiencia"] = (
            "sim" if deficiencias not in (None, "", []) else "nao"
        )

        situacao = estudante.get("situacao", "--").lower()

        if situacao not in ["ativo", "ativo - formando"]:

            # só calcula evasão se API não tem
            if not estudante.get("periodo_de_evasao"):
                try:
                    indice_ingresso = todos_periodos.index(
                        estudante["periodo_de_ingresso"]
                    )
                except ValueError:
                    indice_ingresso = None

                periodos = estudante.get(
                    "periodos_completados",
                    0
                ) or 0

                if indice_ingresso is not None and periodos > 0:
                    indice_final = indice_ingresso + periodos - 1

                    if 0 <= indice_final < len(todos_periodos):
                        estudante["periodo_de_evasao"] = (
                            todos_periodos[indice_final]
                        )
                    else:
                        estudante["periodo_de_evasao"] = None
                else:
                    estudante["periodo_de_evasao"] = None

            # valida periodo evasao < periodo ingresso
            ingresso = periodo_to_tuple(
                estudante.get("periodo_de_ingresso")
            )
            evasao = periodo_to_tuple(
                estudante.get("periodo_de_evasao")
            )

            if ingresso and evasao and evasao < ingresso:
                estudante["periodo_de_evasao"] = None

        for key in keys_a_remover:
            estudante.pop(key, None)

        estudante = {
            k: ", ".join(v) if isinstance(v, list) else v
            for k, v in estudante.items()
        }

        estudante = estudante_norm(estudante)

        return tuple(
            estudante.get(col) for col in estudante_copy_keys
        )

    except Exception as e:
        log_to_file(f"Erro ao processar estudante: {e}")
        return None



def processar_curso(url, curso, todos_periodos, tabela, conn_db_estudante):
    """
    Executa o pipeline completo para um curso
    """
    codigo_curso = curso["codigo_do_curso"]
    descricao    = curso["descricao"]
    LIMIT        = 100

    dados_estudantes = fetch_all_pages_curso(url, codigo_curso, descricao, limit=LIMIT)

    if not dados_estudantes:
        print(f"Curso {codigo_curso} ({descricao}): sem dados.")
        return

    # Constrói o template de INSERT a partir do primeiro estudante
    estudante_copy = dados_estudantes[0].copy()
    estudante_copy["idade"]                          = 0
    estudante_copy["codigo_do_curriculo"]            = 0
    estudante_copy["ano_de_conclusao_ensino_medio"]  = 0
    estudante_copy["prac_renda_per_capita_ate"]      = 0
    estudante_copy["renda_per_capita_ate"]           = 0
    estudante_copy["mc"]                             = 0.0001
    estudante_copy["tem_deficiencia"]                = None
    estudante_copy["cotista"]                        = None
    estudante_copy = {
        k: v for k, v in estudante_copy.items() if k not in keys_to_remove
    }

    columns      = ", ".join(estudante_copy.keys())
    placeholders = ", ".join(["?"] * len(estudante_copy.keys()))
    command      = f"INSERT OR IGNORE INTO {tabela} ({columns}) VALUES ({placeholders});"

    # Transforma cada estudante em paralelo (CPU-bound leve, aceitável em threads)
    valores = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS_PAGINAS) as executor:
        futures = [
            executor.submit(
                processar_estudante,
                estudante,
                todos_periodos,
                keys_to_remove,
                list(estudante_copy.keys()),
            )
            for estudante in dados_estudantes
        ]
        for future in as_completed(futures):
            row = future.result()
            if row is not None:
                valores.append(row)

    # Escrita no SQLite com lock (sqlite3 não suporta escrita multi-thread sem WAL)
    if valores:
        with db_write_lock:
            with conn_db_estudante:
                conn_db_estudante.executemany(command, valores)

    print(f"Curso {descricao} concluído — {len(valores)} estudantes inseridos.")
    log_to_file(f"Curso {descricao} concluído — {len(valores)} estudantes inseridos.")



def aux_estudantes_ufcg_threaded(URL):
    """
    Versão com threads de aux_estudantes_ufcg.
    Paraleliza tanto a busca de páginas por curso quanto o processamento
    de múltiplos cursos simultaneamente.

    Garante escrita segura no SQLite via threading.Lock.
    """
    tabela = "estudantes_ufcg_novo"
    conn_db_estudante = sqlite3.connect(f"{tabela}.sqlite", check_same_thread=False)

    # Habilita WAL para melhor performance com múltiplas threads leitoras
    conn_db_estudante.execute("PRAGMA journal_mode=WAL;")

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
        cotista TEXT
    );
    """
    conn_db_estudante.execute(sql)
    conn_db_estudante.commit()

    todos_periodos = get_periodos_calendarios()
    todos_periodos = sorted(
        todos_periodos, key=lambda p: (int(p.split(".")[0]), int(p.split(".")[1]))
    )

    if URL == URL_SIG:
        conn_db_estudante.execute(f"DELETE FROM {tabela}")
        conn_db_estudante.commit()

    req_cursos = requests.get(f"{URL}/cursos", params={"status": "ATIVOS"})

    if req_cursos.status_code != 200:
        print(f"Erro ao buscar cursos: {req_cursos.status_code}")
        conn_db_estudante.close()
        return

    dados_cursos = json.loads(req_cursos.content)
    print(f"Total de cursos: {len(dados_cursos)} | Workers de cursos: {MAX_WORKERS_CURSOS}")
    log_to_file(f"Iniciando com {len(dados_cursos)} cursos | Workers: {MAX_WORKERS_CURSOS}")

    # Processa cursos em paralelo
    with ThreadPoolExecutor(max_workers=MAX_WORKERS_CURSOS) as executor:
        futures = {
            executor.submit(
                processar_curso,
                URL,
                curso,
                todos_periodos,
                tabela,
                conn_db_estudante,
            ): curso["descricao"]
            for curso in dados_cursos
        }

        for future in as_completed(futures):
            descricao = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"Erro no curso {descricao}: {e}")
                log_to_file(f"Erro no curso {descricao}: {e}")

    conn_db_estudante.close()
    print("Ingestão concluída.")
    log_to_file("Ingestão concluída.")



def get_estudantes_ufcg(params):
    tabela = "estudantes_ufcg_novo"
    conn_db_estudante = sqlite3.connect(f"{tabela}.sqlite")
    conn_db_estudante.row_factory = sqlite3.Row
    cursor = conn_db_estudante.cursor()
    where = []
    values = []

    for key, value in params.items():
        if value != "":
            if key == "situacao-do-estudante":
                where.append(
                    f"situacao='ATIVO'" if value == "ATIVOS" else f"situacao!='ATIVO'"
                )
            if key == "periodo-de-ingresso-de":
                where.append(f"periodo_de_ingresso>={value}")
            if key == "periodo-de-ingresso-ate":
                where.append(f"periodo_de_ingresso<='{value}'")
            if key == "periodo-de-evasao-de":
                where.append(f"periodo_de_evasao>={value}")
            if key == "periodo-de-evasao-ate":
                where.append(f"periodo_de_evasao<='{value}'")
            if key == "curso":
                where.append(f"codigo_do_curso={value}")
            if key == "campus":
                where.append(f"campus={value}")

    query = (
        f"SELECT * FROM {tabela} WHERE {' AND '.join(where)}"
        if where
        else f"SELECT * FROM {tabela}"
    )
    print(query)
    cursor.execute(query, values)
    rows = cursor.fetchall()
    estudantes = [dict(row) for row in rows]
    return estudantes


def get_estudantes_gerais_ufcg(params):
    tabela = "estudantes_ufcg_novo"
    conn_db_estudante = sqlite3.connect(f"{tabela}.sqlite")
    conn_db_estudante.row_factory = sqlite3.Row
    cursor = conn_db_estudante.cursor()
    where = []
    values = []

    for key, value in params.items():
        if value != "":
            if key == "situacao-do-estudante":
                if value == "ATIVOS":
                    where.append(f"situacao IN ('ATIVO', 'CADASTRADO')")
                elif value == "EGRESSOS":
                    where.append(f"situacao IN ('FORMADO', 'CONCLUÍDO')")
                elif value == "FORMANDOS":
                    where.append(f"situacao='ATIVO - FORMANDO'")
                else:
                    where.append(
                        f"situacao IN ('NÃO CADASTRADO', 'CANCELADO', 'DESCONHECIDO', 'TRANCADO')"
                    )
            if key == "periodo-de-ingresso-de":
                where.append(f"periodo_de_ingresso>={value}")
            if key == "periodo-de-ingresso-ate":
                where.append(f"periodo_de_ingresso<='{value}'")
            if key == "periodo-de-evasao-de":
                where.append(f"periodo_de_evasao>={value}")
            if key == "periodo-de-evasao-ate":
                where.append(f"periodo_de_evasao<='{value}'")
            if key == "curso":
                where.append(f"codigo_do_curso={value}")
            if key == "campus":
                where.append(f"campus={value}")

    query = (
        f"SELECT * FROM {tabela} WHERE {' AND '.join(where)}"
        if where
        else f"SELECT * FROM {tabela}"
    )
    print(query)
    cursor.execute(query, values)
    rows = cursor.fetchall()
    estudantes = [dict(row) for row in rows]
    return estudantes


if __name__ == "__main__":
    aux_estudantes_ufcg_threaded(URL_SIG)
