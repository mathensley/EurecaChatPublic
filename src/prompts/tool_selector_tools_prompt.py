DEFAULT_TOOL_CATALOG_PROMPT = """
## Catálogo de ferramentas disponíveis

Use somente os nomes presentes neste catálogo. As descrições abaixo foram escritas para distinguir ferramentas parecidas; dê atenção especial às regras "não use".

{tool_catalog}

## Regras para usar o catálogo

- Escolha pelo objetivo que ainda precisa ser atendido, não apenas por palavras isoladas da mensagem.
- Em continuações como "o primeiro" ou "essa opção", identifique no histórico a solicitação original e selecione a ferramenta correspondente a ela.
- Se duas ferramentas parecerem relacionadas, prefira aquela cuja descrição diga explicitamente que fornece o dado pedido. Em caso de dúvida, escolha as duas.
- Não escolha uma ferramenta citada apenas em um assunto antigo ou em um resultado que já resolveu a solicitação atual.
""".strip()


TOOL_SELECTOR_DESCRIPTIONS = {
    "buscar_fluxograma": """
Use para retornar o fluxograma completo de um curso em texto e PDF, consultar uma disciplina da grade ou listar as disciplinas recomendadas para um semestre ideal específico.
Exige o curso, inclusive quando uma disciplina for informada. Não use para horários, turmas, vagas ou disciplinas ofertadas em um período letivo.
Para métricas agregadas do currículo, como duração total e quantidade de créditos, use buscar_grade_curricular_curso.
""".strip(),
    "buscar_disciplinas": """
Use para o fluxograma de um curso, para listar as disciplinas que compõem sua grade e para consultar dados de uma disciplina, 
como código, créditos, carga horária, período ideal, pré-requisitos e ementa. Não use para horários, turmas ou vagas. 
Para métricas agregadas do currículo, como duração total e quantidade de créditos, use buscar_grade_curricular_curso.
""".strip(),
    "buscar_horarios_turmas_vagas_disciplina": """
Use para oferta de uma disciplina: horários, turmas, vagas, salas e período em que ela está sendo oferecida.
Não use para saber quando o semestre começa ou termina; datas do calendário acadêmico pertencem a buscar_calendarios. Não use para fluxograma.
""".strip(),
    "buscar_estudantes_disciplinas": """
Use quando a pergunta relacionar estudantes ou professores a disciplinas, turmas e períodos: 
matrículas em disciplina, notas, aprovações, reprovações, dificuldade, quantidade de matriculados ou turmas lecionadas.
Não use para dados gerais de estudantes de um curso sem disciplina específica; nesse caso use buscar_dados_gerais_de_todos_estudantes. 
Para o histórico do próprio aluno autenticado, use a ferramenta pessoal correspondente somente se ela estiver presente no catálogo.
""".strip(),
    "buscar_plano_curso_disciplina": """
Use para o plano de curso detalhado de uma disciplina: conteúdo programático, objetivos, metodologia, avaliação, bibliografia e ementa no contexto do plano.
Não use para fluxograma, lista de disciplinas, horários, turmas ou vagas.
""".strip(),
    "buscar_dados_gerais_de_todos_estudantes": """
Use para dados e estatísticas de estudantes matriculados em um curso, campus, centro ou em toda a UFCG, sem foco em uma disciplina: 
quantidade de alunos, matrículas anonimizadas, perfil demográfico, situação, deficiência. Métricas como: MC, IEA, IRA, MCN, IEAN, IECH, IEPL, IECHP e rendimento geral.
Não use para notas ou matrículas em uma disciplina específica. Não use para os dados pessoais do próprio aluno autenticado; 
nesse caso use a ferramenta pessoal correspondente somente se ela estiver presente no catálogo.
""".strip(),
    "buscar_todos_os_cursos": """
Use para perguntas gerais sobre o conjunto de cursos da UFCG, como listar, contar ou comparar cursos, turnos, graus, campi, modalidades e status, 
sem que o pedido esteja centrado em um curso específico. Não use quando o usuário nomear um curso específico, nem para disciplinas,
estudantes, vagas ou currículo detalhado desse curso.
""".strip(),
    "buscar_curso_especifico": """
Use para informações básicas de um curso específico identificado pelo nome ou código: código, grau, turno, campus, setor, data ou período de início e código INEP.
Não use para fluxograma ou disciplinas. Não use para duração, carga horária e créditos do currículo; para isso use buscar_grade_curricular_curso.
""".strip(),
    "buscar_grade_curricular_curso": """
Use para características agregadas do currículo de um curso: código do currículo, regime, duração, carga horária total, número de créditos, 
atividades e disciplinas, incluindo consulta a currículos anteriores. Não use para retornar o fluxograma ou a lista das disciplinas da grade; 
para isso use buscar_fluxograma.
""".strip(),
    "buscar_todos_setores": """
Use para centros, unidades acadêmicas e setores da UFCG, inclusive para listar os cursos associados a cada setor e filtrar por campus.
Não use para detalhes acadêmicos de um curso, currículo, disciplina ou aluno.
""".strip(),
    "buscar_calendarios": """
Use para calendário acadêmico e períodos letivos: início e fim das aulas, próximo semestre, período atual, início de matrículas, 
semanas de aula e prazo final para lançamento de notas.
Não use para o horário, turma, sala ou vagas de uma disciplina; para isso use buscar_horarios_turmas_vagas_disciplina.
""".strip(),
    "busca_portal_ufcg": """
Use para informações públicas do portal institucional: notícias, comunicados, editais, contatos, páginas e links oficiais, 
processos seletivos e informações recentes sobre SISU. Não use para dados estruturados de cursos, currículos, disciplinas ou pessoas.
Não use para responder o que o assistente sabe fazer.
""".strip(),
    "estudante_info": """
Use somente para um aluno autenticado perguntando em primeira pessoa sobre os
próprios dados gerais: CRA, MC, dados cadastrais, créditos, curso, quantidade de
períodos concluídos e período atual.
Para suas disciplinas cursadas, notas e aprovações, use historico_estudante. Não
use para consultar outros estudantes ou estatísticas de um curso.
""".strip(),
    "historico_estudante": """
Use somente para um aluno autenticado perguntando em primeira pessoa sobre o próprio histórico acadêmico: disciplinas cursadas ou atuais, notas, aprovações,
reprovações, dispensas, turmas e períodos das matrículas.
Para dados gerais como CRA, cadastro e total de créditos, use estudante_info. Não use para dados agregados de outros estudantes.
""".strip(),
    "professor_info": """
Use somente para um professor autenticado perguntando em primeira pessoa sobre os próprios dados: cadastro, SIAPE, titulação, departamento, campus, e-mail,
disciplinas e turmas que leciona ou já lecionou. Não use para estatísticas gerais de docentes ou para informações de outro professor.
""".strip(),
}
