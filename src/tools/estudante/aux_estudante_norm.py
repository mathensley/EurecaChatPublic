import re

def eh_cotista(cota):
    if cota is None: return "NAO"
    c = (cota or "").strip().lower()
    nao_cotista = ["", "-", "bon. estudual", "nenhum", "nao informado"]
    return "NAO" if c in nao_cotista else "SIM"

def norm_sexo(sexo):    
    tipo_sexo = {"M": "MASCULINO", "F": "FEMININO"}
    return tipo_sexo.get(sexo, sexo)


def get_nacionalidade(nacionalidade):
    if nacionalidade is None: return None
    nacionalidades = {
        "brasileira": "BRASILEIRO",
        "bestrangeira": "ESTRANGEIRO"
    }
    return nacionalidades.get(nacionalidade.lower(), nacionalidade)


def get_naturalidade(naturalidade):
    naturalidades = {
        "AC": "Acre",
        "AL": "Alagoas",
        "AP": "Amapá",
        "AM": "Amazonas",
        "BA": "Bahia",
        "CE": "Ceará",
        "DF": "Distrito Federal",
        "ES": "Espírito Santo",
        "GO": "Goiás",
        "MA": "Maranhão",
        "MT": "Mato Grosso",
        "MS": "Mato Grosso do Sul",
        "MG": "Minas Gerais",
        "PA": "Pará",
        "PB": "Paraíba",
        "PR": "Paraná",
        "PE": "Pernambuco",
        "PI": "Piauí",
        "RJ": "Rio de Janeiro",
        "RN": "Rio Grande do Norte",
        "RS": "Rio Grande do Sul",
        "RO": "Rondônia",
        "RR": "Roraima",
        "SC": "Santa Catarina",
        "SP": "São Paulo",
        "SE": "Sergipe",
        "TO": "Tocantins"
    }
    
    naturalidades = {v: k for k, v in naturalidades.items()}
    return naturalidades.get(naturalidade, naturalidade)


def get_cor(cor):
    cores = {
        "Preta": "Preto",
        "Parda": "Pardo",
        "Branca": "Branco",
        "Indigena": "Indigeno",
        "Amarela": "Amarelo"
    }
    return cores.get(cor, cor)


def get_curriculo(curriculo):
    codigo = curriculo or ""
    match = re.match(r"(\d{4})", str(codigo))
    return int(match.group(1)) if match else 0


def estudante_norm(estudante):
    estudante["codigo_do_curriculo"] = int(get_curriculo(estudante["codigo_do_curriculo"]))
    estudante["idade"] = int(estudante["idade"]) if (type(estudante["idade"]) == str or type(estudante["idade"])) == int else None
    estudante["cotista"] = eh_cotista(estudante["politica_afirmativa"])
    estudante["nome_do_campus"] = estudante["nome_do_campus"].title()
    estudante["sexo"] = norm_sexo(estudante["sexo"])
    estudante["periodo_de_ingresso"] = float(estudante["periodo_de_ingresso"])
    estudante["ano_de_conclusao_ensino_medio"] = int(estudante["ano_de_conclusao_ensino_medio"])
    estudante["nacionalidade"] = get_nacionalidade(estudante["nacionalidade"])
    estudante["naturalidade"] = get_naturalidade(estudante["naturalidade"])
    estudante["estado_civil"] = estudante["estado_civil"] = re.sub("\(.*$", "", str(estudante.get("estado_civil") or "")).strip()
    estudante["nome_do_campus"] = estudante["nome_do_campus"].title()
    estudante["cor"] = get_cor(estudante["cor"])
    estudante["tem_deficiencia"] =  "nao" if (estudante.get("deficiencias") == None or estudante.get("deficiencias") == "") else 'sim'
    
    nacionalidade = estudante["nacionalidade"]
    estudante["nacionalidade"] = "brasileiro" if nacionalidade and nacionalidade.strip().lower() in ("rio de janeiro", "brasil", "campina grande", "nrasileira") else nacionalidade

    return estudante