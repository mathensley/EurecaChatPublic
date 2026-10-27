"""Copia o status dos professores para o banco professor_disciplina."""

from pathlib import Path
import sqlite3


RAIZ_PROJETO = Path(__file__).resolve().parents[4]

DB_PROFESSORES = RAIZ_PROJETO / "professores_ufcg.sqlite"
DB_PROFESSOR_DISCIPLINA = RAIZ_PROJETO / "professor_disciplina.sqlite"
DB_PROFESSOR_DISCIPLINA_STATUS = (RAIZ_PROJETO / "professor_disciplina_status.sqlite")

TABELA_PROFESSORES = "professores_ufcg"
TABELA_PROFESSOR_DISCIPLINA = "professor_disciplina"


def _validar_tabela(banco: str | Path, tabela: str, colunas_obrigatorias: set[str],) -> None:
    """Valida a existência do banco, da tabela e das colunas necessárias."""

    caminho = Path(banco)
    if not caminho.is_file(): raise FileNotFoundError(f"Banco não encontrado: {caminho}")

    with sqlite3.connect(caminho) as conn:
        tabela_existe = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (tabela,),).fetchone()

        if tabela_existe is None: raise ValueError(f"Tabela {tabela!r} não encontrada em {caminho}")

        colunas = {linha[1] for linha in conn.execute(f'PRAGMA table_info("{tabela}")')}
        ausentes = colunas_obrigatorias - colunas

        if ausentes:
            raise ValueError(f"Colunas ausentes em {tabela!r}: {', '.join(sorted(ausentes))}")


def passar_status_professores(
    db_professores: str | Path = DB_PROFESSORES,
    db_professor_disciplina: str | Path = DB_PROFESSOR_DISCIPLINA,
    db_saida: str | Path = DB_PROFESSOR_DISCIPLINA_STATUS,
) -> dict[str, int | bool | str]:
    """Cria uma cópia de professor_disciplina e preenche a coluna ``status``.

    O cruzamento entre os bancos é realizado pela coluna
    ``matricula_do_docente``. O banco de origem não é modificado e o resultado
    é salvo em ``professor_disciplina_status.sqlite``.
    """

    _validar_tabela(db_professores, TABELA_PROFESSORES, {"matricula_do_docente", "status"},)
    _validar_tabela(db_professor_disciplina, TABELA_PROFESSOR_DISCIPLINA, {"matricula_do_docente"},)

    caminho_origem = Path(db_professor_disciplina).resolve()
    caminho_saida = Path(db_saida).resolve()

    if caminho_origem == caminho_saida: raise ValueError("O banco de saída deve ser diferente do banco de origem")

    caminho_saida.parent.mkdir(parents=True, exist_ok=True)
    with (sqlite3.connect(caminho_origem) as origem, sqlite3.connect(caminho_saida) as destino,):
        origem.backup(destino)

    with sqlite3.connect(caminho_saida) as conn:
        colunas = {linha[1] for linha in conn.execute(f'PRAGMA table_info("{TABELA_PROFESSOR_DISCIPLINA}")')}
        coluna_criada = "status" not in colunas

        if coluna_criada:
            conn.execute(f'ALTER TABLE "{TABELA_PROFESSOR_DISCIPLINA}" ''ADD COLUMN "status" TEXT')

        conn.execute("ATTACH DATABASE ? AS banco_professores", (str(Path(db_professores).resolve()),),)

        total_linhas = conn.execute(f'SELECT COUNT(*) FROM "{TABELA_PROFESSOR_DISCIPLINA}"').fetchone()[0]
        total_matriculas = conn.execute(f"SELECT COUNT(DISTINCT matricula_do_docente) " f'FROM "{TABELA_PROFESSOR_DISCIPLINA}"').fetchone()[0]
        matriculas_sem_correspondencia = conn.execute(
            f"""
            SELECT COUNT(*)
            FROM (
                SELECT DISTINCT destino.matricula_do_docente
                FROM "{TABELA_PROFESSOR_DISCIPLINA}" AS destino
                LEFT JOIN banco_professores."{TABELA_PROFESSORES}" AS origem
                  ON origem.matricula_do_docente = destino.matricula_do_docente
                WHERE origem.matricula_do_docente IS NULL
            )
            """
        ).fetchone()[0]

        conn.execute(
            f"""
            UPDATE "{TABELA_PROFESSOR_DISCIPLINA}"
            SET status = (
                SELECT origem.status
                FROM banco_professores."{TABELA_PROFESSORES}" AS origem
                WHERE origem.matricula_do_docente =
                      "{TABELA_PROFESSOR_DISCIPLINA}".matricula_do_docente
            )
            WHERE EXISTS (
                SELECT 1
                FROM banco_professores."{TABELA_PROFESSORES}" AS origem
                WHERE origem.matricula_do_docente =
                      "{TABELA_PROFESSOR_DISCIPLINA}".matricula_do_docente
            )
            """
        )
        linhas_atualizadas = conn.execute("SELECT changes()").fetchone()[0]
        conn.commit()

        linhas_sem_status = conn.execute(
            f"SELECT COUNT(*) FROM \"{TABELA_PROFESSOR_DISCIPLINA}\" "
            "WHERE status IS NULL"
        ).fetchone()[0]

    return {
        "banco_saida": str(caminho_saida),
        "coluna_criada": coluna_criada,
        "total_linhas": total_linhas,
        "total_matriculas": total_matriculas,
        "linhas_atualizadas": linhas_atualizadas,
        "matriculas_sem_correspondencia": matriculas_sem_correspondencia,
        "linhas_sem_status": linhas_sem_status,
    }


if __name__ == "__main__":
    resultado = passar_status_professores()

    print("============== PASSAGEM DE STATUS DOS PROFESSORES ==============")
    print(f"Banco gerado: {resultado['banco_saida']}")
    print(f"Coluna status criada: {resultado['coluna_criada']}")
    print(f"Linhas na tabela: {resultado['total_linhas']}")
    print(f"Matrículas distintas: {resultado['total_matriculas']}")
    print(f"Linhas atualizadas: {resultado['linhas_atualizadas']}")
    print(
        "Matrículas sem correspondência: "
        f"{resultado['matriculas_sem_correspondencia']}"
    )
    print(f"Linhas sem status: {resultado['linhas_sem_status']}")
