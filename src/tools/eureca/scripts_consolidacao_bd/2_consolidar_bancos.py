"""Consolida os bancos SQLite em um único arquivo com as tabelas finais."""

from pathlib import Path
import sqlite3


BASE_DIR = Path(__file__).parent / "banco_de_dados_consolidado"
DESTINO_PADRAO = BASE_DIR / "ufcg.sqlite"
# (arquivo de origem, tabela de origem, nome da tabela consolidada)

tabela_estrutura_ufcg = f"{BASE_DIR}/estrutura_ufcg.sqlite"
TABELAS = (
    (tabela_estrutura_ufcg, "campus", "campus"),
    (tabela_estrutura_ufcg, "centro", "centro"),
    (tabela_estrutura_ufcg, "unidade", "unidade"),
    (tabela_estrutura_ufcg, "curso", "curso"),
    ("./estagios_ufcg.sqlite", "estagios_ufcg", "estagio"),
    ("./estudantes_ufcg.sqlite", "estudantes_ufcg", "estudante"),
    ("./matriculas_ufcg.sqlite", "matriculas_ufcg", "inscricao"),
    ("./professor_disciplina.sqlite", "professor_disciplina", "professor"),
    #("./horarios_ufcg.sqlite", "horarios_ufcg", "horario"),
    #("./turmas_ufcg.sqlite", "turmas_ufcg", "turma"),
)


def _quote(nome: str) -> str:
    return '"' + nome.replace('"', '""') + '"'


def consolidar_bancos(destino: str | Path = DESTINO_PADRAO) -> dict[str, int]:
    """Substitui o conteúdo do destino pelas oito tabelas consolidadas."""
    destino = Path(destino)
    contagens: dict[str, int] = {}

    with sqlite3.connect(destino) as banco_destino:
        tabelas_existentes = banco_destino.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        for (tabela,) in tabelas_existentes:
            banco_destino.execute(f"DROP TABLE {_quote(tabela)}")

        for arquivo_origem, tabela_origem, tabela_destino in TABELAS:
            caminho_origem = arquivo_origem
            with sqlite3.connect(caminho_origem) as banco_origem:
                schema = banco_origem.execute(
                    "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
                    (tabela_origem,),
                ).fetchone()
                if schema is None:
                    raise ValueError(f"Tabela {tabela_origem!r} não encontrada em {caminho_origem}")

                schema_destino = schema[0].replace(
                    f'CREATE TABLE "{tabela_origem}"', f'CREATE TABLE "{tabela_destino}"', 1
                ).replace(
                    f'CREATE TABLE {tabela_origem}', f'CREATE TABLE {tabela_destino}', 1
                )
                banco_destino.execute(schema_destino)
                colunas = [row[1] for row in banco_origem.execute(f"PRAGMA table_info({_quote(tabela_origem)})")]
                banco_destino.executemany(
                    f"INSERT INTO {_quote(tabela_destino)} VALUES ({', '.join('?' for _ in colunas)})",
                    banco_origem.execute(f"SELECT * FROM {_quote(tabela_origem)}"),
                )
                contagens[tabela_destino] = banco_destino.execute(
                    f"SELECT COUNT(*) FROM {_quote(tabela_destino)}"
                ).fetchone()[0]
    return contagens


if __name__ == "__main__":
    for tabela, total in consolidar_bancos().items():
        print(f"{tabela}: {total} linhas")
