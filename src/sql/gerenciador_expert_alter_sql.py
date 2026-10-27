import re
import sqlparse

class GerenciadorExpertAlterSQL:
    def __init__(self):
        pass

    def extrair_queries(self, texto):
        parsed = sqlparse.parse(texto)
        results = []
        for stmt in parsed:
            sql = str(stmt).strip()
            if sql.upper().startswith("SELECT"):
                results.append(sql)
        return results
    
    
    def alter_query_sql(self, query, columns, template):
        match = self.extrair_queries(query)
        if match:
            query = match[0]

        query = query.replace("\n", ' ').strip()
        for column in columns:
            if column not in template:
                continue
                
            value = template[column]
            
            if isinstance(value, str):
                escaped_value = value.replace('\'', '\'\'')
                value_str = f"'{escaped_value}'"
            else:
                value_str = str(value)

            
            exact_match_pattern = rf"(\b{re.escape(column)}\b\s*=\s*)('[^']*'|\"[^\"]*\"|[^=,\s\(\)]+)"
            query = re.sub(
                exact_match_pattern,
                rf"\g<1>{value_str}",
                query,
                flags=re.IGNORECASE
            )
            

            contains_pattern = rf"(\b{re.escape(column)}\b\s+LIKE\s+)'%[^%]*%'"
            if isinstance(value, str):
                escaped_value = value.replace('\'', '\'\'')
                sql_like_value = f"'%{escaped_value}%'"
                query = re.sub(
                    contains_pattern,
                    rf"\1{sql_like_value}",
                    query,
                    flags=re.IGNORECASE
                )
            
            
            in_pattern = rf"(\b{re.escape(column)}\b\s+IN\s*)\([^)]+\)"
            if isinstance(value, (list, tuple)):
                formatted_values = []
                for v in value:
                    if isinstance(v, str):
                        escaped_v = v.replace('\'', '\'\'')
                        formatted_values.append(f"'{escaped_v}'")
                    else:
                        formatted_values.append(str(v))
                in_values = f"({', '.join(formatted_values)})"
            else:
                in_values = f"({value_str})"

            query = re.sub(in_pattern, rf"\1{in_values}", query, flags=re.IGNORECASE)
        
        query = re.sub(r'\s{2,}', ' ', query)
        if not query.strip().lower().startswith("with"):
            matches = re.compile(
                r"SELECT[\s\S]*?;",
                re.IGNORECASE
            ).findall(query)

            if matches:
                query = matches[0]
            
        return query.replace("\n", " ").strip()
