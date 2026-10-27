import os, requests, json, sqlite3

from application.config import URL_BASE, URL_SIG
from .aux_estudante_norm import estudante_norm

SQLITE_DIR = os.getenv("SQLITE_DIR", ".")
TABELA = "estudantes_ufcg"
DB_PATH = os.path.join(SQLITE_DIR, f"{TABELA}.sqlite")


def get_periodos_calendarios():
    calendarios = []
    req_resp = requests.get(f"{URL_BASE}/calendarios")
    if req_resp.status_code == 200:
        calendarios += json.loads(req_resp.text)

    req_resp = requests.get(f"{URL_SIG}calendarios")
    if req_resp.status_code == 200:
        calendarios += json.loads(req_resp.text)
    
    todos_periodos = [str(x) for x in sorted(set(
        [float(calendario["periodo"]) for calendario in calendarios]
          + [1975.1, 1975.2, 1976.1, 1976.2, 1977.1, 1977.2, 1978.1, 1978.2, 1979.1, 1979.2, 
             1980.1, 1980.2, 1981.1, 1981.2, 1982.1, 1982.2, 1983.1, 1983.2, 1984.1, 1984.2, 1985.1, 1985.2, 1986.1, 1986.2, 1987.1, 1987.2, 1988.1, 1988.2, 1989.1, 1989.2,
             1990.1, 1990.2, 1991.1, 1991.2, 1992.1, 1992.2, 1993.1, 1993.2, 1994.1, 1994.2, 1995.1, 1995.2, 1996.1, 1996.2, 1997.1, 1997.2, 1998.1, 1998.2, 1999.1, 1999.2, 
             2000.1, 2000.2, 2001.1, 2001.2, 2002.1, 2002.2, 2003.1, 2003.2]))]
    
    return todos_periodos


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
    "renda_per_capita"
]


def aux_estudantes_ufcg(URL, periodo):
    #tabela = "estudantes_ufcg"
    conn_db_estudante = sqlite3.connect(DB_PATH)
    
    
    sql = f"""
        CREATE TABLE IF NOT EXISTS {TABELA} (
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
        tem_deficiencia TEXT,
        cotista TEXT
    );
    """
    conn_db_estudante.execute(sql)
    conn_db_estudante.commit()

    todos_periodos = get_periodos_calendarios()
    
    if URL == URL_BASE:
        conn_db_estudante.execute(f"DELETE FROM {TABELA}")
        conn_db_estudante.commit()
    
    req_cursos = requests.get(f"{URL}/cursos")
    if req_cursos.status_code == 200:
        dados_cursos = json.loads(req_cursos.content)

        for curso in dados_cursos:
            req_estudantes_curso = requests.get(f"{URL}estudantes", params={"curso": curso["codigo_do_curso"]})
            print(req_estudantes_curso.url)
            if req_estudantes_curso.status_code == 200:
                dados_estudantes = json.loads(req_estudantes_curso.content)
                
                estudante_copy = dados_estudantes[0].copy()
                estudante_copy["idade"] = 0
                estudante_copy["codigo_do_curriculo"] = 0
                estudante_copy["ano_de_conclusao_ensino_medio"] = 0
                estudante_copy["prac_renda_per_capita_ate"] = 0
                estudante_copy["renda_per_capita_ate"] = 0
                estudante_copy["mc"] = 0.0001
                estudante_copy["tem_deficiencia"] = None
                estudante_copy["cotista"] = None
                estudante_copy = {k: v for k, v in estudante_copy.items() if k not in keys_to_remove}
                
                columns = ", ".join(estudante_copy.keys())
                placeholders = ", ".join(["?"] * len(estudante_copy.keys()))
                command = f"INSERT OR IGNORE INTO {TABELA} ({columns}) VALUES ({placeholders});"
                
                for estudante in dados_estudantes:
                    estudante["idade"] = int(estudante.get("idade") or 0)
                    estudante["codigo_do_curriculo"] = estudante.get("codigo_do_curriculo")
                    estudante["ano_de_conclusao_ensino_medio"] = int(estudante.get("ano_de_conclusao_ensino_medio") or 0)
                    estudante["prac_renda_per_capita_ate"] = (estudante.get("renda_per_capita") or 0) / 1528
                    estudante["renda_per_capita_ate"] = float(estudante.get("prac_renda_per_capita") or 0)
                    estudante["mc"] = estudante.get("notas_acumuladas", 0.0001) / (estudante.get("creditos_do_cra", 1) or 1)
                    estudante["tem_deficiencia"] = "sim" if (estudante.get("deficiencias") != None or estudante.get("deficiencias") != "") else 'nao'
                    
                    """
                    if (estudante.get("situacao", "--").lower() not in ["ativo", "ativo - formando"]):
                        indice_ingresso = todos_periodos.index(estudante["periodo_de_ingresso"])
                        indice_final = indice_ingresso + estudante["periodos_completados"] - 1
                        if indice_final < len(todos_periodos):
                            estudante["periodo_de_evasao"] = todos_periodos[indice_final]
                        else:
                            estudante["periodo_de_evasao"] = None
                    """

                    for key in keys_to_remove: estudante.pop(key, None)
                    estudante = {k: ", ".join(v) if isinstance(v, list) else v for k, v in estudante.items() }
                    estudante = estudante_norm(estudante)
                    conn_db_estudante.execute(command, tuple(estudante.values()))
                conn_db_estudante.commit()
                
            else:
                print(f"Erro ao buscar estudantes do curso {curso['codigo_do_curso']}: {req_estudantes_curso.status_code}")
    
    else:
        print(f"Erro ao buscar cursos: {req_cursos.status_code}")
    
    conn_db_estudante.close()


def get_estudantes_ufcg(params):
    #tabela = "estudantes_ufcg"
    conn_db_estudante = sqlite3.connect(DB_PATH)

    
    conn_db_estudante.row_factory = sqlite3.Row
    cursor = conn_db_estudante.cursor()
    where = []
    values = []

    for key, value in params.items():
        if value != "":
            if key == "situacao-do-estudante":
                where.append(f"situacao='ATIVO'" if value == "ATIVOS" else f"situacao!='ATIVO'")
                
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


    query = f"SELECT * FROM {TABELA} WHERE {' AND '.join(where)}" if where else f"SELECT * FROM {TABELA}"
    print(query)
    cursor.execute(query, values)
    rows = cursor.fetchall()
    estudantes = [dict(row) for row in rows]
    return estudantes


def get_estudantes_gerais_ufcg(params):
    #tabela = "estudantes_ufcg"
    conn_db_estudante = sqlite3.connect(DB_PATH)
    conn_db_estudante.row_factory = sqlite3.Row
    cursor = conn_db_estudante.cursor()
    where = []
    values = []

    for key, value in params.items():
        if value != "":
            """
            if key == "situacao-do-estudante":
                if value == "ATIVOS":
                    where.append(f"situacao LIKE 'ATIVO%'")
                elif value == "INATIVOS":
                    where.append(f"situacao NOT LIKE 'ATIVO%'")
            """
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

            if key == "codigo_do_setor":
                where.append(f"codigo_do_setor={value}")


    query = f"SELECT * FROM {TABELA} WHERE {' AND '.join(where)}" if where else f"SELECT * FROM {TABELA}"
    print(query)
    cursor.execute(query, values)
    rows = cursor.fetchall()
    estudantes = [dict(row) for row in rows]
    return estudantes


if __name__ == "__main__":
    aux_estudantes_ufcg(URL_SIG, None)
    #print(len([estudante for estudante in get_estudantes_ufcg({"situacao-do-estudante":"ATIVOS"}) if estudante["idade"] >10]))
    #print(get_periodos_calendarios())