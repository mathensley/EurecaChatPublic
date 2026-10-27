import re, json, pandas, os, duckdb
from .gerenciador_expert_alter_sql import GerenciadorExpertAlterSQL
from sql_metadata import Parser


PROMPT_SQL_GERAL = """
Dada uma pergunta de entrada, crie uma consulta DuckDB SQL sintaticamente correta para executar e ajudar a encontrar a resposta.

Use apenas a seguintes tabela ('{table_name}') com as seguinte colunas:

Colunas: {table_info}

Siga **rigorosamente** as instruções abaixo:

<RESTRIÇÕES>
- Nunca use "SELECT *" — selecione somente as colunas relevantes.
- Não invente ou modifique os nomes das colunas, e sempre ponha ';' no fim.
- Fique atento para se a pergunta requer contagem ou apenas selecionar colunas.
- Se alguma(s) parte(s) da pergunta não se relaciona com as colunas do esquema, ignore o trecho.
- NÃO COLOQUE COMENTÁRIOS.
- Existem dados que dependendo da consulta podem retornar enormes quantidades de dados. 
- Nunca use NULL;
- Tente fazer uma consulta inteligente que adquira o resultado sem que retorne dados gigantescos, como agrupar, contar agrupando, usar funções matemáticas, distinct, entre outros.
- Não precisa ser tão rigoroso na consulta afim de trazer menos dados, só tenha cuidado nesses enum, você pode conseguir extrair caracteristicas relevantes por contagem, filtro, etc.
- Nunca use atributos que não estejam na tabela.
- Apena use atributos da tabela que façam sentido para responder a pergunta, nunca use além disso.
- Se você indentificar que pode retornar MUITOS dados, limite na consulta para retornar até 100.
- Gere apenas SQL compatível com o dialeto informado.
- O dialeto de execução é DuckDB, não SQLite.
- Para mediana, prefira median(coluna).
- Para quartis, prefira quantile_cont(coluna, 0.25), quantile_cont(coluna, 0.5) e quantile_cont(coluna, 0.75).
- Para campos de período como periodo_de_ingresso e periodo_de_evasao, antes de converter para número valide com regexp_matches(coalesce(campo, ''), '^[0-9]{{4}}\\.[12]$') ou use try_cast.
- Não use expressões aritméticas dentro de LIMIT/OFFSET quando uma função agregadora do DuckDB resolver a pergunta.
- Antes de retornar a consulta, revise a sintaxe SQL mentalmente.
- Não use funções de UPPER nem LOWER
</RESTRIÇÕES>

Se quiser poder usar Common Table Expression (CTE) para auxiliar.

Responda com uma consulta SQL válida e mínima.

Pergunta: "{input}"
"""

class GerenciadorExpert(GerenciadorExpertAlterSQL):
    def __init__(self, table_name, json_data, llm):
        super().__init__()
        
        try:
            self.llm = llm
            self.table_name = table_name
            # Diretório o mapeamento dos dados (atributo, tipos e comentários) estão sendo armazenados
            BASE_DIR = os.path.dirname(os.path.abspath(__file__))
            self.path = os.path.join(BASE_DIR, "", self.table_name, "tabela.json")
            #self.db_name_schema = f"{self.table_name.lower()}.sqlite"
            #self.conn = duckdb.connect(self.db_name_schema)
            self.conn = duckdb.connect(database=":memory:")
            # Retorna três valores, contendo a 
            # - como chave a o atributo inyterno e valor o tipo e tradução do atributo interno e sua descrição 
            # - chave do atributo interno (novo) mapeando como valor a chave do atributo externo (antigo)
            # - chave do atributo externo (antigo) mapeando como valor a chave do atributo interno (novo)
            self.meaning, self.equivalentes, self.equivalentes_inverso = self.get_meaning(table_name)
            # Criando a tabela do banco de dados baseado nos atributos anteriores
            #self.tabela = self.create_table()
            self.prompt = PROMPT_SQL_GERAL

            if isinstance(json_data, (list, dict)):
                self.json_data = json_data
            else:
                self.json_data = json.loads(json_data)

            if isinstance(self.json_data, dict):
                self.json_data = [self.json_data]
            elif isinstance(self.json_data, list):
                self.json_data = self.json_data
            if not self.json_data:
                raise ValueError("Lista de dados JSON está vazia.")

            # Pegando uma amostra dos dados
            self.template = self.json_data[0]

            # Baseado na amostra, essa função avalia quais são os campos contidos na amostra que dar merge 
            # com a tabela alocada localmente com suas devidas traduções nos atributos.
            self.attribes_json = self.get_attributes_json(self.template, self.meaning)

            # Populando a tabela
            self.populate()
            self.sql_estatico = None

        except Exception as e:
            raise(e)
    
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def close(self):
        try:
            if self.conn:
                self.conn.close()
        except Exception:
            pass

    def get_meaning(self, collection) -> dict:
        with open(self.path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        
        if collection not in data:
            raise ValueError(f"A tabela '{collection}' não foi encontrada no arquivo JSON.")
        
        meaning, equivalentes, eq_inverso = {}, {}, {}
        attrs_used_in_query = []
        for key, column_type in data[collection].items():
            mapper_key = column_type["mapper"]
            meaning[mapper_key] = f"{column_type['type']} -- {column_type['description']}"
            equivalentes[column_type["mapper"]] = key
            eq_inverso[key] = column_type["mapper"]
            attrs_used_in_query.append(mapper_key)
        
        self.columns_used_in_query = attrs_used_in_query
        return meaning, equivalentes, eq_inverso


    def get_attributes_json(self, template, meaning):
        if not isinstance(template, dict): raise ValueError("Itens da lista precisam ser dicts.")
        
        attributes = {}
        for key, value in meaning.items():
            if key == "_id": continue
            tipo = type(value).__name__
            significado = meaning.get(key, key)
            attributes[key] = f"{tipo} -- significado: {significado}"
        
        return attributes


    def regex_remove_cols(self, sql: str, col: str) -> str:
        # 1) remove "ano in (...)" if present
        pattern_in = re.compile(rf"\s*(?:where|and|or)\s+{col}\s+in\s*\([^)]*\)", flags=re.IGNORECASE)
        query = pattern_in.sub("", sql)

        # 2) remove parenthesized "ano = X or ano = Y or ..." groups
        pattern_paren_or = re.compile(
            rf"\s*(?:where|and|or)\s*\(\s*(?:{col}\s*=\s*(?:'[^']*'|\d+)\s*(?:\s*or\s*{col}\s*=\s*(?:'[^']*'|\d+)\s*)+)\s*\)",
            flags=re.IGNORECASE,
        )
        query = pattern_paren_or.sub("", query)

        # 3) remove simple equality "ano = 2024" (with or without quotes)
        pattern_simple = re.compile(rf"\s*(?:where|and|or)\s+{col}\s*=\s*(?:'[^']*'|\d+)", flags=re.IGNORECASE)
        query = pattern_simple.sub("", query)

        # 4) cleanup common leftovers:
        query = re.sub(r"(?i)\bwhere\b\s+(?:and|or)\b", "where ", query)
        query = re.sub(r"(?i)\b(?:and|or)\b\s*(?:and|or)\b", lambda m: m.group(0).split()[0] + " ", query)
        query = re.sub(r"(?i)\b(?:and|or)\b\s*(?=;|\s*$)", "", query)
        query = re.sub(r"(?i)\bwhere\b\s*(?=;|\s*$)", "", query)
        query = re.sub(r"[ \t]+", " ", query)
        query = re.sub(r"\s*;\s*$", ";", query.strip())

        query_sem_ano = query.strip()
        return query_sem_ano

    
    def _normalizar_sql_llm(self, response_llm: str, columns) -> str:
        response_llm = re.sub(r"```.*?```", lambda m: m.group(0).strip("`").split("\n", 1)[-1], response_llm, flags=re.DOTALL).strip()
        response_llm = self.alter_query_sql(response_llm, columns, template=self.template)
        response_llm = re.sub(r"\b(tabela|table)\b", self.table_name, response_llm, flags=re.IGNORECASE).lower()
        return response_llm


    def _resultado_tem_erro_sql(self, resultado):
        return isinstance(resultado, list) and bool(resultado) and isinstance(resultado[0], dict) and "error" in resultado[0]


    def _corrigir_sql_com_erro(self, sql, erro, input, columns, observacao):
        table_info = json.dumps(self.attribes_json, indent=2, ensure_ascii=False)
        prompt_correcao = f"""
A consulta DuckDB abaixo foi gerada para responder à pergunta, mas falhou ao executar.

Pergunta: "{input}"

Tabela: {self.table_name}
Colunas: {table_info}

Consulta com erro:
{sql}

Erro retornado pelo banco:
{erro}

Corrija a consulta para DuckDB SQL. Responda apenas com uma consulta SELECT/WITH válida, sem comentários.
"""
        if observacao:
            prompt_correcao += f"\nObservação adicional: {observacao}\n"

        response_llm = self.llm.invoke(prompt_correcao)
        response_llm = response_llm.content.strip()
        return self._normalizar_sql_llm(response_llm, columns)


    def invoke_sql(self, input, columns, show=False, sql_estatico=None, observacao="", max_retries=1):


        if sql_estatico == None:
            if observacao:
                self.prompt += f"\n\nObservação: {observacao}\n"

            formatted_prompt = self.prompt.format(
                input=input, dialect="SQL", table_name=self.table_name,
                table_info=json.dumps(self.attribes_json, indent=2, ensure_ascii=False),
            )

            if show: print(formatted_prompt)
            response_llm = self.llm.invoke(formatted_prompt)
            response_llm = response_llm.content.strip()
            response_llm = self._normalizar_sql_llm(response_llm, columns)
        else:
            self.populate()
            response_llm = sql_estatico

        try:
            for tentativa in range(max_retries + 1):
                todas_colunas = Parser(response_llm).columns
                colunas_consulta_remover = [coluna for coluna in todas_colunas if coluna not in self.columns_used_in_query]
                if '*' in colunas_consulta_remover:
                    colunas_consulta_remover.remove('*')
                
                for col in colunas_consulta_remover:
                    response_llm = self.regex_remove_cols(response_llm, col)

                resultado = self.execute_sql(response_llm)
                if not self._resultado_tem_erro_sql(resultado) or sql_estatico is not None or tentativa >= max_retries:
                    break

                erro = resultado[0]["error"]
                response_llm = self._corrigir_sql_com_erro(response_llm, erro, input, columns, observacao)
        except Exception as e:
            resultado = f"Erro ao executar a expressão: {e}"

        if self.sql_estatico == None:
            self.sql_estatico = response_llm

        result = {
            "consulta": response_llm,
            "resultado":
                resultado.to_dict(orient="records") if isinstance(resultado, pandas.DataFrame) 
                else resultado.to_frame().to_dict(orient="records") if isinstance(resultado, pandas.Series) else resultado
            
        }

        return result
    

    def dicts_to_markdown_table(self, data):
        # Só converte se for uma lista de dicionários
        if not (
            isinstance(data, list)
            and data
            and all(isinstance(item, dict) for item in data)
        ):
            return data

        headers = list(data[0].keys())

        lines = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
        ]

        for row in data:
            values = [str(row.get(col, "")) for col in headers]
            lines.append("| " + " | ".join(values) + " |")

        return "\n".join(lines)


    def execute_sql(self, sql: str):
        try:
            return self.conn.execute(sql).fetchdf()
        except Exception as e: return [{"error": str(e)}]


    def create_table(self):
        with open(self.path, 'r', encoding='utf-8') as file:
            data = json.load(file)

        if self.table_name not in data:
            raise ValueError(f"A tabela '{self.table_name}' não foi encontrada no arquivo JSON.")
        
        colunas_sql, colunas_doc = [], []
        for column, column_type in data[self.table_name].items():
            colunas_sql.append(f"{self.equivalentes_inverso[column]} {column_type['type']}")
            colunas_doc.append(f"{column} {column_type['type']}, -- {column_type['description']}")

        ddl = f"CREATE TABLE IF NOT EXISTS {self.table_name} (_id INTEGER PRIMARY KEY, {', '.join(colunas_sql)});"
        resp = f"{self.table_name}(\n" + "\n".join(colunas_doc) + "\n);"
        self.conn.execute(ddl)
        return resp
    

    def populate(self):
        data = self.json_data  

        if isinstance(data, dict):
            data = [data]

        df = pandas.DataFrame(data)
        df = df.rename(columns=self.equivalentes_inverso)
        normalize_value = lambda x: x.lower() if isinstance(x, str) else x
        if hasattr(df, "map"):
            df = df.map(normalize_value)
        else:
            df = df.applymap(normalize_value)
        self.conn.register('tmp_json', df)
        
        cols = ", ".join([f"{c}" for c in df.columns])
        self.conn.execute(f"CREATE OR REPLACE VIEW {self.table_name} AS SELECT {cols} FROM tmp_json;")
    

    def execute_sql_estatico(self, sql, dados, populate: bool = True, drop: bool = True):
        self.json_data = dados
        if populate:
            self.populate()
        result = self.execute_sql(sql)
        if drop:
            self.conn.execute(f"DROP VIEW IF EXISTS {self.table_name}")
        return result
