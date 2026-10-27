"""Ajustes manuais da tabela de estágios (sem execução na importação)."""

from pathlib import Path
import sqlite3

DB_PATH = Path(__file__).parent / "banco_de_dados_consolidado" / "ufcg.sqlite"
TABELA = "estagio"
COLUNAS_PARA_RENOMEAR = {
    "matricula_do_docente": "matricula_do_professor",
    "inicio_vigencia": "data_inicio_estagio",
    "final_vigencia": "data_final_estagio",
    "carga_semanal": "carga_horaria_semanal",
}
ATUALIZACOES_SET: tuple[tuple[str, str], ...] = ()
COLUNAS_PARA_DROPAR = (
    "departamento", "nome_docente", "codigo_do_curso", "nome_do_curso", "campus",
    "nome_do_campus", "sexo", "cor", "idade", "mc",
    "cnpj", "razao_social", "orgao_administracao_publica",
)


def _quote(nome: str) -> str:
    return '"' + nome.replace('"', '""') + '"'


def filtrar_estagios(db_path: str | Path = DB_PATH) -> tuple[str, ...]:
    """Aplica os ajustes e retorna os nomes das colunas finais."""
    with sqlite3.connect(db_path) as conn:
        existentes = [(row[1], row[2] or "TEXT") for row in conn.execute(f"PRAGMA table_info({_quote(TABELA)})")]
        for coluna, expressao in ATUALIZACOES_SET:
            conn.execute(f"UPDATE {_quote(TABELA)} SET {_quote(coluna)} = {expressao}")
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
    print("\n".join(f"- {coluna}" for coluna in filtrar_estagios()))