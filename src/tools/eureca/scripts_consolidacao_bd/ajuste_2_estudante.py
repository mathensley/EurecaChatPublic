"""Ajustes manuais da tabela de estudantes (sem execução na importação)."""

from pathlib import Path
import sqlite3

DB_PATH = Path(__file__).parent / "banco_de_dados_consolidado" / "ufcg.sqlite"
TABELA = "estudante"

COLUNAS_PARA_RENOMEAR = {
    "local_de_nascimento": "cidade_de_nascimento",
    "naturalidade": "unidade_federativa",
    "renda_per_capita_ate": "renda_percapita_ate",
}

# Formato: (coluna, expressão SQL usada no SET). Adicione regras quando necessário.
ATUALIZACOES_SET: tuple[tuple[str, str], ...] = ()

COLUNAS_PARA_DROPAR = (
    "nome_do_curso", "turno_do_curso", "codigo_do_campus", "nome_do_campus", 
    "codigo_do_setor", "nome_do_setor", "creditos_do_cra", "creditos_completados", 
    "notas_acumuladas", "codigo_da_unidade", "nome_da_unidade", "codigo_do_centro", 
    "nome_do_centro", "modalidade_academica",
)


def _quote(nome: str) -> str:
    return '"' + nome.replace('"', '""') + '"'


def filtrar_estudantes(db_path: str | Path = DB_PATH) -> tuple[str, ...]:
    """Aplica os ajustes e retorna os nomes das colunas finais."""
    with sqlite3.connect(db_path) as conn:
        existentes = [(row[1], row[2] or "TEXT") for row in conn.execute(f"PRAGMA table_info({_quote(TABELA)})")]
        for coluna, expressao in ATUALIZACOES_SET:
            conn.execute(f"UPDATE {_quote(TABELA)} SET {_quote(coluna)} = {expressao}")
        conn.execute(f"UPDATE {_quote(TABELA)} SET motivo_de_evasao = 'FORMADO' WHERE situacao = 'FORMADO';")
        conn.execute(f"UPDATE {_quote(TABELA)} SET motivo_de_evasao = 'CONCLUÍDO' WHERE situacao = 'FORMADO';")
        conn.execute(f"UPDATE {_quote(TABELA)} SET situacao = 'CONCLUÍDO' WHERE motivo_de_evasao = 'CONCLUÍDO';")
        conn.execute(f"UPDATE {_quote(TABELA)} SET motivo_de_evasao = 'CONCLUÍDO' WHERE situacao = 'CONCLUÍDO';")
        conn.execute(f"""DELETE FROM {_quote(TABELA)} WHERE rowid NOT IN (SELECT MIN(rowid) FROM {_quote(TABELA)} GROUP BY matricula_do_estudante)""")
        conn.execute(f"UPDATE {_quote(TABELA)} SET situacao = 'CANCELADO' WHERE situacao = 'TRANCADO';")
        conn.execute(f"DELETE FROM {_quote(TABELA)} WHERE situacao IN ('DESCONHECIDO', 'CADASTRADO', 'NÃO CADASTRADO');")
        conn.execute(f"UPDATE {_quote(TABELA)} SET forma_de_ingresso = 'SiSU' WHERE forma_de_ingresso = 'ENEM';")
        finais = [(origem, COLUNAS_PARA_RENOMEAR.get(origem, origem), tipo) for origem, tipo in existentes if origem not in COLUNAS_PARA_DROPAR]
        temporaria = f"{TABELA}__nova"
        conn.execute(f"DROP TABLE IF EXISTS {_quote(temporaria)}")
        conn.execute(f"CREATE TABLE {_quote(temporaria)} ({', '.join(f'{_quote(nova)} {tipo}' for _, nova, tipo in finais)})")
        conn.execute(f"INSERT INTO {_quote(temporaria)} ({', '.join(_quote(nova) for _, nova, _ in finais)}) SELECT {', '.join(_quote(origem) for origem, _, _ in finais)} FROM {_quote(TABELA)}")
        conn.execute(f"DROP TABLE {_quote(TABELA)}")
        conn.execute(f"ALTER TABLE {_quote(temporaria)} RENAME TO {_quote(TABELA)}")
        return tuple(row[1] for row in conn.execute(f"PRAGMA table_info({_quote(TABELA)})"))


if __name__ == "__main__":
    print("Colunas finais:")
    print("\n".join(f"- {coluna}" for coluna in filtrar_estudantes()))
