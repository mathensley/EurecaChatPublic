import requests, json, sqlite3
from datetime import datetime
from application.config import URL_SIG
from ..estudante.aux_estudantes_ufcg import get_estudantes_ufcg
from ..estudante.aux_estudante_norm import get_naturalidade, norm_sexo, get_cor


def extrair_ano(data_str):
    if not data_str: return None
    try: return datetime.strptime(data_str.split(" ")[0], "%Y-%m-%d").year
    except: return None


MAPEAMENTO_STATUS = {
    # RESCINDIDO
    "Termo rescindido": "RESCINDIDO",
    "RESCINDIDO": "RESCINDIDO",

    # CANCELADO
    "Plano cancelado": "CANCELADO",
    "SOLICITADO CANCELAMENTO": "CANCELADO",
    "CANCELADO": "CANCELADO",
    "NÃO COMPATÍVEL": "CANCELADO",

    # PENDENTE
    "Plano submetido (aguardando orientador)": "PENDENTE",
    "CADASTRO EM ANDAMENTO": "PENDENTE",
    "AGUARDANDO ASSINATURA": "PENDENTE",
    "AGUARDANDO APROVAÇÃO": "PENDENTE",

    # APROVADO
    "Plano aprovado orientador": "APROVADO",
    "Plano aprovado CPE/Centro": "APROVADO",

    # ATIVO
    "Termo celebrado": "ATIVO",
    "ATIVO": "ATIVO",

    # CONCLUIDO
    "CONCLUÍDO": "CONCLUIDO"
}


def aux_estagios(URL, periodo):
    estagios = []
    
    response = requests.get(f'{URL_SIG}/estagios')
    if response.status_code != 200: raise ValueError(str([{"error_status": response.status_code, "msg": "Não foi possível obter informação dos estágios da UFCG via SIGAA."}]))
    estagios += json.loads(response.text)
    
    for estagio in estagios:
        estagio["departamento"] = estagio.get("departamento", None) # Tirar essa linha quando a API do SIGAA trazer essa informação
        estagio["bolsa_mensal"] = estagio.get("bolsa_mensal", None) # Tirar essa linha quando a API do SIGAA trazer essa informação
        estagio["cidade_concedente"] = estagio.get("cidade_concedente", None) # Tirar essa linha quando a API do SIGAA trazer essa informação
        estagio["uf_concedente"] = get_naturalidade(estagio["uf_concedente"]) # Tirar essa linha quando a API do SIGAA trazer essa informação já normalizada
        estagio["auxilio_transporte_diario"] = estagio.get("auxilio_transporte_diario", None) # Tirar essa linha quando a API do SIGAA trazer essa informação
        estagio["cnpj"] = estagio.get("identificador", None) # Tirar essa linha quando a API do SIGAA trazer essa informação for trazida em /concedentes
        estagio["razao_social"] = estagio.get("razao_social", None) # Tirar essa linha quando a API do SIGAA trazer essa informação for trazida em /concedentes
        estagio["cidade_concedente"] = estagio.get("cidade_concedente", None) # Tirar essa linha quando a API do SIGAA trazer essa informação for trazida em /concedentes
        estagio["orgao_administracao_publica"] = estagio.get("orgao_administracao_publica", None) # Tirar essa linha quando a API do SIGAA trazer essa informação for trazida em /concedentes
        estagio["agente_integracao"] = estagio.get("agente_integracao", None) # Tirar essa linha quando a API do SIGAA trazer essa informação
    
    """
    convenios = {}
    response_convenios_sigaa = requests.get(f"{URL_SIG}/convenios-estagio")
    if response_convenios_sigaa.status_code == 200:
        convenios.update({c["id_concedente"]: c for c in json.loads(response_convenios_sigaa.text)})
    else:
        raise ValueError("Erro convenios SIGAA")

    
    concedentes = {}
    response_concedentes_sigaa = requests.get(f"{URL_SIG}/concedentes")
    if response_concedentes_sigaa.status_code == 200:
        concedentes.update({c["identificador"]: c for c in json.loads(response_concedentes_sigaa.text)})
    else: raise ValueError("Erro concedentes SIGAA")
    """

    estudantes = {c["matricula_do_estudante"]: c for c in get_estudantes_ufcg({})}
    
    for estagio in estagios:
        id_concedente = estagio.get("id_concedente")
        #convenio = convenios.get(id_concedente, {})
        #identificador = convenio.get("identificador")
        #concedente = concedentes.get(identificador, {})
        #estagio["cnpj"] = concedente.get("identificador", None)
        #estagio["razao_social"] = concedente.get("razao_social", None)
        #estagio["cidade_concedente"] = concedente.get("cidade_concedente", None)
        #estagio["orgao_administracao_publica"] = concedente.get("orgao_administracao_publica", None)
        estagio["status"] = MAPEAMENTO_STATUS.get(estagio["status"], None)
        estudante = estudantes.get(estagio.get("matricula_do_estudante"), {})
        estagio["codigo_do_curso"] = estudante.get("codigo_do_curso")
        estagio["nome_do_curso"] = estudante.get("nome_do_curso")
        estagio["campus"] = estudante.get("campus")
        estagio["nome_do_campus"] = estudante.get("nome_do_campus")
        estagio["sexo"] = norm_sexo(estudante.get("sexo"))
        estagio["cor"] = get_cor(estudante.get("cor"))
        estagio["idade"] = int(estudante.get("idade")) if estudante.get("idade") is not None else None
        estagio["mc"] = estudante.get("mc")
        inicio_estagio = estagio.get("inicio_vigencia")
        final_estagio = estagio.get("final_vigencia")
        inicio_estagio_date = inicio_estagio.split(" ")[0] if inicio_estagio else None
        final_estagio_date = final_estagio.split(" ")[0] if final_estagio else None
        estagio["inicio_vigencia"] = inicio_estagio_date
        estagio["final_vigencia"] = final_estagio_date
        estagio.pop("id_concedente", None)
        estagio.pop("codigo_da_disciplina", None)
        estagio.pop("id", None)
    
    tabela = "estagios_ufcg"
    conn_db_estagios = sqlite3.connect(f"{tabela}.sqlite")
    
    sql = f"""
    CREATE TABLE IF NOT EXISTS {tabela} (
        matricula_do_estudante TEXT,
        uf_concedente TEXT,
        matricula_do_docente INTEGER,
        departamento TEXT,
        nome_docente TEXT,
        obrigatorio BOOLEAN,
        inicio_vigencia TEXT,
        final_vigencia TEXT,
        carga_semanal INTEGER,
        status TEXT,
        agente_integracao TEXT,
        bolsa_mensal REAL,
        auxilio_transporte_diario REAL,
        cidade_concedente TEXT,
        cnpj TEXT,
        razao_social TEXT,
        orgao_administracao_publica BOOLEAN,
        codigo_do_curso INTEGER,
        nome_do_curso TEXT,
        campus INTEGER,
        nome_do_campus TEXT,
        sexo TEXT,
        cor TEXT,
        idade INTEGER,
        mc REAL
    );
    """
    
    campos_tabela = [
        "matricula_do_estudante",
        "uf_concedente",
        "matricula_do_docente",
        "departamento",
        "nome_docente",
        "obrigatorio",
        "inicio_vigencia",
        "final_vigencia",
        "carga_semanal",
        "status",
        "agente_integracao",
        "bolsa_mensal",
        "auxilio_transporte_diario",
        "cidade_concedente",
        "cnpj",
        "razao_social",
        "orgao_administracao_publica",
        "codigo_do_curso",
        "nome_do_curso",
        "campus",
        "nome_do_campus",
        "sexo",
        "cor",
        "idade",
        "mc"
    ]

    conn_db_estagios.execute(sql)
    conn_db_estagios.commit()
    print(estagios[0].keys())
    columns = ", ".join(campos_tabela)
    placeholders = ", ".join(["?"] * len(campos_tabela))
    command = f"""INSERT OR IGNORE INTO {tabela} ({columns}) VALUES ({placeholders});"""

    for estagio in estagios:
        valores = tuple(estagio.get(campo, None) for campo in campos_tabela)
        conn_db_estagios.execute(command, valores)
    conn_db_estagios.commit()


def get_todos_estagios(params):
    tabela = "estagios_ufcg"
    conn_db_estudante = sqlite3.connect(f"{tabela}.sqlite")
    conn_db_estudante.row_factory = sqlite3.Row
    cursor = conn_db_estudante.cursor()
    where = []
    values = []

    for key, value in params.items():
        if value != "":
            if key == "inicio-de":
                where.append(f"strftime('%Y', inicio_vigencia) >= '{value}'")
                
            if key == "fim-ate":
                where.append(f"strftime('%Y', final_vigencia) <= '{value}'")
            
            if key == "codigo_do_curso":
                where.append(f"codigo_do_curso={value}")

            if key == "campus":
                where.append(f"campus={value}")


    query = f"SELECT * FROM {tabela} WHERE {' AND '.join(where)}" if where else f"SELECT * FROM {tabela}"
    print(query)
    cursor.execute(query, values)
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


if __name__ == "__main__":
    aux_estagios(URL_SIG, None)
    print(len(get_todos_estagios({})))