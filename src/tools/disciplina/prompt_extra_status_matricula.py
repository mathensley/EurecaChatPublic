PROMPT_EXTRA_STATUS_ESTUDANTE = """
nome da tabela: 'Estudante_na_Disciplina'.

Os status do estudante é um ENUM e podem ser:

- 'Reprovado'
- 'Reprovado Por Média e Por Faltas'
- 'Cancelado' Explicação: cancelou a matrícula na disciplina
- 'Trancado' Explicação: cancelou a matrícula na disciplina depois que as aulas começaram (o estudante tem alguns dias para trancar no início das aulas, depois disso não tem como trancar mais)
- 'Aprovado' Explicação: passou na disciplina.
- 'Transferido'
- 'Indeferido' Explicação: não conseguiu vagas na disciplina.
- 'Desistencia' Explicação: o estudante colocou a disciplina mas desistiu de cursar a disciplina antes das aulas começarem. Pode ser porque ele se matriculou em outra turma da disciplina ou simplesmente não quis mais a disciplina.
- 'Em Curso' Explicação: (para quando está cursando a disciplina atualmente).

Quando a pergunta envolver reprovação em geral sem especificar se foi por nota ou por falta use: 'Reprovado' OR 'Reprovado Por Média e Por Faltas'.
Os estudantes que estão matriculados, estudando na disciplina são os 'Em curso', 'Aprovado', 'Reprovado' ou 'Reprovado Por Média e Por Faltas'
Seria interessante você responder para cada tipo de status se puder.
Além disso, como a(s) disciplina(s) podem ter estudantes de vários cursos, seria bom que a consulta SQL mostrasse dados por cada curso nas(s) disciplina(s).

Raciocine como responder bem essa pergunta observando as colunas e os tipos
"""