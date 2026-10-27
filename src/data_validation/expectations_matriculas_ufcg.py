"""
Expectation Suite para a tabela: matriculas_ufcg
Banco de dados: matriculas_ufcg.sqlite

NOTAS:
  - 'turno_do_curso' e 'politica_afirmativa' estão 100% nulas
  - 'motivo_de_evasao' está 100% nula
  - 'dispensas' está 100% nula
  - 'sexo' possui valor 'N' além de MASCULINO/FEMININO
  - 'idade' possui outliers (max=1819)
  - 'periodo' possui ~4.898 nulos
  - 'turma' possui ~362.960 nulos
  - 'media_final' possui ~277.421 nulos (disciplinas em curso)
  - 'tipo' possui ~130.044 nulos
"""

import great_expectations as gx


def build_suite() -> gx.ExpectationSuite:
    suite = gx.ExpectationSuite(name="suite_matriculas_ufcg")

    # ─────────────────────────────────────────────────────────────────────────
    # BLOCO A: Colunas herdadas do cadastro do estudante
    # ─────────────────────────────────────────────────────────────────────────

    # matricula_do_estudante (TEXT) — NÃO é única aqui (1 estudante N disciplinas)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="matricula_do_estudante")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToMatchRegex(
            column="matricula_do_estudante",
            regex=r"^\d+$"
        )
    )

    # codigo_do_curso (INTEGER)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="codigo_do_curso")
    )
   
    #  nome_do_curso (TEXT)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="nome_do_curso")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValueLengthsToBeBetween(
            column="nome_do_curso", min_value=3, max_value=200
        )
    )

    # turno_do_curso (TEXT) — 100% nula
    suite.add_expectation(
        gx.expectations.ExpectColumnToExist(column="turno_do_curso")
    )

    # codigo_do_curriculo (INTEGER)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="codigo_do_curriculo")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="codigo_do_curriculo", min_value=1000, max_value=10000
        )
    )

    # campus (INTEGER)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="campus")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="campus", min_value=1, max_value=9
        )
    )

    # nome_do_campus (TEXT)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="nome_do_campus")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="nome_do_campus",
            value_set=[
                "Campina Grande", "Sumé", "Patos", "Sousa",
                "Cuité", "Cajazeiras", "Pombal"
            ]
        )
    )

    # codigo_do_setor (INTEGER)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="codigo_do_setor")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="codigo_do_setor", min_value=1000, max_value=200000
        )
    )

    # nome_do_setor (TEXT)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="nome_do_setor")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="nome_do_setor",
            value_set=[
                "CCT - CENTRO DE CIENCIAS E TECNOLOGIA",
                "CDSA - CENTRO DE DESENVOLVIMENTO DO SEMI-ARIDO",
                "CH - CENTRO DE HUMANIDADES",
                "CSTR - CENTRO DE SAUDE E TECNOLOGIA RURAL",
                "CEEI - CENTRO DE ENG. ELETRICA E INFORMATICA",
                "CCJS - CENTRO DE CIENCIAS JURIDICAS E SOCIAIS",
                "CTRN - CENTRO DE TECNOLOGIA E RECURSOS NATURAIS",
                "CES - CENTRO DE EDUCACAO E SAUDE - CUITE",
                "CFP - CENTRO DE FORMACAO DE PROFESSORES",
                "CCTA - CENTRO DE CIENCIAS TEC. AGROALIMENTAR",
                "CCBS - CENTRO DE CIENCIAS BIOLOGICAS E DA SAUDE",
            ]
        )
    )

    #  estado_civil (TEXT)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="estado_civil")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="estado_civil",
            value_set=[
                "Solteiro", "Casado", "Divorciado", "Viúvo",
                "Separado Judicialmente", "Outro", "Não Informado", ""
            ]
        )
    )

    # sexo (TEXT)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="sexo")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="sexo",
            value_set=["MASCULINO", "FEMININO"],
            mostly=0.99
        )
    )

    #  idade (INTEGER) — máximo observado de 1819 é dado inválido
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="idade")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="idade", min_value=10, max_value=90
        )
    )

    # situacao (TEXT)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="situacao")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="situacao",
            value_set=[
                "ATIVO", "CANCELADO", "CONCLUÍDO", "TRANCADO",
                "ATIVO - FORMANDO", "CADASTRADO", "FORMADO",
                "NÃO CADASTRADO", "DESCONHECIDO"
            ]
        )
    )

    # motivo_de_evasao (TEXT) — 100% nula
    suite.add_expectation(
        gx.expectations.ExpectColumnToExist(column="motivo_de_evasao")
    )

    # periodo_de_evasao (TEXT) — formato YYYY.S
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToMatchRegex(
            column="periodo_de_evasao",
            regex=r"^\d{4}\.[012]$",
            mostly=0.98
        )
    )

    # forma_de_ingresso (TEXT)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="forma_de_ingresso")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="forma_de_ingresso",
            value_set=[
                "SiSU", "VESTIBULAR", "REOPCAO", "PORTADOR DE DIPLOMA",
                "TRANSFERÊNCIA VOLUNTÁRIA", "REOCUPAÇÃO DE VAGAS RESIDUAIS",
                "JUDICIAL", "NAO INFORMADO", "PROCESSO SELETIVO ESPECÍFICO",
                "TRANSF. COMPULSORIA", "CONVENIO PEC-G", "ALUNO ESPECIAL",
                "MOBILIDADE ESTUDANTIL", "PROCESSO SELETIVO", "PARFOR",
                "ALUNO EM MOBILIDADE INTERNACIONAL"
            ]
        )
    )

    # periodo_de_ingresso (TEXT) — formato YYYY.S
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="periodo_de_ingresso")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToMatchRegex(
            column="periodo_de_ingresso",
            regex=r"^\d{4}\.[012]$"
        )
    )

    # nacionalidade (TEXT) — possui nulos e vazios
    suite.add_expectation(
        gx.expectations.ExpectColumnToExist(column="nacionalidade")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValueLengthsToBeBetween(
            column="nacionalidade", min_value=2, max_value=100,
            mostly=0.95
        )
    )

    # local_de_nascimento (TEXT) — muitos nulos
    suite.add_expectation(
        gx.expectations.ExpectColumnToExist(column="local_de_nascimento")
    )

    # naturalidade (TEXT) — sigla de UF, ou nulo
    suite.add_expectation(
        gx.expectations.ExpectColumnToExist(column="naturalidade")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToMatchRegex(
            column="naturalidade",
            regex=r"^[A-Z]{2}$",
            mostly=0.95
        )
    )

    #  cor (TEXT)
    suite.add_expectation(
        gx.expectations.ExpectColumnToExist(column="cor")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="cor",
            value_set=[
                "Pardo", "Negro", "Branco", "Não Informado",
                "Amarelo (de origem oriental)", "Indígeno",
                "Remanescente de quilombo"
            ],
            mostly=0.95
        )
    )

    # deficiencias (TEXT) — muitos nulos
    suite.add_expectation(
        gx.expectations.ExpectColumnToExist(column="deficiencias")
    )

    #  ano_de_conclusao_ensino_medio (INTEGER)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="ano_de_conclusao_ensino_medio")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="ano_de_conclusao_ensino_medio", min_value=1970, max_value=2026,
            mostly=0.95
        )
    )

    #  tipo_de_ensino_medio (TEXT)
    suite.add_expectation(
        gx.expectations.ExpectColumnToExist(column="tipo_de_ensino_medio")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="tipo_de_ensino_medio",
            value_set=["Pública", "Privada", "Não Informado"],
            mostly=0.95
        )
    )

    #  politica_afirmativa (TEXT) — 100% nula
    suite.add_expectation(
        gx.expectations.ExpectColumnToExist(column="politica_afirmativa")
    )

    # creditos_do_cra (INTEGER)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="creditos_do_cra")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="creditos_do_cra", min_value=0, max_value=1000
        )
    )

    # notas_acumuladas (REAL)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="notas_acumuladas")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="notas_acumuladas", min_value=0.0, max_value=5000.0
        )
    )

    #  periodos_completados (INTEGER)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="periodos_completados")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="periodos_completados", min_value=0, max_value=60
        )
    )

    # creditos_tentados (INTEGER)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="creditos_tentados")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="creditos_tentados", min_value=0, max_value=1000
        )
    )

    # creditos_completados (INTEGER)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="creditos_completados")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="creditos_completados", min_value=0, max_value=1000
        )
    )

    # creditos_isentos (INTEGER)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="creditos_isentos")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="creditos_isentos", min_value=0, max_value=10
        )
    )

    # creditos_falhados (INTEGER)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="creditos_falhados")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="creditos_falhados", min_value=0, max_value=800
        )
    )

    # creditos_suspensos (INTEGER)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="creditos_suspensos")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="creditos_suspensos", min_value=0, max_value=400
        )
    )

    #  creditos_em_andamento (INTEGER)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="creditos_em_andamento")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="creditos_em_andamento", min_value=0, max_value=60
        )
    )

    # velocidade_media (REAL)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="velocidade_media")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="velocidade_media", min_value=0.0, max_value=300.0
        )
    )

    # taxa_de_sucesso (REAL) — proporção entre 0 e 1
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="taxa_de_sucesso")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="taxa_de_sucesso", min_value=0.0, max_value=1.0
        )
    )

    # renda_per_capita_ate (REAL)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="renda_per_capita_ate")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="renda_per_capita_ate", min_value=0.0, max_value=100000.0
        )
    )

    # mc (REAL) — Média do Curso, entre 0 e 10
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="mc")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="mc", min_value=0.0, max_value=10.0
        )
    )

    # tem_deficiencia (TEXT)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="tem_deficiencia")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="tem_deficiencia",
            value_set=["sim", "nao"]
        )
    )

    # cotista (TEXT)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="cotista")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="cotista",
            value_set=["SIM", "NAO"]
        )
    )

    # ─────────────────────────────────────────────────────────────────────────
    # BLOCO B: Colunas exclusivas de matrícula em disciplina
    # ─────────────────────────────────────────────────────────────────────────

    # codigo_da_disciplina (INTEGER)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="codigo_da_disciplina")
    )
  

    #  nome_da_disciplina (TEXT)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="nome_da_disciplina")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValueLengthsToBeBetween(
            column="nome_da_disciplina", min_value=2, max_value=300
        )
    )

    # periodo (TEXT) — formato YYYY.S, com ~4.898 nulos tolerados
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToMatchRegex(
            column="periodo",
            regex=r"^\d{4}\.[012]$",
            mostly=0.998  # ~4.898 nulos em 3.319.867 linhas ≈ 0.1%
        )
    )

    # turma (INTEGER) — ~362.960 nulos tolerados (matrícula sem turma atribuída)
    suite.add_expectation(
        gx.expectations.ExpectColumnToExist(column="turma")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="turma", min_value=0, max_value=99,
            mostly=0.89  # ~11% de nulos observados
        )
    )

    #  status (TEXT) — status da matrícula na disciplina
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="status")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="status",
            value_set=[
                "Aprovado", "Reprovado", "Reprovado Por Faltas",
                "Transferido", "Cancelado", "Trancado", "Indeferido",
                "Em Curso", "Excluida", "Reprovado Por Média E Por Faltas",
                "Desistencia", "Aprovado Por Nota", "Em Espera",
                "Dispensado", "Incorporado"
            ]
        )
    )

    # tipo (TEXT) — ~130.044 nulos (optativas sem classificação)
    suite.add_expectation(
        gx.expectations.ExpectColumnToExist(column="tipo")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="tipo",
            value_set=[
                "Obrigatória Da Grade", "Optativa Da Grade",
                "Extra Curricular", "Equivalente Obrigatória",
                "Equivalente Optativa Da Grade"
            ],
            mostly=0.96  # ~4% de nulos esperados
        )
    )

    # media_final (REAL) — ~277.421 nulos (disciplinas ainda em curso)
    suite.add_expectation(
        gx.expectations.ExpectColumnToExist(column="media_final")
    )
    # suite.add_expectation(
    #     gx.expectations.ExpectColumnValuesToBeBetween(
    #         column="media_final", min_value=0.0, max_value=10.0,
    #         mostly=0.91  
    #     )
    # )

    #  dispensas (REAL) — 100% nula na base
    suite.add_expectation(
        gx.expectations.ExpectColumnToExist(column="dispensas")
    )

    return suite
