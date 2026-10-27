import sqlite3
from pathlib import Path


# ============================================================
# CONFIGURAÇÃO
# ============================================================

UFCG_DB = Path("ufcg_com_chaves_estrangeiras.sqlite")
PROFESSOR_DB = Path("professor_disciplina.sqlite")


if not UFCG_DB.exists():
    raise FileNotFoundError(
        f"Banco não encontrado: {UFCG_DB}"
    )

if not PROFESSOR_DB.exists():
    raise FileNotFoundError(
        f"Banco não encontrado: {PROFESSOR_DB}"
    )


# ============================================================
# CONEXÃO
# ============================================================

with sqlite3.connect(UFCG_DB) as conn:

    conn.row_factory = sqlite3.Row

    conn.execute(
        "ATTACH DATABASE ? AS professor_db",
        (str(PROFESSOR_DB.resolve()),)
    )

    # ========================================================
    # TOTAL
    # ========================================================

    total = conn.execute("""
        SELECT COUNT(*) AS quantidade
        FROM inscricao;
    """).fetchone()["quantidade"]


    print()
    print("=" * 80)
    print("ANÁLISE COMPLETA DOS DADOS DA INSCRIÇÃO")
    print("=" * 80)

    print(
        f"Total de inscrições: "
        f"{total:,}"
    )


    # ========================================================
    # TODAS AS 8 COMBINAÇÕES POSSÍVEIS
    #
    # codigo
    # periodo
    # turma
    #
    # 2^3 = 8 possibilidades
    # ========================================================

    combinacoes = conn.execute("""
        SELECT
            CASE
                WHEN codigo_da_disciplina IS NOT NULL
                THEN 1
                ELSE 0
            END AS tem_codigo,

            CASE
                WHEN periodo IS NOT NULL
                THEN 1
                ELSE 0
            END AS tem_periodo,

            CASE
                WHEN turma IS NOT NULL
                THEN 1
                ELSE 0
            END AS tem_turma,

            COUNT(*) AS quantidade

        FROM inscricao

        GROUP BY
            tem_codigo,
            tem_periodo,
            tem_turma;
    """).fetchall()


    # Inicializa TODAS as combinações.
    # Isso garante que uma combinação inexistente
    # apareça como 0.

    contagens = {
        (1, 1, 1): 0,
        (1, 1, 0): 0,
        (1, 0, 1): 0,
        (1, 0, 0): 0,
        (0, 1, 1): 0,
        (0, 1, 0): 0,
        (0, 0, 1): 0,
        (0, 0, 0): 0,
    }


    for row in combinacoes:

        chave = (
            row["tem_codigo"],
            row["tem_periodo"],
            row["tem_turma"],
        )

        contagens[chave] = row["quantidade"]


    print()
    print("=" * 80)
    print("COMBINAÇÕES DE CÓDIGO + PERÍODO + TURMA")
    print("=" * 80)

    print(
        f"{'Código + Período + Turma':40}"
        f"{contagens[(1, 1, 1)]:>15,}"
    )

    print(
        f"{'Código + Período':40}"
        f"{contagens[(1, 1, 0)]:>15,}"
    )

    print(
        f"{'Código + Turma':40}"
        f"{contagens[(1, 0, 1)]:>15,}"
    )

    print(
        f"{'Somente Código':40}"
        f"{contagens[(1, 0, 0)]:>15,}"
    )

    print(
        f"{'Período + Turma':40}"
        f"{contagens[(0, 1, 1)]:>15,}"
    )

    print(
        f"{'Somente Período':40}"
        f"{contagens[(0, 1, 0)]:>15,}"
    )

    print(
        f"{'Somente Turma':40}"
        f"{contagens[(0, 0, 1)]:>15,}"
    )

    print(
        f"{'Nenhum dos três':40}"
        f"{contagens[(0, 0, 0)]:>15,}"
    )

    print("-" * 55)

    total_combinacoes = sum(contagens.values())

    print(
        f"{'TOTAL':40}"
        f"{total_combinacoes:>15,}"
    )


    # ========================================================
    # NULL INDIVIDUALMENTE
    # ========================================================

    nulls = conn.execute("""
        SELECT

            SUM(
                CASE
                    WHEN codigo_da_disciplina IS NULL
                    THEN 1
                    ELSE 0
                END
            ) AS codigo_null,

            SUM(
                CASE
                    WHEN periodo IS NULL
                    THEN 1
                    ELSE 0
                END
            ) AS periodo_null,

            SUM(
                CASE
                    WHEN turma IS NULL
                    THEN 1
                    ELSE 0
                END
            ) AS turma_null,

            SUM(
                CASE
                    WHEN matricula_do_professor IS NULL
                    THEN 1
                    ELSE 0
                END
            ) AS professor_null

        FROM inscricao;
    """).fetchone()


    print()
    print("=" * 80)
    print("NULL POR CAMPO")
    print("=" * 80)

    print(
        f"Código da disciplina NULL: "
        f"{nulls['codigo_null']:,}"
    )

    print(
        f"Período NULL:              "
        f"{nulls['periodo_null']:,}"
    )

    print(
        f"Turma NULL:                "
        f"{nulls['turma_null']:,}"
    )

    print(
        f"Professor NULL:            "
        f"{nulls['professor_null']:,}"
    )


    # ========================================================
    # PROFESSORES POR
    #
    # CÓDIGO + PERÍODO + TURMA
    # ========================================================

    analise_turma = conn.execute("""
        SELECT
            pd.codigo_da_disciplina,
            pd.periodo,
            pd.turma,

            COUNT(
                DISTINCT pd.matricula_do_docente
            ) AS quantidade_professores

        FROM professor_db.professor_disciplina AS pd

        WHERE pd.codigo_da_disciplina IS NOT NULL
          AND pd.periodo IS NOT NULL
          AND pd.turma IS NOT NULL

        GROUP BY
            pd.codigo_da_disciplina,
            pd.periodo,
            pd.turma;
    """).fetchall()


    turma_um_professor = 0
    turma_varios_professores = 0


    for row in analise_turma:

        if row["quantidade_professores"] == 1:

            turma_um_professor += 1

        elif row["quantidade_professores"] > 1:

            turma_varios_professores += 1


    print()
    print("=" * 80)
    print("PROFESSORES POR DISCIPLINA + PERÍODO + TURMA")
    print("=" * 80)

    print(
        f"Combinações código + período + turma: "
        f"{len(analise_turma):,}"
    )

    print(
        f"1 professor:                            "
        f"{turma_um_professor:,}"
    )

    print(
        f"Mais de 1 professor:                    "
        f"{turma_varios_professores:,}"
    )


    # ========================================================
    # CÓDIGO + PERÍODO
    #
    # Quantas turmas e professores existem?
    # ========================================================

    analise_periodo = conn.execute("""
        SELECT
            pd.codigo_da_disciplina,
            pd.periodo,

            COUNT(
                DISTINCT pd.turma
            ) AS quantidade_turmas,

            COUNT(
                DISTINCT pd.matricula_do_docente
            ) AS quantidade_professores

        FROM professor_db.professor_disciplina AS pd

        WHERE pd.codigo_da_disciplina IS NOT NULL
          AND pd.periodo IS NOT NULL

        GROUP BY
            pd.codigo_da_disciplina,
            pd.periodo;
    """).fetchall()


    uma_turma = 0
    varias_turmas = 0

    um_professor = 0
    varios_professores = 0

    uma_turma_um_professor = 0
    uma_turma_varios_professores = 0
    varias_turmas_um_professor = 0
    varias_turmas_varios_professores = 0


    for row in analise_periodo:

        turmas = row["quantidade_turmas"]
        professores = row["quantidade_professores"]


        if turmas == 1:

            uma_turma += 1

        elif turmas > 1:

            varias_turmas += 1


        if professores == 1:

            um_professor += 1

        elif professores > 1:

            varios_professores += 1


        if turmas == 1 and professores == 1:

            uma_turma_um_professor += 1

        elif turmas == 1 and professores > 1:

            uma_turma_varios_professores += 1

        elif turmas > 1 and professores == 1:

            varias_turmas_um_professor += 1

        elif turmas > 1 and professores > 1:

            varias_turmas_varios_professores += 1


    print()
    print("=" * 80)
    print("PROFESSORES E TURMAS POR CÓDIGO + PERÍODO")
    print("=" * 80)

    print(
        f"Combinações código + período: "
        f"{len(analise_periodo):,}"
    )

    print()

    print(
        f"1 única turma:                       "
        f"{uma_turma:,}"
    )

    print(
        f"Mais de uma turma:                   "
        f"{varias_turmas:,}"
    )

    print()

    print(
        f"1 único professor:                   "
        f"{um_professor:,}"
    )

    print(
        f"Mais de um professor:                "
        f"{varios_professores:,}"
    )

    print()

    print(
        f"1 turma + 1 professor:               "
        f"{uma_turma_um_professor:,}"
    )

    print(
        f"1 turma + vários professores:        "
        f"{uma_turma_varios_professores:,}"
    )

    print(
        f"Várias turmas + 1 professor:         "
        f"{varias_turmas_um_professor:,}"
    )

    print(
        f"Várias turmas + vários professores:  "
        f"{varias_turmas_varios_professores:,}"
    )


    # ========================================================
    # PROFESSOR NULL COM CHAVE COMPLETA
    #
    # CÓDIGO + PERÍODO + TURMA
    # ========================================================

    professor_null_com_chave = conn.execute("""
        SELECT COUNT(*) AS quantidade

        FROM inscricao AS i

        WHERE i.matricula_do_professor IS NULL

          AND i.codigo_da_disciplina IS NOT NULL
          AND i.periodo IS NOT NULL
          AND i.turma IS NOT NULL;
    """).fetchone()["quantidade"]


    print()
    print("=" * 80)
    print("PROFESSOR NULL COM CÓDIGO + PERÍODO + TURMA")
    print("=" * 80)

    print(
        f"Inscrições: "
        f"{professor_null_com_chave:,}"
    )


    # ========================================================
    # TURMA NULL + CÓDIGO + PERÍODO
    # ========================================================

    turma_null = conn.execute("""
        SELECT COUNT(*) AS quantidade

        FROM inscricao AS i

        WHERE i.turma IS NULL
          AND i.codigo_da_disciplina IS NOT NULL
          AND i.periodo IS NOT NULL;
    """).fetchone()["quantidade"]


    print()
    print("=" * 80)
    print("TURMA NULL + CÓDIGO + PERÍODO")
    print("=" * 80)

    print(
        f"Inscrições analisáveis: "
        f"{turma_null:,}"
    )


    # ========================================================
    # RECUPERAÇÃO DA TURMA
    #
    # Para cada inscrição:
    #
    # código + período
    #
    # quantas turmas existem na referência?
    # ========================================================

    recuperacao_turma = conn.execute("""
        SELECT

            CASE

                WHEN COUNT(
                    DISTINCT pd.turma
                ) = 0

                    THEN 'SEM_CORRESPONDENCIA'

                WHEN COUNT(
                    DISTINCT pd.turma
                ) = 1

                    THEN 'UMA_TURMA'

                ELSE 'VARIAS_TURMAS'

            END AS situacao,

            COUNT(*) AS quantidade

        FROM inscricao AS i

        LEFT JOIN professor_db.professor_disciplina AS pd

            ON pd.codigo_da_disciplina =
                i.codigo_da_disciplina

            AND pd.periodo =
                i.periodo

        WHERE i.turma IS NULL

          AND i.codigo_da_disciplina IS NOT NULL
          AND i.periodo IS NOT NULL

        GROUP BY
            i.id_inscricao;
    """).fetchall()


    recuperacao_turma_resultado = {
        "UMA_TURMA": 0,
        "VARIAS_TURMAS": 0,
        "SEM_CORRESPONDENCIA": 0,
    }


    for row in recuperacao_turma:

        recuperacao_turma_resultado[
            row["situacao"]
        ] += 1


    print()
    print(
        f"Uma única turma encontrada:         "
        f"{recuperacao_turma_resultado['UMA_TURMA']:,}"
    )

    print(
        f"Várias turmas encontradas:          "
        f"{recuperacao_turma_resultado['VARIAS_TURMAS']:,}"
    )

    print(
        f"Sem correspondência:                "
        f"{recuperacao_turma_resultado['SEM_CORRESPONDENCIA']:,}"
    )


    # ========================================================
    # ANÁLISE FINAL DA TURMA NULL
    #
    # Depois de descobrir a turma:
    #
    # verifica quantos professores existem naquela turma.
    # ========================================================

    resultado_final = conn.execute("""
        SELECT

            CASE

                WHEN COUNT(DISTINCT pd.turma) = 0

                    THEN 'SEM_CORRESPONDENCIA'

                WHEN COUNT(DISTINCT pd.turma) > 1

                    THEN 'TURMA_AMBIGUA'

                WHEN COUNT(
                    DISTINCT pd.matricula_do_docente
                ) = 0

                    THEN 'SEM_PROFESSOR'

                WHEN COUNT(
                    DISTINCT pd.matricula_do_docente
                ) = 1

                    THEN 'TURMA_E_PROFESSOR_SEGUROS'

                ELSE 'TURMA_SEGURA_PROFESSOR_AMBIGUO'

            END AS situacao,

            COUNT(*) AS quantidade

        FROM inscricao AS i

        LEFT JOIN professor_db.professor_disciplina AS pd

            ON pd.codigo_da_disciplina =
                i.codigo_da_disciplina

            AND pd.periodo =
                i.periodo

        WHERE i.turma IS NULL

          AND i.codigo_da_disciplina IS NOT NULL
          AND i.periodo IS NOT NULL

        GROUP BY
            i.id_inscricao;
    """).fetchall()


    resultado_final_dict = {
        "SEM_CORRESPONDENCIA": 0,
        "TURMA_AMBIGUA": 0,
        "SEM_PROFESSOR": 0,
        "TURMA_E_PROFESSOR_SEGUROS": 0,
        "TURMA_SEGURA_PROFESSOR_AMBIGUO": 0,
    }


    for row in resultado_final:

        resultado_final_dict[
            row["situacao"]
        ] += 1


    print()
    print("=" * 80)
    print("TURMA NULL — ANÁLISE FINAL")
    print("=" * 80)

    print(
        f"Turma e professor seguros:           "
        f"{resultado_final_dict['TURMA_E_PROFESSOR_SEGUROS']:,}"
    )

    print(
        f"Turma segura, professor ambíguo:     "
        f"{resultado_final_dict['TURMA_SEGURA_PROFESSOR_AMBIGUO']:,}"
    )

    print(
        f"Turma ambígua:                        "
        f"{resultado_final_dict['TURMA_AMBIGUA']:,}"
    )

    print(
        f"Sem professor na referência:          "
        f"{resultado_final_dict['SEM_PROFESSOR']:,}"
    )

    print(
        f"Sem correspondência:                  "
        f"{resultado_final_dict['SEM_CORRESPONDENCIA']:,}"
    )


    # ========================================================
    # RESUMO
    # ========================================================

    print()
    print("=" * 80)
    print("RESUMO")
    print("=" * 80)

    print(
        f"Total de inscrições:                  "
        f"{total:,}"
    )

    print(
        f"Código NULL:                          "
        f"{nulls['codigo_null']:,}"
    )

    print(
        f"Período NULL:                         "
        f"{nulls['periodo_null']:,}"
    )

    print(
        f"Turma NULL:                           "
        f"{nulls['turma_null']:,}"
    )

    print(
        f"Professor NULL:                       "
        f"{nulls['professor_null']:,}"
    )

    print()
    print("Nenhum dado foi alterado.")