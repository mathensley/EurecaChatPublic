"""Cria o banco SQLite com a estrutura de campi, centros e unidades da UFCG."""

import json
from pathlib import Path
import sqlite3


BASE_DIR = Path(__file__).parent
CURSOS_PATH = BASE_DIR.parent / "hierarquia_siglas" / "cursos.json"
DB_PATH = BASE_DIR / "banco_de_dados_consolidado" / "estrutura_ufcg.sqlite"


def _nome_com_sigla(nome: str, sigla: str | None) -> str:
    return f"{nome} - {sigla}" if sigla else nome


def criar_estrutura(
    cursos_path: str | Path = CURSOS_PATH,
    db_path: str | Path = DB_PATH,
) -> dict[str, int]:
    """Cria e popula as tabelas ``campus``, ``centro`` e ``unidade``."""
    cursos = json.loads(Path(cursos_path).read_text(encoding="utf-8"))

    campi: dict[int, tuple[int, str]] = {}
    centros: dict[int, tuple[int, str, int, str, str | None]] = {}
    unidades: dict[int, tuple[int, str, int, str, int, str, str | None]] = {}
    cursos_por_codigo: dict[int, tuple] = {}
    for item in cursos:
        codigo_campus = item["codigo_do_campus"]
        nome_campus = item["nome_do_campus"]
        codigo_centro = item["codigo_do_centro"]
        nome_centro = _nome_com_sigla(item["nome_do_centro"], item.get("sigla_do_centro"))
        codigo_unidade = item["codigo_da_unidade"]
        nome_unidade = _nome_com_sigla(item["nome_da_unidade"], item.get("sigla_da_unidade"))
        email_centro = item.get("email_do_centro")

        campi[codigo_campus] = (codigo_campus, nome_campus)
        centros[codigo_centro] = (
            codigo_centro, nome_centro, codigo_campus, nome_campus, email_centro
        )
        unidades[codigo_unidade] = (
            codigo_unidade, nome_unidade, codigo_centro, nome_centro,
            codigo_campus, nome_campus, email_centro,
        )
        cursos_por_codigo[item["codigo_do_curso"]] = (
            item["codigo_do_curso"], item["nome_do_curso"],
            item.get("modalidade_academica"), item.get("turno"),
            item.get("periodo_de_inicio"), item.get("data_de_funcionamento"),
            item.get("area_de_retencao"), item.get("ciclo_enade"),
            codigo_unidade, item["nome_da_unidade"], item.get("sigla_da_unidade"),
            codigo_centro, item["nome_do_centro"], item.get("sigla_do_centro"),
            codigo_campus, nome_campus,
            item["codigo_do_curriculo"],
            item["duracao_minima"],
            item["duracao_maxima"],
            item["duracao_media"],
            item["carga_horaria_disciplinas_obrigatorias_minima"],
            item["carga_horaria_disciplinas_optativas_minima"],
            item["carga_horaria_atividades_complementares_minima"],
            item["carga_horaria_minima_total"],
            item["minimo_creditos_disciplinas_optativas"],
            item["minimo_creditos_total"],
        )

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS campus (
                codigo_do_campus INTEGER PRIMARY KEY,
                nome_do_campus TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS centro (
                codigo_do_centro INTEGER PRIMARY KEY,
                nome_do_centro TEXT NOT NULL,
                codigo_do_campus INTEGER NOT NULL,
                nome_do_campus TEXT NOT NULL,
                email_do_centro TEXT,
                FOREIGN KEY (codigo_do_campus) REFERENCES campus(codigo_do_campus)
            );

            CREATE TABLE IF NOT EXISTS unidade (
                codigo_da_unidade INTEGER PRIMARY KEY,
                nome_da_unidade TEXT NOT NULL,
                codigo_do_centro INTEGER NOT NULL,
                nome_do_centro TEXT NOT NULL,
                codigo_do_campus INTEGER NOT NULL,
                nome_do_campus TEXT NOT NULL,
                email_da_unidade TEXT,
                FOREIGN KEY (codigo_do_centro) REFERENCES centro(codigo_do_centro),
                FOREIGN KEY (codigo_do_campus) REFERENCES campus(codigo_do_campus)
            );

            DROP TABLE IF EXISTS curso;
            CREATE TABLE curso (
                codigo_do_curso INTEGER PRIMARY KEY,
                nome_do_curso TEXT NOT NULL,
                modalidade_academica TEXT,
                turno TEXT,
                periodo_de_inicio TEXT,
                data_de_funcionamento TEXT,
                area_de_retencao TEXT,
                ciclo_enade TEXT,
                codigo_da_unidade INTEGER NOT NULL,
                nome_da_unidade TEXT NOT NULL,
                sigla_da_unidade TEXT,
                codigo_do_centro INTEGER NOT NULL,
                nome_do_centro TEXT NOT NULL,
                sigla_do_centro TEXT,
                codigo_do_campus INTEGER NOT NULL,
                nome_do_campus TEXT NOT NULL,
                codigo_do_curriculo TEXT,
                duracao_minima INTEGER,
                duracao_maxima INTEGER,
                duracao_media INTEGER,
                carga_horaria_disciplinas_obrigatorias_minima INTEGER,
                carga_horaria_disciplinas_optativas_minima INTEGER,
                carga_horaria_atividades_complementares_minima INTEGER,
                carga_horaria_minima_total INTEGER,
                minimo_creditos_disciplinas_optativas INTEGER,
                minimo_creditos_total INTEGER,
                FOREIGN KEY (codigo_da_unidade) REFERENCES unidade(codigo_da_unidade),
                FOREIGN KEY (codigo_do_centro) REFERENCES centro(codigo_do_centro),
                FOREIGN KEY (codigo_do_campus) REFERENCES campus(codigo_do_campus)
            );
        """)
        conn.executemany("INSERT OR REPLACE INTO campus VALUES (?, ?)", campi.values())
        conn.executemany("INSERT OR REPLACE INTO centro VALUES (?, ?, ?, ?, ?)", centros.values())
        conn.executemany("INSERT OR REPLACE INTO unidade VALUES (?, ?, ?, ?, ?, ?, ?)", unidades.values())
        conn.executemany(
            "INSERT INTO curso VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            cursos_por_codigo.values(),
        )

    return {
        "campus": len(campi), "centro": len(centros),
        "unidade": len(unidades), "curso": len(cursos_por_codigo),
    }


if __name__ == "__main__":
    for tabela, total in criar_estrutura().items():
        print(f"{tabela}: {total} registros")
