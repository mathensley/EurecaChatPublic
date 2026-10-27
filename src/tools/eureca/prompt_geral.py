DESCRICAO_SITUACAO = """
Para consultas que envolvam situação do estudante, exsitem uma relação chave e valor entre os atributos situação (key) e motivo de evasão (value).
Para a situação que tiver lista vazia não precisa usar a coluna motivo de evasão.

"ATIVO": [],
"ATIVO - FORMANDO": [],
"CONCLUÍDO": [],
"CANCELADO": [
    NULL,
    "ABANDONO (NENHUMA MATRÍCULA)",
    "ABANDONO (NENHUMA INTEGRALIZAÇÃO)",
    "EFETIVAÇÃO DE NOVO CADASTRO",
    "SOLICITAÇÃO ESPONTÂNEA",
    "INSUFICIÊNCIA DE DESEMPENHO ACADÊMICO",
    "CANC. POR REOPÇÃO",
    "DECURSO DE PRAZO MÁXIMO P/ CONCLUSÃO DE CURSO",
    "TRANSF.P/OUTRA IES",
    "CANCELAMENTO JUDICIAL",
    "TÉRMINO DO BENEFÍCIO DO CONVÊNIO",
    "FALECIMENTO DO ALUNO",
    "DECISÃO ADMINISTRATIVA",
    "CADASTRO CANCELADO",
    "PROGRAMA CANCELADO",
    "NÃO CONFIRMAÇÃO DE VÍNCULO",
    "INTEGRALIZAÇÃO DE DISCENTE"
],
"""


PROMPT_SQL_EXPERT = """
<ESQUEMA_SQL>
{visao_tabelas}
</ESQUEMA_SQL>

{descricao_situacao}

<DADOS_DE_REFERENCIA>
{contexto_dados}
</DADOS_DE_REFERENCIA>

<REGRAS_DE_USO>
- 1. Use os códigos EXATAMENTE como aparecem em <DADOS_DE_REFERENCIA>. Nunca invente ou deduza um código que não esteja listado ali.
- 2. Se a entidade mencionada na pergunta não aparecer em <DADOS_DE_REFERENCIA>, NÃO monte filtro por código. Use LIKE na coluna de nome, ou selecione a coluna sem filtrar, conforme orientado em <ESQUEMA_SQL>.
- 3. Nunca combine o código de uma entidade (ex: codigo_do_centro) com o nome de outra (ex: nome_da_unidade).
- 4. Se houver mais de um candidato plausível em <DADOS_DE_REFERENCIA>, prefira o que casa exatamente (case-insensitive) com o termo da pergunta. Se nenhum casar exatamente, explique a ambiguidade em vez de escolher arbitrariamente.
- 5. Sempre gere apenas o SQL puro, sem explicações adicionais, salvo quando a regra 4 se aplicar.
- 6. Quando o código de uma entidade for conhecido e usado como filtro, NÃO adicione também um filtro de igualdade exata pelo nome dessa mesma entidade — o nome pode divergir em acentuação/caixa em relação ao dado de referência. Inclua o nome apenas no SELECT para exibição. Só use o nome como filtro (com LIKE e COLLATE NOCASE, nunca igualdade exata) quando o código for desconhecido.
- 7. Nunca use "SELECT *" — selecione somente as colunas relevantes.
- 8. Não invente ou modifique os nomes das colunas, e sempre ponha ';' no fim.
- 9. Fique atento para se a pergunta requer contagem ou apenas selecionar colunas.
- 10. Se alguma(s) parte(s) da pergunta não se relaciona com as colunas do esquema, ignore o trecho.
- 11. Não coloque comentários.
- 12. Existem dados que dependendo da consulta podem retornar enormes quantidades de dados. 
- 14. Tente fazer uma consulta inteligente que adquira o resultado sem que retorne dados gigantescos, como agrupar, contar agrupando, usar funções matemáticas, distinct, entre outros.
- 15. Não precisa ser tão rigoroso na consulta afim de trazer menos dados, só tenha cuidado nesses enum, você pode conseguir extrair caracteristicas relevantes por contagem, filtro, etc.
- 16. Nunca use atributos que não estejam na tabela.
- 17. Apena use atributos da tabela que façam sentido para responder a pergunta, nunca use além disso.
- 18. Use sintaxe SQLite: não use ILIKE; para buscas sem diferenciar
maiúsculas/minúsculas, use LIKE com COLLATE NOCASE.
- 19. Quando a pergunta pedir dados da "UFCG" como instituição, ou disser
"todos os cursos e campi", considere todo o banco: não crie filtro de campus
com o texto "UFCG". Só filtre campus quando o usuário informar um campus
específico ou quando houver um código de campus em <DADOS_DE_REFERENCIA>.
</REGRAS_DE_USO>

Pergunta do usuário: {query}


Raciocine fortemente como responder essa pergunta analisando as tabelas mostradas, dados de referência e regras de uso, sem perder detalhes.
"""


DOC_STRING_TOOL = """
Busca dados acadêmicos da UFCG (campus, centro, unidade, curso, disciplina,
professor) para responder a `query`, aceitando nome OU código em cada campo.

Cada parâmetro `nomes_dos_*` / `nomes_das_*` aceita um ou mais termos
separados por vírgula, podendo misturar nome e código livremente no mesmo
campo (ex.: "999999, nome do curso").

Args:
    query (str): Pergunta em linguagem natural ou em sql que motiva a busca.
    nomes_dos_campus (Any): Nome(s) e/ou código(s) de campus, separados
        por vírgula. Ex.: "Campina Grande" ou "1, Sousa".
    nomes_dos_centros (Any): Nome(s) e/ou código(s) de centro, separados
        por vírgula.
    nomes_das_unidades (Any): Nome(s) e/ou código(s) de unidade
        acadêmica, separados por vírgula.
    nomes_dos_cursos (Any): Nome(s) e/ou código(s) de curso, separados
        por vírgula. Ex.: "108095, engenharia elétrica".
    nomes_das_disciplinas (Any): Nome(s) e/ou código(s) de disciplina,
        separados por vírgula.
    nomes_dos_professores (str): Nome(s) e/ou matrícula(s) de professor,
        separados por vírgula. Ex.: "andrey, patricia".
    periodo_de_busca_de (Any): Período inicial (formato "AAAA.S") para
        filtrar disciplinas/professores. Se omitido, assume um padrão
        baseado no período corrente.
    periodo_de_busca_ate (Any): Período final (formato "AAAA.S") para
        filtrar disciplinas/professores. Se omitido, assume um padrão
        baseado no período corrente.
    gerar_csv (bool): Quando True, inclui também um CSV para download,
        mesmo que a consulta tenha até 100 linhas.

Tabelas e colunas disponíveis no banco consolidado:

{formato_tabela}

{descricao_situacao}

Returns:
    Até 100 linhas, retorna todos os dados. Acima desse limite, retorna
    uma prévia e um CSV para download. Quando `gerar_csv=True` e houver
    até 100 linhas, retorna todos os dados e o CSV em `arquivo_csv`.
"""
