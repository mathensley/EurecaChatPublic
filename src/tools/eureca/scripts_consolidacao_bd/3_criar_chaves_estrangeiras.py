"""Gera uma cópia de ufcg.sqlite com chaves estrangeiras validadas."""

from pathlib import Path
import sqlite3


BASE_DIR = Path(__file__).parent
BANCO_DE_DADOS_DIR = BASE_DIR / "banco_de_dados_consolidado"
ORIGEM_PADRAO = BANCO_DE_DADOS_DIR / "ufcg.sqlite"
DESTINO_PADRAO = BANCO_DE_DADOS_DIR / "ufcg_com_chaves_estrangeiras.sqlite"
ORDEM_TABELAS = ("campus", "centro", "unidade", "curso", "estudante", "professor", "estagio", "inscricao",)
RESTRICOES = {
    "centro": ("FOREIGN KEY (codigo_do_campus) REFERENCES campus(codigo_do_campus)",),
    "unidade": (
        "FOREIGN KEY (codigo_do_centro) REFERENCES centro(codigo_do_centro)",
        "FOREIGN KEY (codigo_do_campus) REFERENCES campus(codigo_do_campus)",
    ),
    "curso": (
        "FOREIGN KEY (codigo_da_unidade) REFERENCES unidade(codigo_da_unidade)",
        "FOREIGN KEY (codigo_do_centro) REFERENCES centro(codigo_do_centro)",
        "FOREIGN KEY (codigo_do_campus) REFERENCES campus(codigo_do_campus)",
    ),
    "estudante": (
        "UNIQUE (matricula_do_estudante)",
        "FOREIGN KEY (codigo_do_curso) REFERENCES curso(codigo_do_curso)",
    ),
    "professor": (
        "UNIQUE (matricula_do_professor)",
        "FOREIGN KEY (codigo_da_unidade) REFERENCES unidade(codigo_da_unidade)",
    ),
    "estagio": (
        "FOREIGN KEY (matricula_do_estudante) REFERENCES estudante(matricula_do_estudante)",
        "FOREIGN KEY (matricula_do_professor) REFERENCES professor(matricula_do_professor)",
    ),
    "inscricao": (
        "FOREIGN KEY (matricula_do_estudante) REFERENCES estudante(matricula_do_estudante)",
        "FOREIGN KEY (matricula_do_professor) REFERENCES professor(matricula_do_professor)",
    ),
}


def _quote(nome: str) -> str:
    return '"' + nome.replace('"', '""') + '"'


def _schema_com_restricoes(schema: str, tabela: str) -> str:
    """Inclui restrições no fim da definição CREATE TABLE original."""
    restricoes = RESTRICOES.get(tabela, ())
    if not restricoes:
        return schema
    indice_final = schema.rfind(")")
    if indice_final < 0:
        raise ValueError(f"Definição SQL inválida para a tabela {tabela!r}")
    return schema[:indice_final] + ", " + ", ".join(restricoes) + schema[indice_final:]


def criar_banco_com_chaves_estrangeiras(
    origem: str | Path = ORIGEM_PADRAO,
    destino: str | Path = DESTINO_PADRAO,
) -> dict[str, int]:
    """Copia os dados e retorna as referências de professor convertidas em NULL.

    O arquivo de destino não pode existir, evitando sobrescrita acidental.
    """
    origem, destino = Path(origem), Path(destino)
    if destino.exists():
        destino.unlink()
        # raise FileExistsError(f"O destino já existe: {destino}")

    with sqlite3.connect(origem) as banco_origem, sqlite3.connect(destino) as banco_destino:
        banco_destino.execute("PRAGMA foreign_keys = OFF")
        for tabela in ORDEM_TABELAS:
            schema = banco_origem.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (tabela,)
            ).fetchone()
            if schema is None:
                raise ValueError(f"Tabela obrigatória ausente: {tabela}")
            banco_destino.execute(_schema_com_restricoes(schema[0], tabela))
            colunas = [row[1] for row in banco_origem.execute(f"PRAGMA table_info({_quote(tabela)})")]
            banco_destino.executemany(
                f"INSERT INTO {_quote(tabela)} VALUES ({', '.join('?' for _ in colunas)})",
                banco_origem.execute(f"SELECT * FROM {_quote(tabela)}"),
            )
        banco_destino.commit()

        banco_destino.execute("PRAGMA foreign_keys = ON")
        inscricoes_nulas = banco_destino.execute("""
            UPDATE inscricao
            SET matricula_do_professor = NULL
            WHERE matricula_do_professor IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM professor
                  WHERE professor.matricula_do_professor = inscricao.matricula_do_professor
              )
        """).rowcount
        estagios_nulos = banco_destino.execute("""
            UPDATE estagio
            SET matricula_do_professor = NULL
            WHERE matricula_do_professor IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM professor
                  WHERE professor.matricula_do_professor = estagio.matricula_do_professor
              )
        """).rowcount
        violacoes = banco_destino.execute("PRAGMA foreign_key_check").fetchall()
        if violacoes:
            raise ValueError(f"Há violações de chave estrangeira: {violacoes[:5]}")
    return {
        "matriculas_do_professor_convertidas_em_null": inscricoes_nulas,
        "estagios_do_professor_convertidos_em_null": estagios_nulos,
    }


if __name__ == "__main__":
    for descricao, total in criar_banco_com_chaves_estrangeiras().items():
        print(f"{descricao}: {total}")
