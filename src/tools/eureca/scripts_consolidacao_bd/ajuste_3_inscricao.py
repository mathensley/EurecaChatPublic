"""Ajustes manuais da tabela de matrículas (sem execução na importação)."""

from pathlib import Path
import sqlite3

DB_PATH = Path(__file__).parent / "banco_de_dados_consolidado" / "ufcg.sqlite"
PROFESSORES_DB_PATH = Path(__file__).resolve().parents[4] / "professor_disciplina.sqlite"
TABELA = "inscricao"
COLUNAS_PARA_RENOMEAR: dict[str, str] = {}
ATUALIZACOES_SET: tuple[tuple[str, str], ...] = ()
COLUNAS_PARA_DROPAR = (
    "codigo_do_curso", "nome_do_curso", "turno_do_curso", "codigo_do_curriculo",
    "codigo_do_campus", "nome_do_campus", "codigo_do_setor", "nome_do_setor",
    "estado_civil", "sexo", "idade", "situacao", "motivo_de_evasao", "periodo_de_evasao",
    "forma_de_ingresso", "periodo_de_ingresso", "nacionalidade", "local_de_nascimento",
    "naturalidade", "cor", "deficiencias", "ano_de_conclusao_ensino_medio",
    "tipo_de_ensino_medio", "politica_afirmativa", "creditos_do_cra", "notas_acumuladas",
    "periodos_completados", "creditos_tentados", "creditos_completados", "creditos_isentos",
    "creditos_falhados", "creditos_suspensos", "creditos_em_andamento", "velocidade_media",
    "taxa_de_sucesso", "renda_per_capita_ate", "mc", "tem_deficiencia", "cotista",
    "codigo_da_unidade", "nome_da_unidade", "codigo_do_centro", "nome_do_centro",
    "modalidade_academica",
)


def _quote(nome: str) -> str:
    return '"' + nome.replace('"', '""') + '"'


def filtrar_matriculas(
    db_path: str | Path = DB_PATH,
    professores_db_path: str | Path = PROFESSORES_DB_PATH,
) -> tuple[tuple[str, ...], int]:
    """Filtra matrículas e associa o primeiro professor de cada turma.

    Para chaves repetidas no banco de professores, é mantido o registro de
    menor ``rowid`` para a combinação de disciplina, turma e período.
    Retorna ``(colunas_finais, matriculas_com_professor)``.
    """
    with sqlite3.connect(db_path) as conn:
        conn.execute("ATTACH DATABASE ? AS professores", (str(professores_db_path),))
        existentes = [(row[1], row[2] or "TEXT") for row in conn.execute(f"PRAGMA table_info({_quote(TABELA)})")]
        for coluna, expressao in ATUALIZACOES_SET:
            conn.execute(f"UPDATE {_quote(TABELA)} SET {_quote(coluna)} = {expressao}")
        finais = [
            (origem, COLUNAS_PARA_RENOMEAR.get(origem, origem), tipo)
            for origem, tipo in existentes
            if origem not in COLUNAS_PARA_DROPAR
            and COLUNAS_PARA_RENOMEAR.get(origem, origem)
            not in {"id_inscricao", "matricula_do_professor"}
        ]
        nomes_finais = {nova for _, nova, _ in finais}
        chaves = {"codigo_da_disciplina", "turma", "periodo"}
        if not chaves.issubset(nomes_finais):
            raise ValueError(f"Colunas obrigatórias ausentes: {', '.join(sorted(chaves - nomes_finais))}")

        # Uma única matrícula de professor por disciplina/turma/período.
        tabela_mapa = "professores_por_turma__temp"
        conn.execute(f"DROP TABLE IF EXISTS {_quote(tabela_mapa)}")
        conn.execute(
            f"CREATE TEMP TABLE {_quote(tabela_mapa)} AS "
            "SELECT codigo_da_disciplina, turma, periodo, "
            "matricula_do_docente AS matricula_do_professor "
            "FROM professores.professor_disciplina "
            "WHERE rowid IN ("
            "SELECT MIN(rowid) FROM professores.professor_disciplina "
            "GROUP BY codigo_da_disciplina, turma, periodo)"
        )

        temporaria = f"{TABELA}__nova"
        conn.execute(f"DROP TABLE IF EXISTS {_quote(temporaria)}")
        # Em uma tabela nova, INTEGER PRIMARY KEY gera os valores 1, 2, 3...
        # automaticamente durante o INSERT, um por matrícula.
        definicoes = [f'{_quote("id_inscricao")} INTEGER PRIMARY KEY']
        definicoes.extend(f"{_quote(nova)} {tipo}" for _, nova, tipo in finais)
        definicoes.append(f'{_quote("matricula_do_professor")} INTEGER')
        conn.execute(f"CREATE TABLE {_quote(temporaria)} ({', '.join(definicoes)})")
        conn.execute(
            f"INSERT INTO {_quote(temporaria)} ({', '.join(_quote(nova) for _, nova, _ in finais)}, {_quote('matricula_do_professor')}) "
            f"SELECT {', '.join(f'matricula.{_quote(origem)}' for origem, _, _ in finais)}, professor.matricula_do_professor "
            f"FROM {_quote(TABELA)} AS matricula "
            f"LEFT JOIN {_quote(tabela_mapa)} AS professor "
            "ON matricula.codigo_da_disciplina = professor.codigo_da_disciplina "
            "AND matricula.turma = professor.turma "
            "AND matricula.periodo = professor.periodo"
        )
        associadas = conn.execute(
            f"SELECT COUNT(*) FROM {_quote(temporaria)} "
            "WHERE matricula_do_professor IS NOT NULL"
        ).fetchone()[0]
        conn.execute(f"DROP TABLE {_quote(TABELA)}")
        conn.execute(f"ALTER TABLE {_quote(temporaria)} RENAME TO {_quote(TABELA)}")
        colunas = tuple(row[1] for row in conn.execute(f"PRAGMA table_info({_quote(TABELA)})"))
        return colunas, associadas


def alocar_professores_unicos(
    db_path: str | Path = DB_PATH,
    professores_db_path: str | Path = PROFESSORES_DB_PATH,
) -> int:
    """Completa dados que sejam inequívocos por disciplina e período.

    A matrícula do professor é preenchida se houver somente um docente na
    combinação, mesmo que ele ministre mais de uma turma. A turma é
    preenchida somente se houver uma única turma. Assim, cada campo é
    completado apenas quando a informação específica não for ambígua.

    Retorna a quantidade total de inscrições atualizadas.
    """
    with sqlite3.connect(db_path) as conn:
        conn.execute("ATTACH DATABASE ? AS professores", (str(professores_db_path),))

        colunas_inscricao = {
            row[1] for row in conn.execute(f"PRAGMA table_info({_quote(TABELA)})")
        }
        obrigatorias = {
            "codigo_da_disciplina",
            "periodo",
            "turma",
            "matricula_do_professor",
        }
        ausentes = obrigatorias - colunas_inscricao
        if ausentes:
            raise ValueError(
                "Colunas obrigatórias ausentes: "
                f"{', '.join(sorted(ausentes))}"
            )

        # Uma linha por disciplina/período, com as quantidades que determinam
        # se cada informação pode ser preenchida com segurança.
        tabela_mapa = "professores_unicos_por_disciplina_periodo__temp"
        conn.execute(f"DROP TABLE IF EXISTS {_quote(tabela_mapa)}")
        conn.execute(
            f"CREATE TEMP TABLE {_quote(tabela_mapa)} AS "
            "SELECT codigo_da_disciplina, periodo, "
            "MIN(turma) AS turma, "
            "MIN(matricula_do_docente) AS matricula_do_professor "
            ", COUNT(DISTINCT turma) AS quantidade_turmas "
            ", COUNT(DISTINCT matricula_do_docente) AS quantidade_professores "
            "FROM professores.professor_disciplina "
            "WHERE codigo_da_disciplina IS NOT NULL "
            "AND periodo IS NOT NULL "
            "AND turma IS NOT NULL "
            "AND matricula_do_docente IS NOT NULL "
            "GROUP BY codigo_da_disciplina, periodo "
        )
        conn.execute(
            f"CREATE INDEX {_quote(f'{tabela_mapa}__chave')} "
            f"ON {_quote(tabela_mapa)} (codigo_da_disciplina, periodo)"
        )

        conn.execute(
            f"UPDATE {_quote(TABELA)} AS inscricao "
            "SET matricula_do_professor = ("
            f"SELECT professor.matricula_do_professor FROM {_quote(tabela_mapa)} AS professor "
            "WHERE professor.codigo_da_disciplina = inscricao.codigo_da_disciplina "
            "AND professor.periodo = inscricao.periodo"
            ") "
            "WHERE inscricao.matricula_do_professor IS NULL "
            "AND inscricao.codigo_da_disciplina IS NOT NULL "
            "AND inscricao.periodo IS NOT NULL "
            "AND EXISTS ("
            f"SELECT 1 FROM {_quote(tabela_mapa)} AS professor "
            "WHERE professor.codigo_da_disciplina = inscricao.codigo_da_disciplina "
            "AND professor.periodo = inscricao.periodo "
            "AND professor.quantidade_professores = 1"
            ")"
        )
        professores_alocados = conn.execute("SELECT changes()").fetchone()[0]
        conn.execute(
            f"UPDATE {_quote(TABELA)} AS inscricao "
            "SET turma = ("
            f"SELECT professor.turma FROM {_quote(tabela_mapa)} AS professor "
            "WHERE professor.codigo_da_disciplina = inscricao.codigo_da_disciplina "
            "AND professor.periodo = inscricao.periodo"
            ") "
            "WHERE inscricao.turma IS NULL "
            "AND inscricao.codigo_da_disciplina IS NOT NULL "
            "AND inscricao.periodo IS NOT NULL "
            "AND EXISTS ("
            f"SELECT 1 FROM {_quote(tabela_mapa)} AS professor "
            "WHERE professor.codigo_da_disciplina = inscricao.codigo_da_disciplina "
            "AND professor.periodo = inscricao.periodo "
            "AND professor.quantidade_turmas = 1"
            ")"
        )
        turmas_alocadas = conn.execute("SELECT changes()").fetchone()[0]
        return professores_alocados + turmas_alocadas

if __name__ == "__main__":
    colunas, associadas = filtrar_matriculas()
    alocacoes_inequivocas = alocar_professores_unicos()
    print("Colunas finais:")
    print("\n".join(f"- {coluna}" for coluna in colunas))
    print(f"Matrículas associadas a um professor: {associadas}")
    print(f"Campos preenchidos por correspondência inequívoca: {alocacoes_inequivocas}")
