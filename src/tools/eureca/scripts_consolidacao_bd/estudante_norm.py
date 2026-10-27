import re


def eh_cotista(cota):
    if cota is None:
        return "NAO"

    c = (cota or "").strip().lower()

    nao_cotista = [
        "",
        "-",
        "bon. estudual",
        "nenhum",
        "nao informado"
    ]

    return "NAO" if c in nao_cotista else "SIM"


def norm_sexo(sexo):
    tipo_sexo = {
        "M": "MASCULINO",
        "F": "FEMININO"
    }

    return tipo_sexo.get(sexo, sexo)


def get_nacionalidade(nacionalidade):
    if nacionalidade is None:
        return None

    nacionalidades = {
        "brasileira": "BRASILEIRO",
        "bestrangeira": "ESTRANGEIRO"
    }

    return nacionalidades.get(
        nacionalidade.lower(),
        nacionalidade
    )


def get_naturalidade(naturalidade):
    if naturalidade is None:
        return None

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

    naturalidades = {
        v: k for k, v in naturalidades.items()
    }

    return naturalidades.get(
        naturalidade,
        naturalidade
    )


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
    if curriculo is None:
        return None

    codigo = str(curriculo)

    match = re.match(r"(\d{4})", codigo)

    return int(match.group(1)) if match else None


def estudante_norm(estudante):

    estudante["codigo_do_curriculo"] = get_curriculo(
        estudante.get("codigo_do_curriculo")
    )

    idade = estudante.get("idade")

    if idade is not None:
        try:
            estudante["idade"] = int(idade)
        except (ValueError, TypeError):
            estudante["idade"] = None
    else:
        estudante["idade"] = None

    estudante["cotista"] = eh_cotista(
        estudante.get("politica_afirmativa")
    )

    estudante["nome_do_campus"] = (
        estudante.get("nome_do_campus") or ""
    ).title()

    estudante["sexo"] = norm_sexo(
        estudante.get("sexo")
    )

    periodo = estudante.get("periodo_de_ingresso")

    if periodo is not None:
        try:
            estudante["periodo_de_ingresso"] = float(periodo)
        except (ValueError, TypeError):
            estudante["periodo_de_ingresso"] = None
    else:
        estudante["periodo_de_ingresso"] = None

    ano = estudante.get("ano_de_conclusao_ensino_medio")

    if ano is not None:
        try:
            estudante["ano_de_conclusao_ensino_medio"] = int(ano)
        except (ValueError, TypeError):
            estudante["ano_de_conclusao_ensino_medio"] = None
    else:
        estudante["ano_de_conclusao_ensino_medio"] = None

    estudante["nacionalidade"] = get_nacionalidade(
        estudante.get("nacionalidade")
    )

    estudante["naturalidade"] = get_naturalidade(
        estudante.get("naturalidade")
    )

    estudante["estado_civil"] = re.sub(
        r"(.\*$)",
        "",
        str(estudante.get("estado_civil") or "")
    ).strip()

    estudante["nome_do_campus"] = (
        estudante.get("nome_do_campus") or ""
    ).title()

    estudante["cor"] = get_cor(
        estudante.get("cor")
    )

    estudante["tem_deficiencia"] = (
        "nao"
        if estudante.get("deficiencias") in (None, "")
        else "sim"
    )

    nacionalidade = estudante.get("nacionalidade")

    estudante["nacionalidade"] = (
        "brasileiro"
        if nacionalidade
        and nacionalidade.strip().lower()
        in (
            "rio de janeiro",
            "brasil",
            "campina grande",
            "nrasileira"
        )
        else nacionalidade
    )

    return estudante