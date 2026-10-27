"""
Expectation Suite para a tabela: estudantes_ufcg
Banco de dados: estudantes_ufcg.sqlite

NOTAS:
  - 'turno_do_curso' e 'politica_afirmativa' estão 100% nulas 
  - 'motivo_de_evasao' está 100% nula
  - 'sexo' possui valor 'N' além de MASCULINO/FEMININO 
  - 'idade' possui outliers (max=1819), sinalizados como dado suspeito
  - 'cotista' só tem o valor 'NAO' 
"""

import great_expectations as gx


def build_suite() -> gx.ExpectationSuite:
    suite = gx.ExpectationSuite(name="suite_estudantes_ufcg")

    # matricula_do_estudante (TEXT, PK)

    # Não deve ter nulos
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="matricula_do_estudante")
    )

    # Deve ser única (é a chave primária)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeUnique(column="matricula_do_estudante")
    )

    # Deve ser numérico 
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
  
    # nome_do_curso (TEXT)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="nome_do_curso")
    )
    # Deve ter ao menos 3 caracteres
    suite.add_expectation(
        gx.expectations.ExpectColumnValueLengthsToBeBetween(
            column="nome_do_curso", min_value=3, max_value=200
        )
    )

    # turno_do_curso (TEXT)
    # NOTA: coluna está 100% nula na base — apenas validamos que a coluna existe
    suite.add_expectation(
        gx.expectations.ExpectColumnToExist(column="turno_do_curso")
    )

    # codigo_do_curriculo (INTEGER)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="codigo_do_curriculo")
    )
    # Range observado: 1979 a 7142
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="codigo_do_curriculo", min_value=1000, max_value=10000
        )
    )

    # campus (INTEGER)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="campus")
    )
    # Range observado: 1 a 9 (9 campi da UFCG)
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

    # estado_civil (TEXT)
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
    # NOTA: valor 'N' está presente nos dados (dado inconsistente real)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="sexo")
    )
    # Validação estrita: apenas MASCULINO ou FEMININO são valores válidos
    # (O valor 'N' irá gerar falha, sendo identificado como dado inconsistente)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="sexo",
            value_set=["MASCULINO", "FEMININO"],
            mostly=0.99  # Tolera até 1% de valores fora do padrão
        )
    )

    # idade (INTEGER)
    # NOTA: max=1819 é dado claramente inválido — a expectation sinalizará isso
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="idade")
    )
    # Faixa plausível para seres humanos
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

    # motivo_de_evasao (TEXT) — 100% nula na base
    suite.add_expectation(
        gx.expectations.ExpectColumnToExist(column="motivo_de_evasao")
    )

    # periodo_de_evasao (TEXT) — formato YYYY.S (ex: 2024.2)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToMatchRegex(
            column="periodo_de_evasao",
            regex=r"^\d{4}\.[012]$",
            mostly=0.98  # Alguns nulos são esperados (estudantes ativos não têm evasão)
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
    # Quando não nulo, deve ter ao menos 2 caracteres
    suite.add_expectation(
        gx.expectations.ExpectColumnValueLengthsToBeBetween(
            column="nacionalidade", min_value=2, max_value=100,
            mostly=0.95
        )
    )

    # local_de_nascimento (TEXT) — muitos nulos esperados
    suite.add_expectation(
        gx.expectations.ExpectColumnToExist(column="local_de_nascimento")
    )

    # naturalidade (TEXT) — UF brasileira ou nula
    suite.add_expectation(
        gx.expectations.ExpectColumnToExist(column="naturalidade")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToMatchRegex(
            column="naturalidade",
            regex=r"^[A-Z]{2}$",
            mostly=0.95  # Nulos e estrangeiros são esperados
        )
    )

    # cor (TEXT)
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

    # deficiencias (TEXT) — muitos nulos (a maioria não tem deficiência)
    suite.add_expectation(
        gx.expectations.ExpectColumnToExist(column="deficiencias")
    )

    # ano_de_conclusao_ensino_medio (INTEGER)
    # NOTA: max=3013 é dado claramente inválido — expectation sinalizará
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="ano_de_conclusao_ensino_medio")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="ano_de_conclusao_ensino_medio", min_value=1960, max_value=2026,
           # mostly=0.95  # Tolera valor 0 (não informado) e anos mais antigos
        )
    )

    # tipo_de_ensino_medio (TEXT) — possui nulos
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

    # politica_afirmativa (TEXT) — 100% nula na base
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

    #  creditos_isentos (INTEGER)
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

    # creditos_em_andamento (INTEGER)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="creditos_em_andamento")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="creditos_em_andamento", min_value=0, max_value=60
        )
    )

    #  velocidade_media (REAL)
    # ==================================
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="velocidade_media")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="velocidade_media", min_value=0.0, max_value=300.0
        )
    )

    # taxa_de_sucesso (REAL) — deve estar entre 0 e 1 (proporção)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="taxa_de_sucesso")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="taxa_de_sucesso", min_value=0.0, max_value=1.0
        )
    )

    # renda_per_capita_ate (REAL) — todos zeros na base (campo não preenchido)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="renda_per_capita_ate")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(
            column="renda_per_capita_ate", min_value=0.0, max_value=100000.0
        )
    )

    # mc (REAL) — Média do Curso, deve estar entre 0 e 10
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

    # cotista (TEXT) — apenas 'NAO' observado (dado possivelmente incompleto)
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="cotista")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeInSet(
            column="cotista",
            value_set=["SIM", "NAO"]
        )
    )

    return suite
