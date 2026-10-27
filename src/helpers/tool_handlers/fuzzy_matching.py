import unicodedata, re
from rapidfuzz import process, fuzz

def roman_to_int(match):
    ROMAN_MAP = {
        "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5,
        "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10
    }
    roman = match.group(0).lower()
    return str(ROMAN_MAP[roman])

def normalize_txt(txt):
    txt = "".join(
        c for c in unicodedata.normalize("NFD", txt.lower())
        if unicodedata.category(c) != "Mn"
    )

    txt = re.sub(
        r"\b(i|ii|iii|iv|v|vi|vii|viii|ix|x)\b",
        roman_to_int,
        txt
    )

    txt = re.sub(r"[^a-z0-9\s]", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()

    return txt

def format_course_results(matches: list[tuple[dict, float]]) -> list[dict]:
    """
    Formata os resultados da busca de cursos.
    
    - Se houver mais de um candidato, retorna lista resumida com apenas código, descrição, turno, modalidade e similaridade.
    - Se houver apenas um candidato, retorna lista com o curso completo (sem incluir a similaridade).

    Args:
        matches (list[tuple[dict, float]]): Lista de tuplas contendo (curso_dict, score_de_similaridade).

    Returns:
        list[dict]: Lista formatada conforme regra descrita acima.
    """

    if not matches:
        return []
    
    if len(matches) > 1:
        resultado = [
            {
                "codigo_do_curso": c.get("codigo_do_curso"),
                "descricao": c.get("descricao"),
                "nome_do_campus": c.get("nome_do_campus"),
                "turno": c.get("turno"),
                "modalidade_academica": c.get("modalidade_academica"),
                "similaridade": score
            }
            for c, score in matches
        ]
        if len(resultado) > 1:
            tops = "\n".join(f"- {x['descricao']}, Código do curso: {x.get('codigo_do_curso')}, Campus: {x.get('nome_do_campus', '')}" for x in resultado)
            texto_adicional = "Se você achar que algum destes itens é o correto, então chame essa ferramenta novamente fornecendo o nome correto e outros parâmetros necessários. Caso não encontre alguma similar o bastante, pergunte ao usuário."
            raise ValueError(f"Nenhum item semelhante encontrado.\nTermos mais próximos encontrados:\n\n{tops}\n\n{texto_adicional}")
    curso, _ = matches[0]
    return [curso]

def format_subject_results(matches: list[tuple[dict, float]]) -> list[dict]:
    """
    Formata os resultados da busca de disciplinas.

    - Se houver mais de um candidato, retorna lista resumida com apenas código, nome, nome do setor e similaridade.
    - Se houver apenas um candidato, retorna lista com a disciplina completa (sem incluir a similaridade).

    Args:
        matches (list[tuple[dict, float]]): Lista de tuplas contendo (disciplina_dict, score_de_similaridade).

    Returns:
        list[dict]: Lista formatada conforme regra descrita acima.
    """

    if not matches:
        return []
    
    if len(matches) > 1:
        return [
            {
                "codigo_da_disciplina": c.get("codigo_da_disciplina"),
                "nome": c.get("nome"),
                "nome_do_setor": c.get("nome_do_setor"),
                "similaridade": score
            }
            for c, score in matches
        ]
    disciplina, _ = matches[0]
    return [disciplina]

def format_setor_results(matches: list[tuple[dict, float]]) -> list[dict]:
    """
    Formata os resultados da busca de setores.

    - Se houver mais de um candidato, retorna lista resumida com apenas código, nome, nome do setor e similaridade.
    - Se houver apenas um candidato, retorna lista com a disciplina completa (sem incluir a similaridade).

    Args:
        matches (list[tuple[dict, float]]): Lista de tuplas contendo (disciplina_dict, score_de_similaridade).

    Returns:
        list[dict]: Lista formatada conforme regra descrita acima.
    """

    if not matches:
        return []
    
    if len(matches) > 1:
        return [
            {
                "codigo_do_setor": c.get("codigo_do_setor"),
                "descricao": c.get("descricao"),
                "similaridade": score
            }
            for c, score in matches
        ]
    setor, _ = matches[0]
    return [setor]


def extract_most_similar(
        query_text: str,
        items: list[dict],
        field: str,
        tie_break_threshold: float = 2.0,
        top_k: int = 10,
        min_similarity: float = 70.0
) -> list[tuple[dict, float]]:
    """
    Retorna os itens mais semelhantes a um texto de consulta com base em comparação aproximada de strings (fuzzy matching).

    Args:
        query_text (str): Texto de entrada a ser comparado.
        items (list[dict]): Lista de objetos (dicionários) a serem buscados.
        field (str): Nome do atributo (chave do dicionário) usado para comparação.
        tie_break_threshold (float, optional): Diferença máxima de score em relação ao melhor resultado para considerar empate.
        top_k (int, optional): Número máximo de candidatos a retornar antes da aplicação do critério de desempate.
        min_similarity (float, optional): Similaridade mínima aceitável para considerar uma correspondência válida.
    
    Returns:
        list[tuple[dict, float]]: Lista de tuplas contendo:
            - O objeto original (dict) correspondente
            - O score de similaridade (float)
    
    Raises:
        ValueError: Se nenhuma correspondência tiver similaridade suficiente.
    """
    
    query = normalize_txt(query_text)
    list_norm = [normalize_txt(obj[field]) for obj in items]
    #print("\nTARGET: ", query)
    
    matches = process.extract(query, list_norm, limit=top_k, scorer=fuzz.token_set_ratio)
    #print("\nMATCHES ENCONTRADOS: ", matches)
    
    if not matches: return []
    best_score = matches[0][1]

    if best_score < min_similarity:
        tops = "\n".join(f"- {items[idx][field]}" for _, _, idx in matches[:top_k])
        texto_adicional = "Se você achar que algum destes itens é o correto, então chame essa ferramenta novamente fornecendo o nome correto e outros parâmetros necessários. Caso não encontre alguma similar o bastante, pergunte ao usuário."
        raise ValueError(f"Nenhum item semelhante encontrado.\nTermos mais próximos encontrados:\n\n{tops}\n\n{texto_adicional}")

    possibles = [m for m in matches if best_score - m[1] <= tie_break_threshold]
    return [(items[idx], score) for _, score, idx in possibles]
