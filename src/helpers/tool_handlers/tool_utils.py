import difflib, re, unicodedata

from .siglas import SIGLAS

def merge_disciplina_data(disciplina_data: dict, curriculo_data: dict) -> dict:
    """
    Faz a união entre os dados da disciplina e os dados do currículo.
    Com remoção de valores nulos e do código do curso.
    """
    resultado = {k: v for k, v in disciplina_data.items() if v is not None}

    for k, v in curriculo_data.items():
        if k == "codigo_do_curso" or v is None:
            continue
        if k not in resultado:
            resultado[k] = v
    return resultado

def merge_lista_disciplinas(disciplinas_gerais: list[dict], disciplinas_curriculo: list[dict]) -> list[dict]:
    """
    Faz o merge entre duas listas de disciplinas (vindo de /disciplinas e /disciplinas-por-curriculo), unindo os dados apenas quando ambas têm o mesmo código de disciplina.

    Retorna uma lista de disciplinas completas.
    """

    mapa_curriculo = {
        str(d.get("codigo_da_disciplina")): d
        for d in disciplinas_curriculo
        if "codigo_da_disciplina" in d
    }

    disciplinas_final = []

    for disc in disciplinas_gerais:
        codigo = str(disc.get("codigo_da_disciplina"))
        if codigo in mapa_curriculo:
            merged = merge_disciplina_data(disc, mapa_curriculo[codigo])
            disciplinas_final.append(merged)
        else:
            disciplinas_final.append(disc)

    return disciplinas_final

def formatar_fluxo_disciplinas(disciplinas: list[dict]) -> str:
    """
    Formata a lista de disciplinas em formato textual organizado por semestre,
    incluindo no final a contagem total de disciplinas.
    """

    if not disciplinas:
        return "Nenhuma disciplina encontrada."

    fluxograma = {}
    optativas = []
    complementares = []

    for disc in disciplinas:
        semestre = disc.get("semestre_ideal")
        tipo = (disc.get("tipo") or "").upper()

        if tipo == "COMPLEMENTAR":
            complementares.append(disc)
        elif tipo == "OPTATIVO":
            optativas.append(disc)
        elif semestre in [None, "0", 0]:
            optativas.append(disc)
        else:
            fluxograma.setdefault(str(semestre), []).append(disc)

    semestres_ordenados = sorted(fluxograma.keys(), key=lambda x: int(x))

    linhas = []
    linhas.append("## **Fluxograma de Disciplinas do Curso**\n")

    total_obrigatorias = 0

    for semestre in semestres_ordenados:
        linhas.append(f"\n### **{semestre}º Semestre**\n")
        linhas.append(
            "| Disciplina | Código | Créditos | Carga Horária | Setor | Tipo | Pré-requisito |\n"
            "|------------|--------|----------|----------------|--------|--------|----------------|\n"
        )

        for disc in fluxograma[semestre]:
            nome = disc.get("nome", "-")
            codigo = disc.get("codigo_da_disciplina", "-")
            creditos = disc.get("quantidade_de_creditos", "-")
            horas = disc.get("horas_totais", "-")
            setor = disc.get("nome_do_setor", "-")
            tipo = disc.get("tipo", "-")
            prereq = limpar_prerequisitos(disc.get("pre_requisitos", ""))

            linhas.append(
                f"| {nome} | {codigo} | {creditos} | {horas}h | {setor} | {tipo} | {prereq} |\n"
            )

            total_obrigatorias += 1

    total_opt = len(optativas)

    if optativas:
        linhas.append("\n## **Disciplinas Optativas**\n")
        linhas.append(
            "| Disciplina | Código | Créditos | Carga Horária | Setor | Tipo | Pré-requisito |\n"
            "|------------|--------|----------|----------------|--------|--------|----------------|\n"
        )

        for disc in optativas:
            nome = disc.get("nome", "-")
            codigo = disc.get("codigo_da_disciplina", "-")
            creditos = disc.get("quantidade_de_creditos", "-")
            horas = disc.get("horas_totais", "-")
            setor = disc.get("nome_do_setor", "-")
            tipo = disc.get("tipo", "-")
            prereq = limpar_prerequisitos(disc.get("pre_requisitos", ""))

            linhas.append(
                f"| {nome} | {codigo} | {creditos} | {horas}h | {setor} | {tipo} | {prereq} |\n"
            )

    total_comp = len(complementares)

    if complementares:
        linhas.append("\n## **Disciplinas Complementares**\n")
        linhas.append(
            "| Disciplina | Código | Créditos | Carga Horária | Setor | Tipo | Pré-requisito |\n"
            "|------------|--------|----------|----------------|--------|--------|----------------|\n"
        )

        for disc in complementares:
            nome = disc.get("nome", "-")
            codigo = disc.get("codigo_da_disciplina", "-")
            creditos = disc.get("quantidade_de_creditos", "-")
            horas = disc.get("horas_totais", "-")
            setor = disc.get("nome_do_setor", "-")
            tipo = disc.get("tipo", "-")
            prereq = limpar_prerequisitos(disc.get("pre_requisitos", ""))

            linhas.append(
                f"| {nome} | {codigo} | {creditos} | {horas}h | {setor} | {tipo} | {prereq} |\n"
            )
    
    total_geral = total_obrigatorias + total_opt + total_comp
    curriculo = disciplinas[-1].get("codigo_do_curriculo", "-")

    linhas.append("\n---\n")
    linhas.append("## **Resumo Geral**\n")
    linhas.append(f"- **Total:** {total_geral} disciplinas\n")
    linhas.append(f"- **Obrigatórias:** {total_obrigatorias}\n")
    linhas.append(f"- **Optativas:** {total_opt}\n")
    linhas.append(f"- **Complementares:** {total_comp}\n")
    linhas.append(f"- **Currículo utilizado:** {curriculo}\n")

    return "".join(linhas)

def limpar_prerequisitos(valor: str) -> str:
    if not valor:
        return "Não possui"

    texto = valor.strip()
    texto = re.sub(r'(?i)pré[\s-]*requisitos?:\s*', '', texto)
    texto = texto.replace("[", "").replace("]", "")
    texto = texto.strip()

    return texto if texto else "Não possui"

def validar_turma(turma_usada: str):
    if (turma_usada.isdigit() and int(turma_usada) >= 1 and int(turma_usada) <= 20) or turma_usada == "": 
        return True, ""
    return False, f"Turma inválida. A turma precisa ser um valor númerico entre 1 a 20. O padrão é vazio '' (caso você escolha o padrão, você deve informar ao usuário da sua escolha relatando o problema)."

def get_most_similar_acronym(sigla: str, context: str):
    """
    Função que utiliza difflib para encontrar a sigla mais similar à sigla informada.

    Args:
        sigla: sigla desejada.
        context: Contexto da sigla, pode ser disciplina, curso etc. Por exemplo se o contexto informado for 'disciplina' então as siglas a serem consideradas serão as siglas das disciplinas que estão no arquivo json siglas.
    
    Returns:
            Sigla original ou nome por extenso da sigla mais próxima à desejada. Ex: se for 'fm cc 2', a função retornará 'fundamentos de matemática para ciência da computação 2'.
    
    Observação:
        Caso a sigla não tenha correspondência no arquivo json então a sigla orginal que foi passado para o parâmetro da função é o que será retornado.
    """
    
    if not SIGLAS:
        return sigla

    if context not in SIGLAS:
        return sigla

    sigla_copia = sigla
    sigla = sigla.upper().strip()
    lista_siglas = list(SIGLAS[context].keys())

    most_similar = difflib.get_close_matches(sigla, lista_siglas, n=1, cutoff=0.7)

    return SIGLAS[context][most_similar[0]] if most_similar else sigla_copia

def remover_acentos(texto: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')