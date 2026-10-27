import time
import logging
import sqlite3
import requests

from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.exceptions import ChunkedEncodingError, RequestException

from application.config import URL_SIG
from .estudante_norm import estudante_norm


# ============================================================
# CONFIGURAÇÃO
# ============================================================

MAX_THREADS = 1
MAX_THREADS_NORMALIZACAO = 1

TAMANHO_PAGINA = 100
MAX_RETRIES = 10

DB_PATH = "estudantes_ufcg.sqlite"
TABELA = "estudantes_ufcg"


logging.basicConfig(
    filename="log_estudantes_ufcg.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8"
)


# BUSCAR PÁGINA

def buscar_pagina(url, codigo_curso, pagina):
    """
    Busca uma página de estudantes.

    Retorna:
        list    -> estudantes encontrados
        "END"   -> fim da paginação
        "ERROR" -> erro real após todas as tentativas
    """

    for tentativa in range(MAX_RETRIES):

        try:

            response = requests.get(
                f"{url.rstrip('/')}/estudantes",
                params={
                    "curso": codigo_curso,
                    "pagina": pagina,
                    "tamanho": TAMANHO_PAGINA
                },
                timeout=300
            )

            dados = response.json()

            # Existem estudantes nessa página
            if isinstance(dados, list):

                if dados:
                    return dados
                return "END"

            if isinstance(dados, dict) and "errors" in dados:
                return "END"

            # Resposta inesperada

            logging.warning(
                f"Resposta inesperada | "
                f"curso={codigo_curso} | "
                f"pagina={pagina} | "
                f"resposta={dados}"
            )

            time.sleep(2 ** tentativa)

        except (
            ChunkedEncodingError,
            RequestException,
            ValueError
        ) as e:

            logging.warning(
                f"Erro curso={codigo_curso}, "
                f"pagina={pagina}, "
                f"tentativa={tentativa + 1}/{MAX_RETRIES}: {e}"
            )

            time.sleep(2 ** tentativa)

    logging.error(
        f"Todas as tentativas falharam | "
        f"curso={codigo_curso} | "
        f"pagina={pagina}"
    )

    return "ERROR"


# NORMALIZAÇÃO / EXTRAÇÃO

def processar_estudante(estudante):

    matricula = estudante.get(
        "matricula_do_estudante"
    )

    try:

        # Extrair índices acadêmicos

        indices = estudante.pop(
            "indices_academicos",
            {}
        ) or {}

        estudante["mc"] = indices.get("MC", None)
        estudante["iea"] = indices.get("IEA", None)
        estudante["ira"] = indices.get("IRA", None)
        estudante["mcn"] = indices.get("MCN", None)
        estudante["iean"] = indices.get("IEAN", None)
        estudante["iech"] = indices.get("IECH", None)
        estudante["iepl"] = indices.get("IEPL", None)
        estudante["iechp"] = indices.get("IECHP", None)

        # Normalização existente

        estudante = estudante_norm(estudante)

        return estudante

    except Exception as e:

        logging.info(
            f"Erro estudante {matricula}: {e}"
        )

        return None


# PROCESSAR PÁGINA

def processar_pagina(estudantes):

    resultados = []

    with ThreadPoolExecutor(
        max_workers=MAX_THREADS_NORMALIZACAO
    ) as executor:

        futures = [
            executor.submit(
                processar_estudante,
                estudante
            )
            for estudante in estudantes
        ]

        for future in as_completed(futures):

            estudante = future.result()

            if estudante is not None:
                resultados.append(estudante)

    return resultados


# BUSCAR ESTUDANTES DE UM CURSO
def buscar_estudantes(codigo_curso, url):

    pagina = 1
    estudantes = []

    while True:

        dados = buscar_pagina(
            url,
            codigo_curso,
            pagina
        )

        # ----------------------------------------------------
        # Fim da paginação
        # ----------------------------------------------------

        if dados == "END":

            logging.info(
                f"CURSO {codigo_curso} concluído | "
                f"{len(estudantes)} estudantes inseridos"
            )

            break

        # ----------------------------------------------------
        # Erro real
        # ----------------------------------------------------

        if dados == "ERROR":

            logging.error(
                f"ERRO CURSO {codigo_curso} | "
                f"Página {pagina} | "
                f"{len(estudantes)} estudantes processados até agora"
            )

            break

        # ----------------------------------------------------
        # Processar página
        # ----------------------------------------------------

        estudantes_processados = processar_pagina(dados)

        estudantes.extend(
            estudantes_processados
        )

        # ----------------------------------------------------
        # Log da página
        # ----------------------------------------------------

        logging.info(
            f"CURSO {codigo_curso} | "
            f"PÁGINA {pagina} | "
            f"{len(estudantes_processados)} estudantes"
        )

        print(
            f"Curso {codigo_curso} | "
            f"Página {pagina} | "
            f"{len(estudantes_processados)} estudantes"
        )

        pagina += 1

    return estudantes


# CRIAR TABELA

def criar_tabela():

    with sqlite3.connect(DB_PATH) as conn:

        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABELA} (

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
                periodo_de_ingresso REAL,

                nacionalidade TEXT,
                local_de_nascimento TEXT,
                naturalidade TEXT,
                cor TEXT,

                deficiencias TEXT,

                ano_de_conclusao_ensino_medio INTEGER,
                tipo_de_ensino_medio TEXT,

                politica_afirmativa TEXT,
                renda_per_capita REAL,

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

                -- Índices acadêmicos
                mc REAL,
                iea REAL,
                ira REAL,
                mcn REAL,
                iean REAL,
                iech REAL,
                iepl REAL,
                iechp REAL,

                cotista TEXT,
                tem_deficiencia TEXT
            )
            """
        )

        conn.commit()


# SALVAR ESTUDANTES

def salvar_estudantes(estudantes):

    if not estudantes:
        return

    with sqlite3.connect(DB_PATH) as conn:

        # ----------------------------------------------------
        # IMPORTANTE:
        # usamos explicitamente as colunas da tabela.
        #
        # Isso evita que campos extras vindos da API,
        # como "indices_academicos", sejam inseridos.
        # ----------------------------------------------------

        colunas = [

            "matricula_do_estudante",

            "codigo_do_curso",
            "nome_do_curso",
            "turno_do_curso",

            "codigo_do_curriculo",

            "campus",
            "nome_do_campus",

            "codigo_do_setor",
            "nome_do_setor",

            "estado_civil",
            "sexo",
            "idade",

            "situacao",
            "motivo_de_evasao",
            "periodo_de_evasao",

            "forma_de_ingresso",
            "periodo_de_ingresso",

            "nacionalidade",
            "local_de_nascimento",
            "naturalidade",
            "cor",

            "deficiencias",

            "ano_de_conclusao_ensino_medio",
            "tipo_de_ensino_medio",

            "politica_afirmativa",
            "renda_per_capita",

            "creditos_do_cra",
            "notas_acumuladas",
            "periodos_completados",

            "creditos_tentados",
            "creditos_completados",
            "creditos_isentos",
            "creditos_falhados",
            "creditos_suspensos",
            "creditos_em_andamento",

            "velocidade_media",
            "taxa_de_sucesso",

            # Índices acadêmicos
            "mc",
            "iea",
            "ira",
            "mcn",
            "iean",
            "iech",
            "iepl",
            "iechp",

            "cotista",
            "tem_deficiencia"
        ]

        placeholders = ", ".join(
            "?" for _ in colunas
        )

        sql = f"""
            INSERT INTO {TABELA}
            ({", ".join(colunas)})
            VALUES ({placeholders})
        """

        valores = [
            tuple(
                estudante.get(coluna)
                for coluna in colunas
            )
            for estudante in estudantes
        ]

        conn.executemany(
            sql,
            valores
        )

        conn.commit()


# PRINCIPAL

def main():

    print(
        "========== DOWNLOAD DE ESTUDANTES =========="
    )

    criar_tabela()

    # --------------------------------------------------------
    # Buscar cursos pelo endpoint
    # --------------------------------------------------------

    try:

        response = requests.get(
            f"{URL_SIG}/cursos",
            params={
                "status": "ATIVOS"
            },
            timeout=60
        )

        response.raise_for_status()

        cursos = response.json()

    except Exception as e:

        logging.error(
            f"Erro ao buscar cursos: {e}"
        )

        print(
            f"Erro ao buscar cursos: {e}"
        )

        return

    print(
        f"{len(cursos)} cursos encontrados"
    )

    # --------------------------------------------------------
    # Processar cursos
    # --------------------------------------------------------

    with ThreadPoolExecutor(
        max_workers=MAX_THREADS
    ) as executor:

        futures = {
            executor.submit(
                buscar_estudantes,
                curso["codigo_do_curso"],
                URL_SIG
            ): curso
            for curso in cursos
        }

        for future in as_completed(futures):

            curso = futures[future]

            codigo = curso[
                "codigo_do_curso"
            ]

            try:

                estudantes = future.result()

                salvar_estudantes(
                    estudantes
                )

                print(
                    f"Curso {codigo} finalizado | "
                    f"{len(estudantes)} estudantes"
                )

            except Exception as e:

                logging.error(
                    f"Erro curso {codigo}: {e}"
                )

                print(
                    f"Erro curso {codigo}: {e}"
                )

if __name__ == "__main__":
    main()
