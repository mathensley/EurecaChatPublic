PROMPT_SQL_GERAL = """
Dada uma pergunta de entrada, crie uma consulta SQLite sintaticamente correta para executar e ajudar a encontrar a resposta.

Use apenas a seguintes tabela ('{table_name}') com as seguinte colunas:

Colunas: {table_info}

Siga **rigorosamente** as instruções abaixo:

<RESTRIÇÕES>
- Nunca use "SELECT *" — selecione somente as colunas relevantes.
- Não invente ou modifique os nomes das colunas, e sempre ponha ';' no fim.
- Fique atento para se a pergunta requer contagem ou apenas selecionar colunas.
- Se alguma(s) parte(s) da pergunta não se relaciona com as colunas do esquema, ignore o trecho.
- Não coloque comentários.
- Existem dados que dependendo da consulta podem retornar enormes quantidades de dados. 
- Nunca use NULL;
- Tente fazer uma consulta inteligente que adquira o resultado sem que retorne dados gigantescos, como agrupar, contar agrupando, usar funções matemáticas, distinct, entre outros.
- Não precisa ser tão rigoroso na consulta afim de trazer menos dados, só tenha cuidado nesses enum, você pode conseguir extrair caracteristicas relevantes por contagem, filtro, etc.
- Nunca use atributos que não estejam na tabela.
- Apena use atributos da tabela que façam sentido para responder a pergunta, nunca use além disso.
- Se você indentificar que pode retornar MUITOS dados, limite na consulta para retornar até 100.
</RESTRIÇÕES>

Responda com uma consulta SQL válida e mínima.

Pergunta: "{input}"
"""


PROMPT_SQL_INCONSISTENCIAS = """
Dado o seguinte comando SQL:

{sql}

Gere consultas SQL adicionais para identificar possíveis inconsistências nos dados relacionados a essa consulta.

Exemplos de problemas:
- Valores NULL em colunas relevantes
- Valores fora do intervalo esperado
- Registros inconsistentes ou incompletos
- Uso de agregações (ex: COUNT(*)) que podem esconder problemas

Regras:
- As consultas devem ser baseadas nas mesmas colunas da query original
- Retorne apenas SQLs válidos e mínimos
"""