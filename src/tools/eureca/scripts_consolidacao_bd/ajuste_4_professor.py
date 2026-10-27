"""Ajustes manuais da tabela de professores (sem execução na importação)."""

from pathlib import Path
import json
import sqlite3

DB_PATH = Path(__file__).parent / "banco_de_dados_consolidado" / "ufcg.sqlite"
TABELA = "professor"

# Os dados do professor tem o nome da unidade mas não o código da unidade, esse códigos unidade path resolve isso.
CODIGOS_UNIDADES_PATH = Path(__file__).parent / "unidades_professor_com_codigos.json"
COLUNAS_PARA_RENOMEAR = {
    "matricula_do_docente": "matricula_do_professor",
    "nome": "nome_do_professor",
    "unidade": "unidade",
}
ATUALIZACOES_SET: tuple[tuple[str, str], ...] = (
    (
        "sexo",
        "CASE "
        "WHEN sexo = 'F' THEN 'FEMININO' "
        "WHEN sexo = 'M' THEN 'MASCULINO' "
        "ELSE sexo END",
    ),
)
COLUNA_PARA_REMOVER_DUPLICADOS = "matricula_do_professor"
COLUNAS_PARA_DROPAR = (
    "turma", "codigo_da_disciplina", "nome_da_disciplina", "periodo",
    "carga_horaria_especifica",
)
# A coluna é necessária para cruzar com o JSON, mas não é mantida no resultado.
COLUNAS_PARA_DROPAR_NO_FINAL = ("unidade",)


def _quote(nome: str) -> str:
    return '"' + nome.replace('"', '""') + '"'


def obter_colunas(db_path: str | Path = DB_PATH) -> tuple[str, ...]:
    """Retorna as colunas existentes, inclusive após uma execução anterior."""
    with sqlite3.connect(db_path) as conn:
        return tuple(
            row[1] for row in conn.execute(f"PRAGMA table_info({_quote(TABELA)})")
        )


def _carregar_codigos_unidades(caminho: str | Path = CODIGOS_UNIDADES_PATH) -> list[tuple[str, int]]:
    """Lê somente os pares de unidade e código que possuem código válido."""
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    return [
        (item["nome_da_unidade"], item["codigo_da_unidade"])
        for item in dados
        if item.get("codigo_da_unidade") is not None
    ]


def filtrar_professores(
    db_path: str | Path = DB_PATH,
) -> tuple[tuple[str, ...], int, list[tuple[str | None, str | None]]]:
    """Inclui o código da unidade e remove linhas cuja unidade não tenha código.

    Retorna ``(colunas_finais, linhas_sem_codigo_removidas, removidos)``.
    ``removidos`` contém pares ``(nome_do_professor, unidade)``. A
    deduplicação por matrícula é aplicada apenas entre os registros válidos.
    """
    with sqlite3.connect(db_path) as conn:
        existentes = [(row[1], row[2] or "TEXT") for row in conn.execute(f"PRAGMA table_info({_quote(TABELA)})")]
        for coluna, expressao in ATUALIZACOES_SET:
            conn.execute(f"UPDATE {_quote(TABELA)} SET {_quote(coluna)} = {expressao}")
        finais = [
            (origem, COLUNAS_PARA_RENOMEAR.get(origem, origem), tipo)
            for origem, tipo in existentes
            if origem not in COLUNAS_PARA_DROPAR
            and COLUNAS_PARA_RENOMEAR.get(origem, origem) != "codigo_da_unidade"
        ]
        coluna_unidade_origem = next(
            (origem for origem, nova, _ in finais if nova == "unidade"), None
        )
        # Em execuções posteriores a coluna já foi descartada. Ainda assim,
        # as atualizações de dados acima (como a normalização de sexo) devem
        # ser confirmadas sem tentar refazer a filtragem.
        if coluna_unidade_origem is None:
            colunas_atuais = tuple(
                row[1] for row in conn.execute(f"PRAGMA table_info({_quote(TABELA)})")
            )
            return colunas_atuais, 0, []
        coluna_matricula_origem = next(
            (origem for origem, nova, _ in finais if nova == COLUNA_PARA_REMOVER_DUPLICADOS),
            None,
        )
        if coluna_unidade_origem is None:
            raise ValueError("Coluna 'unidade' não encontrada")
        if coluna_matricula_origem is None:
            raise ValueError(f"Coluna {COLUNA_PARA_REMOVER_DUPLICADOS!r} não encontrada")
        coluna_nome_origem = next(
            (origem for origem, nova, _ in finais if nova == "nome_do_professor"), None
        )
        if coluna_nome_origem is None:
            raise ValueError("Coluna 'nome_do_professor' não encontrada")

        codigos = _carregar_codigos_unidades()
        total_original = conn.execute(f"SELECT COUNT(*) FROM {_quote(TABELA)}").fetchone()[0]
        tabela_codigos = "codigos_unidades__temp"
        conn.execute(f"DROP TABLE IF EXISTS {_quote(tabela_codigos)}")
        conn.execute(f"CREATE TEMP TABLE {_quote(tabela_codigos)} (nome_da_unidade TEXT PRIMARY KEY, codigo_da_unidade INTEGER NOT NULL)")
        conn.executemany(
            f"INSERT INTO {_quote(tabela_codigos)} VALUES (?, ?)", codigos
        )
        total_com_codigo = conn.execute(
            f"SELECT COUNT(*) FROM {_quote(TABELA)} AS professor "
            f"JOIN {_quote(tabela_codigos)} AS codigo "
            f"ON professor.{_quote(coluna_unidade_origem)} = codigo.nome_da_unidade"
        ).fetchone()[0]
        removidas_sem_codigo = total_original - total_com_codigo
        removidos = conn.execute(
            f"SELECT professor.{_quote(coluna_nome_origem)}, professor.{_quote(coluna_unidade_origem)} "
            f"FROM {_quote(TABELA)} AS professor "
            f"LEFT JOIN {_quote(tabela_codigos)} AS codigo "
            f"ON professor.{_quote(coluna_unidade_origem)} = codigo.nome_da_unidade "
            f"WHERE codigo.codigo_da_unidade IS NULL "
            f"ORDER BY professor.{_quote(coluna_unidade_origem)}, professor.{_quote(coluna_nome_origem)}"
        ).fetchall()

        temporaria = f"{TABELA}__nova"
        conn.execute(f"DROP TABLE IF EXISTS {_quote(temporaria)}")
        finais_banco = [
            item for item in finais if item[1] not in COLUNAS_PARA_DROPAR_NO_FINAL
        ]
        definicoes = [f"{_quote(nova)} {tipo}" for _, nova, tipo in finais_banco]
        definicoes.append(f'{_quote("codigo_da_unidade")} INTEGER')
        conn.execute(f"CREATE TABLE {_quote(temporaria)} ({', '.join(definicoes)})")
        conn.execute(
            f"INSERT INTO {_quote(temporaria)} ({', '.join(_quote(nova) for _, nova, _ in finais_banco)}, {_quote('codigo_da_unidade')}) "
            f"SELECT {', '.join(f'professor.{_quote(origem)}' for origem, _, _ in finais_banco)}, codigo.codigo_da_unidade "
            f"FROM {_quote(TABELA)} AS professor "
            f"JOIN {_quote(tabela_codigos)} AS codigo "
            f"ON professor.{_quote(coluna_unidade_origem)} = codigo.nome_da_unidade "
            f"WHERE professor.rowid IN ("
            f"SELECT MIN(origem.rowid) FROM {_quote(TABELA)} AS origem "
            f"JOIN {_quote(tabela_codigos)} AS codigo_origem "
            f"ON origem.{_quote(coluna_unidade_origem)} = codigo_origem.nome_da_unidade "
            f"GROUP BY origem.{_quote(coluna_matricula_origem)})"
        )
        conn.execute(f"DROP TABLE {_quote(TABELA)}")
        conn.execute(f"ALTER TABLE {_quote(temporaria)} RENAME TO {_quote(TABELA)}")
        colunas_finais = tuple(row[1] for row in conn.execute(f"PRAGMA table_info({_quote(TABELA)})"))
        return colunas_finais, removidas_sem_codigo, removidos


if __name__ == "__main__":
    try:
        colunas, removidas, professores_removidos = filtrar_professores()
    except ValueError as erro:
        # A segunda execução encontra a tabela já filtrada, sem ``unidade``.
        print(f"Nenhuma alteração aplicada: {erro}")
        colunas, removidas, professores_removidos = obter_colunas(), 0, []

    print("Colunas finais atuais:")
    print("\n".join(f"- {coluna}" for coluna in colunas))
    if removidas:
        print(f"Linhas removidas por não possuírem código da unidade: {removidas}")
        print("Professores removidos (nome | unidade):")
        #for nome, unidade in professores_removidos:
        #    print(f"- {nome} | {unidade}")
