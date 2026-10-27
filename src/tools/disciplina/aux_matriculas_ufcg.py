import os, requests, json, sqlite3
from ..estudante.aux_estudantes_ufcg import get_estudantes_ufcg

from application.config import URL_BASE, URL_SIG

SQLITE_DIR = os.getenv("SQLITE_DIR", ".")
TABELA = "matriculas_ufcg"
DB_PATH = os.path.join(SQLITE_DIR, f"{TABELA}.sqlite")


def aux_matriculas_ufcg(URL, periodo):
    #tabela = "matriculas_ufcg"
    conn_db_estudante = sqlite3.connect(DB_PATH)
    estudantes = get_estudantes_ufcg({})
    print(len(estudantes))

    estudantes = {estudante["matricula_do_estudante"]: estudante for estudante in estudantes}

    sql = f"""
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
    
    conn_db_estudante.execute(sql)
    conn_db_estudante.commit()
    
    if URL == URL_BASE: # Se usar URL_BASE fazer chamada por URL_BASE seguido de URL_SIG.
        conn_db_estudante.execute(f"DELETE FROM {TABELA}")
        conn_db_estudante.commit()
    
    req_cursos = requests.get(f"{URL}/cursos", params={"status": "ATIVOS"})
    if req_cursos.status_code == 200:
        dados_cursos = json.loads(req_cursos.content)

        for curso in dados_cursos:
            req_matriculas_curso = requests.get(f"{URL}/matriculas", params={"curso": curso["codigo_do_curso"]}, timeout=3600)
            if req_matriculas_curso.status_code == 200:
                matricula_estudantes = json.loads(req_matriculas_curso.text)
                todos_os_campos = {**next(iter(estudantes.values())), **matricula_estudantes[0]}
                columns = ", ".join(todos_os_campos.keys())
                placeholders = ", ".join(["?"] * len(todos_os_campos))
                command = f"INSERT OR IGNORE INTO {TABELA} ({columns}) VALUES ({placeholders});"
                
                for matricula in matricula_estudantes:
                    matricula = {k: ", ".join(v) if isinstance(v, list) else v for k, v in matricula.items() }
                    matricula = {**estudantes.get(matricula["matricula_do_estudante"], {}), **matricula}
                    print(matricula)
                    conn_db_estudante.execute(command, tuple(matricula.values()))
                conn_db_estudante.commit()
            
            else:
                print(f"Erro ao buscar estudantes do curso {curso['codigo_do_curso']}: {req_matriculas_curso.status_code}")
    
    else:
        print(f"Erro ao buscar cursos: {req_cursos.status_code}")
    
    conn_db_estudante.close()


def get_matriculas_ufcg(params):
    #tabela = "matriculas_ufcg"
    conn_db_estudante = sqlite3.connect(DB_PATH)
    conn_db_estudante.row_factory = sqlite3.Row
    cursor = conn_db_estudante.cursor()
    where = []
    values = []
    keys = params.keys()
        
    for key, value in params.items():
        if value != "":
            if key == "periodo-de":
                where.append(f"periodo>='{value}'")
            
            if key == "periodo-ate":
                where.append(f"periodo<='{value}'")

            if key == "disciplina":
                where.append(f"codigo_da_disciplina={value}")
            
            if key == "curso" and not "disciplina" in keys:
            #if key == "curso":
                where.append(f"codigo_do_curso='{value}'")
            
            if key == "campus":
                where.append(f"campus='{value}'")
            
            if key == "turma":
                where.append(f"turma={value}")

            if key == "codigo_do_setor":
                where.append(f"codigo_do_setor={value}")
    
    query = f"SELECT * FROM {TABELA} WHERE " + " AND ".join(where) if where else f"SELECT * FROM {TABELA}"

    print(query)

    cursor.execute(query, values)
    rows = cursor.fetchall()
    matriculas = [dict(row) for row in rows]
    return matriculas


if __name__ == "__main__":
    aux_matriculas_ufcg(URL_SIG, None)