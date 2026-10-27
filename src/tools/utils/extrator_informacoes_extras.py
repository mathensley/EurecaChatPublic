from ...helpers.tool_handlers.fuzzy_matching import extract_most_similar
from ..utils.extrair_colunas_where import extrair_colunas_where, extrair_valores_where


def extrator_informacoes_extras(sql, colunas_comparaveis, dados_filtrados):
    resultado = None

    try:
        if not sql:
            return None

        colunas_extraidas = extrair_colunas_where(sql)
        comparacoes_where = extrair_valores_where(sql)
        similaridade_em = ["local_de_nascimento", "nome_do_estudante", "nome_do_professor"]

        outros_dados = {coluna: set() for coluna in colunas_extraidas if coluna in colunas_comparaveis}
        for dado in dados_filtrados:
            for coluna in outros_dados:
                valor = dado.get(coluna)
                if valor is not None:
                    outros_dados[coluna].add(valor)


        for coluna in similaridade_em:
            if coluna not in colunas_extraidas: continue
            valor_pesquisado = ", ".join(comparacoes_where[coluna])
            valores_dados = [{"key": x} for x in list(outros_dados[coluna])]
            similares = extract_most_similar(valor_pesquisado, valores_dados, "key", min_similarity=0.005, tie_break_threshold=40)
            outros_dados[coluna] = [x[0]["key"] for x in similares[:10]]
        
        for coluna, valores in outros_dados.items():
            if isinstance(valores, set):
                outros_dados[coluna] = sorted(valores)[:10]
        
        if any(outros_dados.values()):
            informacoes = "\n".join(
                f"{coluna}: {', '.join(repr(valor) for valor in sorted(valores))}"
                for coluna, valores in outros_dados.items()
                if valores
            )

            resultado = f"""
            Além disso, há outros dados como:

            {informacoes}

            Observando as informações extras, se o SQL foi gerado errado ou quiser algumas dessas informações, você deve solicitar na query colocando o(s) valor(es) entre aspas junto a pergunta feita anteriormente na query.
            Caso o SQL tenha sido feito de forma correta, então ignore essa informação extra.
            """
    except Exception as e:
        pass
    
    return resultado
