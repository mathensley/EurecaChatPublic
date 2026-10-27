import sqlglot
from sqlglot import exp


def extrair_colunas_where(sql):
    tree = sqlglot.parse_one(sql)

    colunas = []

    for where in tree.find_all(exp.Where):
        for coluna in where.find_all(exp.Column):
            colunas.append(coluna.name)

    # Remove duplicatas preservando a ordem
    return list(dict.fromkeys(colunas))


def extrair_valores_where(sql):
    tree = sqlglot.parse_one(sql)

    resultado = {}

    # igualdade (=)
    for node in tree.find_all(exp.EQ):
        if isinstance(node.left, exp.Column):
            if isinstance(node.right, exp.Literal):
                resultado.setdefault(node.left.name, []).append(node.right.this)

    # LIKE
    for node in tree.find_all(exp.Like):
        if isinstance(node.this, exp.Column):
            if isinstance(node.expression, exp.Literal):
                resultado.setdefault(node.this.name, []).append(node.expression.this)

    # IN (...)
    for node in tree.find_all(exp.In):
        if isinstance(node.this, exp.Column):
            valores = []

            for valor in node.expressions:
                if isinstance(valor, exp.Literal):
                    valores.append(valor.this)

            resultado.setdefault(node.this.name, []).extend(valores)

    return resultado