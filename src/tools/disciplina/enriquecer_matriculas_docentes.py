#!/usr/bin/env python3
"""Adiciona dados de docentes em matriculas_ufcg_novo.sqlite.

O join usa codigo_da_disciplina, turma e periodo. Quando ha mais de um docente
na mesma disciplina/turma/periodo, os valores sao agrupados com " / ".
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


DEFAULT_MATRICULAS_DB = "matriculas_ufcg_novo.sqlite"
DEFAULT_PROFESSORES_DB = "professor_disciplina.sqlite"

MATRICULAS_TABLE = "matriculas_ufcg"
PROFESSORES_TABLE = "professor_disciplina"

NOVAS_COLUNAS = {
    "nome_do_professor": "TEXT",
    "matricula_do_docente": "TEXT",
    "siape": "TEXT",
}


def parse_args() -> argparse.Namespace:
    base_dir = Path(__file__).resolve().parent

    parser = argparse.ArgumentParser(
        description=(
            "Inclui nome_do_professor, matricula_do_docente e siape na tabela "
            "matriculas_ufcg, usando professor_disciplina como fonte."
        )
    )
    parser.add_argument(
        "--matriculas-db",
        type=Path,
        default=base_dir / DEFAULT_MATRICULAS_DB,
        help="Caminho do SQLite com a tabela matriculas_ufcg.",
    )
    parser.add_argument(
        "--professores-db",
        type=Path,
        default=base_dir / DEFAULT_PROFESSORES_DB,
        help="Caminho do SQLite com a tabela professor_disciplina.",
    )
    parser.add_argument(
        "--sem-backup",
        action="store_true",
        help="Nao cria uma copia .bak antes de alterar o banco de matriculas.",
    )
    return parser.parse_args()


def garantir_arquivo(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {path}")
    if not path.is_file():
        raise ValueError(f"O caminho nao e um arquivo: {path}")


def colunas_da_tabela(conn: sqlite3.Connection, tabela: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({tabela})").fetchall()
    if not rows:
        raise ValueError(f"Tabela nao encontrada: {tabela}")
    return {row[1] for row in rows}


def adicionar_colunas_se_precisar(conn: sqlite3.Connection) -> None:
    colunas_existentes = colunas_da_tabela(conn, MATRICULAS_TABLE)

    for coluna, tipo in NOVAS_COLUNAS.items():
        if coluna not in colunas_existentes:
            conn.execute(f"ALTER TABLE {MATRICULAS_TABLE} ADD COLUMN {coluna} {tipo}")


def criar_backup(matriculas_db: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = matriculas_db.with_suffix(matriculas_db.suffix + f".bak-{timestamp}")
    shutil.copy2(matriculas_db, backup_path)
    return backup_path


def anexar_professores(conn: sqlite3.Connection, professores_db: Path) -> None:
    conn.execute("ATTACH DATABASE ? AS professores_db", (str(professores_db),))


def preparar_docentes_agregados(conn: sqlite3.Connection) -> int:
    conn.execute("DROP TABLE IF EXISTS temp.docentes_por_turma")
    conn.execute(
        """
        CREATE TEMP TABLE docentes_por_turma AS
        SELECT
            codigo_da_disciplina,
            turma,
            periodo,
            group_concat(nome, ' / ') AS nome_do_professor,
            group_concat(CAST(matricula_do_docente AS TEXT), ' / ') AS matricula_do_docente,
            group_concat(CAST(siape AS TEXT), ' / ') AS siape
        FROM (
            SELECT DISTINCT
                codigo_da_disciplina,
                turma,
                periodo,
                nome,
                matricula_do_docente,
                siape
            FROM professores_db.professor_disciplina
            WHERE codigo_da_disciplina IS NOT NULL
              AND turma IS NOT NULL
              AND periodo IS NOT NULL
            ORDER BY
                codigo_da_disciplina,
                turma,
                periodo,
                nome,
                matricula_do_docente,
                siape
        )
        GROUP BY codigo_da_disciplina, turma, periodo
        """
    )
    conn.execute(
        """
        CREATE INDEX temp.idx_docentes_por_turma_chave
        ON docentes_por_turma (codigo_da_disciplina, turma, periodo)
        """
    )
    return conn.execute("SELECT COUNT(*) FROM temp.docentes_por_turma").fetchone()[0]


def contar_matriculas_com_docente(conn: sqlite3.Connection) -> int:
    return conn.execute(
        f"""
        SELECT COUNT(*)
        FROM {MATRICULAS_TABLE} AS m
        WHERE EXISTS (
            SELECT 1
            FROM temp.docentes_por_turma AS d
            WHERE d.codigo_da_disciplina = m.codigo_da_disciplina
              AND d.turma = m.turma
              AND d.periodo = m.periodo
        )
        """
    ).fetchone()[0]


def atualizar_matriculas(conn: sqlite3.Connection) -> int:
    conn.execute(
        f"""
        UPDATE {MATRICULAS_TABLE} AS m
        SET
            nome_do_professor = (
                SELECT d.nome_do_professor
                FROM temp.docentes_por_turma AS d
                WHERE d.codigo_da_disciplina = m.codigo_da_disciplina
                  AND d.turma = m.turma
                  AND d.periodo = m.periodo
            ),
            matricula_do_docente = (
                SELECT d.matricula_do_docente
                FROM temp.docentes_por_turma AS d
                WHERE d.codigo_da_disciplina = m.codigo_da_disciplina
                  AND d.turma = m.turma
                  AND d.periodo = m.periodo
            ),
            siape = (
                SELECT d.siape
                FROM temp.docentes_por_turma AS d
                WHERE d.codigo_da_disciplina = m.codigo_da_disciplina
                  AND d.turma = m.turma
                  AND d.periodo = m.periodo
            )
        WHERE EXISTS (
            SELECT 1
            FROM temp.docentes_por_turma AS d
            WHERE d.codigo_da_disciplina = m.codigo_da_disciplina
              AND d.turma = m.turma
              AND d.periodo = m.periodo
        )
        """
    )
    return conn.execute("SELECT changes()").fetchone()[0]


def main() -> None:
    args = parse_args()
    matriculas_db = args.matriculas_db.resolve()
    professores_db = args.professores_db.resolve()

    garantir_arquivo(matriculas_db)
    garantir_arquivo(professores_db)

    if not args.sem_backup:
        backup_path = criar_backup(matriculas_db)
        print(f"Backup criado: {backup_path}")

    with sqlite3.connect(matriculas_db) as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")

        adicionar_colunas_se_precisar(conn)
        anexar_professores(conn, professores_db)

        total_docentes_agregados = preparar_docentes_agregados(conn)
        total_matriculas_alvo = contar_matriculas_com_docente(conn)
        total_atualizadas = atualizar_matriculas(conn)

        conn.commit()

    print(f"Chaves disciplina/turma/periodo com docente: {total_docentes_agregados}")
    print(f"Linhas de matriculas com docente encontrado: {total_matriculas_alvo}")
    print(f"Linhas atualizadas: {total_atualizadas}")


if __name__ == "__main__":
    main()
