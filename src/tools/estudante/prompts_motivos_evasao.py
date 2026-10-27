PROMPTS_MOTIVOS_EVASAO = """
nome da tabela: 'estudante_info_gerais'.

Esses valores abaixo corresponde a situação e motivo de saída do curso dos estudantes inativos, que podem ser usados para filtrar os estudantes inativos de acordo com a necessidade da pergunta feita pelo usuário.

situacao, motivo_que_saiu_do_curso

ATIVO: PRORROGAÇÃO POR TRANCAMENTO DE PROGRAMA
ATIVO: None
ATIVO: TRANCAMENTO DE PROGRAMA
ATIVO: PRORROGAÇÃO ADMINISTRATIVA
ATIVO: ABANDONO (NENHUMA MATRÍCULA)
ATIVO: DECURSO DE PRAZO MÁXIMO P/ CONCLUSÃO DE CURSO
ATIVO: PRORROGAÇÃO POR CADASTRAMENTO DE NOVO VÍNCULO
ATIVO: ANTECIPAÇÃO ADMINISTRATIVA
ATIVO: INSUFICIÊNCIA DE DESEMPENHO ACADÊMICO
ATIVO: EFETIVAÇÃO DE NOVO CADASTRO
ATIVO: SOLICITAÇÃO ESPONTÂNEA
ATIVO: INTEGRALIZAÇÃO DE DISCENTE
ATIVO - FORMANDO: None
ATIVO - FORMANDO: TRANCAMENTO DE PROGRAMA
ATIVO - FORMANDO: PRORROGAÇÃO ADMINISTRATIVA
ATIVO - FORMANDO: PRORROGAÇÃO POR TRANCAMENTO DE PROGRAMA
ATIVO - FORMANDO: INTEGRALIZAÇÃO DE DISCENTE
ATIVO - FORMANDO: ABANDONO (NENHUMA MATRÍCULA)
CADASTRADO: None
CANCELADO: ABANDONO (NENHUMA MATRÍCULA)
CANCELADO: DECURSO DE PRAZO MÁXIMO P/ CONCLUSÃO DE CURSO
CANCELADO: PRORROGAÇÃO POR TRANCAMENTO DE PROGRAMA
CANCELADO: SOLICITAÇÃO ESPONTÂNEA
CANCELADO: TRANCAMENTO DE PROGRAMA
CANCELADO: EFETIVAÇÃO DE NOVO CADASTRO
CANCELADO: None
CANCELADO: ABANDONO (NENHUMA INTEGRALIZAÇÃO)
CANCELADO: INSUFICIÊNCIA DE DESEMPENHO ACADÊMICO
CANCELADO: TRANSF.P/OUTRA IES
CANCELADO: CANC. POR REOPCAO
CANCELADO: PRORROGAÇÃO ADMINISTRATIVA
CANCELADO: TÉRMINO DO BENEFÍCIO DO CONVÊNIO
CANCELADO: CANCELAMENTO JUDICIAL
CANCELADO: INTEGRALIZAÇÃO DE DISCENTE
CANCELADO: FALECIMENTO DO ALUNO
CANCELADO: CADASTRO CANCELADO
CANCELADO: PROGRAMA CANCELADO
CANCELADO: DECISÃO ADMINISTRATIVA
CANCELADO: PRORROGAÇÃO POR CADASTRAMENTO DE NOVO VÍNCULO
CANCELADO: NÃO CONFIRMAÇÃO DE VÍNCULO
CONCLUÍDO: INTEGRALIZAÇÃO DE DISCENTE
CONCLUÍDO: TRANCAMENTO DE PROGRAMA
CONCLUÍDO: None
CONCLUÍDO: CONCLUÍDO
CONCLUÍDO: PRORROGAÇÃO ADMINISTRATIVA
CONCLUÍDO: PRORROGAÇÃO POR TRANCAMENTO DE PROGRAMA
CONCLUÍDO: DECURSO DE PRAZO MÁXIMO P/ CONCLUSÃO DE CURSO
CONCLUÍDO: ABANDONO (NENHUMA MATRÍCULA)
CONCLUÍDO: ANTECIPAÇÃO ADMINISTRATIVA
DESCONHECIDO: None
DESCONHECIDO: SOLICITAÇÃO ESPONTÂNEA
FORMADO: PRORROGAÇÃO POR TRANCAMENTO DE PROGRAMA
FORMADO: PRORROGAÇÃO ADMINISTRATIVA
FORMADO: INTEGRALIZAÇÃO DE DISCENTE
FORMADO: TRANCAMENTO DE PROGRAMA
FORMADO: DECURSO DE PRAZO MÁXIMO P/ CONCLUSÃO DE CURSO
NÃO CADASTRADO: None
NÃO CADASTRADO: TRANCAMENTO DE PROGRAMA
NÃO CADASTRADO: SOLICITAÇÃO ESPONTÂNEA
NÃO CADASTRADO: ABANDONO (NENHUMA MATRÍCULA)
TRANCADO: TRANCAMENTO DE PROGRAMA
TRANCADO: PRORROGAÇÃO POR TRANCAMENTO DE PROGRAMA
TRANCADO: PRORROGAÇÃO POR CADASTRAMENTO DE NOVO VÍNCULO
TRANCADO: ABANDONO (NENHUMA MATRÍCULA)
TRANCADO: None
TRANCADO: EFETIVAÇÃO DE NOVO CADASTRO

Caso não seja ativo nem cadastrado, a informação do motivo_que_saiu_do_curso é relevante. Os ativos e os cadastrados de fato não possuem o motivo_que_saiu_do_curso, portanto aparecem como None. Mas tem casos dos ativos que pode ter acontecido alguma coisa com ele),
entao pode ser bom que se alguem perguntar por ativos, mostre o resultado por motivo_que caiu do curso

Raciocine como responder bem essa pergunta observando as colunas e os tipos


PRESTE ATENÇÃO NESSE TRECHO: Estudantes formados ou evadidos não são considerados ativos após o período de evasão. No entanto, ao consultar um período histórico, um estudante deve ser considerado ativo no periodo de interesse se o período consultado estiver entre periodo_de_ingresso e periodo_de_evasao (inclusive). Se periodo_de_evasao estiver vazio ou None, o estudante é considerado ativo desde o ingresso até o período atual.
IMPORTANTE: Quando o usuário perguntar quantos estudantes um curso "tinha", "possuía", "existiam", "havia" ou "estavam" em um determinado período, interprete como quantidade de estudantes ativos naquele período, e não apenas os estudantes cujo periodo_de_ingresso seja igual ao período informado.
Quando a pergunta estiver no verbo Presente do indicativo ou similar use a situação "ATIVO".
Para um período histórico, considere ativo todo estudante cujo período consultado esteja entre periodo_de_ingresso e periodo_de_evasao (inclusive). Se periodo_de_evasao estiver vazio ou None, considere o estudante ativo até o período atual.
Ou seja, para "Quantos estudantes o curso X tinha em 2015.1?" a resposta esperada deveria ser: Conte os estudantes ativos em 2015.1 (ingresso <= 2015.1 e evasão inexistente ou >= 2015.1), e não apenas os estudantes que ingressaram em 2015.1. Por exemplo:
SELECT COUNT(*) AS total FROM estudante_info_gerais WHERE nome_do_curso = 'ciência da computação - d' AND periodo_de_ingresso <= '2015.1' AND (periodo_de_evasao = '' OR periodo_de_evasao >= '2015.1'); Você pode usar esse como base.
"""