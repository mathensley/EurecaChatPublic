from pathlib import Path
import asyncio
import sqlglot
from sqlglot import exp
import sqlite3, os, json
from application.config import chat_sql
from .prompt_geral import PROMPT_SQL_EXPERT
from .prompt_geral import DESCRICAO_SITUACAO
from sqlglot.errors import SqlglotError
from sqlglot.optimizer.qualify import qualify
from src.helpers.chat.chat_msgs_utils import extract_text_content
from .montar_hierarquia_ufcg import TABELAS, _ORDEM_NIVEIS, buscar_dados_explicativos, _montar_hierarquia
from .atributos_nao_permitidos_por_usuario import LISTA_DE_ATRIBUTOS_NAO_PERMITIDOS_POR_USUARIO, ColunasNaoPermitidasError, SqlInvalidoError


dados_explicativos = buscar_dados_explicativos()


class GerenciadorExpertV2():
    def __init__(self, llm=None):
        super().__init__()

        try:
            self.llm = llm
            SQLITE_DIR = Path(os.getenv("SQLITE_DIR", ".")).expanduser()
            TABELA = "ufcg"
            DB_PATH = (SQLITE_DIR / f"{TABELA}.sqlite").resolve()
            if not DB_PATH.is_file(): raise FileNotFoundError(f"Banco consolidado não encontrado: {DB_PATH}")
            self.caminho_sqlite = DB_PATH

            visao_tabelas: dict[str, dict[str, dict[str, str]]] = {}
            with sqlite3.connect(f"{self.caminho_sqlite.as_uri()}?mode=ro", uri=True) as conn:
                for tabela in TABELAS:
                    visao_tabelas[tabela] = {}
                    for _, nome, tipo, *_ in conn.execute(f'PRAGMA table_info("{tabela}")').fetchall():
                        descricao = dados_explicativos.get(tabela, {}).get(nome, "")
                        visao_tabelas[tabela][nome] = { "tipo": tipo, "descricao": descricao, }

            self.visao_tabelas = visao_tabelas
            self.schema = {
                tabela: {coluna: info["tipo"] or "TEXT" for coluna, info in colunas.items()}
                for tabela, colunas in visao_tabelas.items()
            }
        
        except Exception as e: raise(e)


    @staticmethod
    def _formatar_visao_tabelas(visao_tabelas: dict[str, dict[str, dict[str, str]]]) -> str:
        linhas = []
        for tabela, colunas in visao_tabelas.items():
            linhas.append(f"• Tabela: {tabela}")
            linhas.append("• Colunas:")
            for nome, metadados in colunas.items():
                tipo = metadados["tipo"]
                descricao = metadados["descricao"]
                linhas.append(f"\t- {nome} ({tipo}){': ' + descricao if descricao else ''}")

            linhas.append("-" * 100)
            linhas.append("")

        return "\n".join(linhas)


    def construir_contexto_dados(self, entidades: dict) -> str:
        linhas = []
        niveis_presentes = [nivel for nivel in _ORDEM_NIVEIS if entidades.get(nivel)]

        if niveis_presentes:
            linhas.append("CAMPUS / CENTROS / UNIDADES / CURSOS (use exatamente estes códigos):")
            linhas.extend(_montar_hierarquia(entidades, niveis_presentes))

        if entidades.get("disciplina"):
            linhas.append("\nDISCIPLINAS (use exatamente estes códigos, se aplicável):")
            for d in entidades["disciplina"]:
                linhas.append(f'- codigo_da_disciplina={d["codigo_da_disciplina"]} | nome_da_disciplina="{d["nome_da_disciplina"]}"')
            linhas.append(f"... \n\nHá outras disciplinas além dessas acima (estou mostrando apenas algumas amostras de algumas disciplinas).")

        if entidades.get("professor"):
            linhas.append("\nPROFESSORES (use exatamente estes códigos, se aplicável):")
            for p in entidades["professor"]:
                linhas.append(f'- matricula_do_professor={p["matricula_do_professor"]} | nome_do_professor="{p["nome_do_professor"]}')
            linhas.append(f"...\n\nHá outros professores além desses acima (estou mostrando apenas algumas amostras de alguns professores).")

        if entidades.get("periodo"):
            linhas.append("\nPERIODO (use se aplicável):")
            periodos = entidades.get("periodo", [])
            if periodos:
                periodo_de = periodos[0].get("periodo_de")
                periodo_ate = periodos[0].get("periodo_ate")
                if periodo_de != periodo_ate and periodo_de is not None and periodo_ate is not None:
                    linhas.append(f"Usar entre o periodo de '{periodo_de}' a '{periodo_ate}'.")
                elif periodo_de == periodo_ate and periodo_de is not None and periodo_ate is not None:
                    linhas.append(f"Usar periodo: {periodo_ate}")
                else:
                    if periodo_ate is None:
                        linhas.append(f"Usar periodo a partir de: {periodo_de}")
                    else:
                        linhas.append(f"Periodo até: {periodo_ate}")

        return "- " + "\n".join(linhas) + "\n"


    def agrupar_entidades(self, dados_adicionais: list) -> dict:

        entidades = {
            "campus": [], "centro": [], "unidade": [], "curso": [],
            "disciplina": [], "professor": [], "periodo": []
        }

        for item in dados_adicionais:
            if "matricula_do_professor" in item:
                entidades["professor"].append(item)
            elif "codigo_da_disciplina" in item:
                entidades["disciplina"].append(item)
            elif "codigo_do_curso" in item:
                entidades["curso"].append(item)
            elif "codigo_da_unidade" in item:
                entidades["unidade"].append(item)
            elif "codigo_do_centro" in item:
                entidades["centro"].append(item)
            elif "codigo_do_campus" in item:
                entidades["campus"].append(item)
            elif "periodo_de" in item or "periodo_ate" in item:
                entidades["periodo"].append(item)
            else: raise ValueError(f"Não foi possível classificar a entidade: {item}")
        
        return entidades


    def _extrair_sql(self, sql_gerado) -> str:
        sql = extract_text_content(sql_gerado).strip()
        if not sql: raise ValueError("O modelo não retornou uma consulta SQL.")
        return sql


    def _preparar_invocacao(self, entidades: dict, query: str, tipo_user: str = "anon",) -> tuple[list[dict], str]:
        entidades = self.agrupar_entidades(entidades)
        contexto_dados = self.construir_contexto_dados(entidades)

        tipo_user = tipo_user if tipo_user else "anon"
        nao_permitidos = LISTA_DE_ATRIBUTOS_NAO_PERMITIDOS_POR_USUARIO.get(tipo_user)

        # Cada chamada recebe sua própria visão para que o filtro de permissão
        # não altere o esquema compartilhado pelas invocações seguintes.
        visao_tabelas = {
            tabela: {
                coluna: metadados.copy()
                for coluna, metadados in colunas.items()
                if coluna not in nao_permitidos.get(tabela, ())
            }
            for tabela, colunas in self.visao_tabelas.items()
        }
        
        visao_tabelas_formatada = self._formatar_visao_tabelas(visao_tabelas)
        prompt = PROMPT_SQL_EXPERT.format(
            visao_tabelas=visao_tabelas_formatada,
            descricao_situacao=DESCRICAO_SITUACAO,
            contexto_dados=contexto_dados,
            query=query,
        )

        print(prompt)
        return [{"role": "user", "content": prompt}], contexto_dados


    def _executar_sql(self, sql: str):
        with sqlite3.connect(f"{self.caminho_sqlite.as_uri()}?mode=ro", uri=True) as conn:
            cursor = conn.execute(sql)
            if cursor.description is None:
                return "Comando executado com sucesso."

            colunas = [coluna[0] for coluna in cursor.description]
            linhas = [dict(zip(colunas, linha)) for linha in cursor.fetchall()]
            return json.dumps(linhas, ensure_ascii=False, default=str, indent=2)


    def _montar_resultado(self, sql: str, resultado_formatado, response, contexto_dados: str) -> dict:
        return {
            "sql_criado": sql.strip(),
            "resultado": resultado_formatado,
            "metadados_llm": response,
            "dados_de_referencia": f"""
                <DADOS_DE_REFERENCIA>
                {contexto_dados}
                </DADOS_DE_REFERENCIA>
            """,
        }


    @staticmethod
    def _adicionar_correcao_sql(mensagens: list[dict], response, ultimo_erro: str) -> None:
        mensagens.append({"role": "assistant", "content": response.content})
        mensagens.append({"role": "user", "content": (
            f"O SQL gerado falhou ao executar com o seguinte erro:\n{ultimo_erro}\n"
            "Corrija o SQL respeitando as REGRAS_DE_USO acima. "
            "Gere apenas o SQL corrigido."
        )})
    

    @staticmethod
    def checar_colunas_sql_nao_autorizadas(sql: str, nao_permitidos: dict[str, list[str]], schema: dict) -> tuple[bool, list[str]]:
        proibidas = {(t.lower(), c.lower()) for t, cols in nao_permitidos.items() for c in cols}

        try:
            statements = [s for s in sqlglot.parse(sql, dialect="sqlite") if s is not None]
        except SqlglotError as e: raise SqlInvalidoError(f"SQL inválido: {e}") from e

        if len(statements) != 1: raise SqlInvalidoError("é permitido exatamente um comando")

        stmt = statements[0]
        tipos_consulta = (exp.Query,) if hasattr(exp, "Query") else (exp.Select, exp.Union)
        if not isinstance(stmt, tipos_consulta): raise SqlInvalidoError("apenas consultas (SELECT) são permitidas")

        try:
            tree = qualify(stmt, schema=schema, dialect="sqlite")
        except SqlglotError as e:
            raise SqlInvalidoError(f"não foi possível resolver as colunas: {e}") from e

        alias_para_tabelas: dict[str, set[str]] = {}
        for tabela in tree.find_all(exp.Table):
            alias_para_tabelas.setdefault(tabela.alias_or_name.lower(), set()).add(tabela.name.lower())

        usadas = set()
        for col in tree.find_all(exp.Column):
            ref = col.table.lower()
            for real in alias_para_tabelas.get(ref, {ref}):
                usadas.add((real, col.name.lower()))

        bloqueadas = sorted(f"{t}.{c}" for t, c in usadas & proibidas)
        return not bloqueadas, bloqueadas


    async def ainvoke(self, entidades: dict, query: str, max_retries, tipo_user: str = "anon"):
        mensagens, contexto_dados = self._preparar_invocacao(entidades, query, tipo_user)        
        colunas_nao_permitidas = LISTA_DE_ATRIBUTOS_NAO_PERMITIDOS_POR_USUARIO[tipo_user]

        ultimo_erro = None
        for tentativa in range(max_retries + 1):
            response = await self.llm.ainvoke(mensagens)
            sql = self._extrair_sql(response.content)

            try:
                autorizado, colunas_nao_permitidas_encontradas = self.checar_colunas_sql_nao_autorizadas(sql, colunas_nao_permitidas, self.schema)
            except SqlInvalidoError as e:
                ultimo_erro = str(e)
                if tentativa == max_retries: break
                self._adicionar_correcao_sql(mensagens, response, ultimo_erro)
                continue
            
            if not autorizado: raise ColunasNaoPermitidasError(colunas_nao_permitidas_encontradas)
            
            try:
                resultado_formatado = await asyncio.to_thread(self._executar_sql, sql)
                return self._montar_resultado(sql, resultado_formatado, response, contexto_dados)
            except sqlite3.Error as e:
                ultimo_erro = str(e)
                if tentativa == max_retries: break
                self._adicionar_correcao_sql(mensagens, response, ultimo_erro)

        raise RuntimeError(f"Não foi possível gerar um SQL válido após {max_retries} tentativas. Último erro: {ultimo_erro}")


if __name__ == "__main__":
    gerenciador = GerenciadorExpertV2(llm=chat_sql)
    entidades = [
        {"nome_do_campus": "Campina Grande", "codigo_do_campus": 1},
        {"nome_do_centro": "CENTRO DE ENGENHARIA ELETRICA E INFORMATICA - CEEI", "codigo_do_centro": 1102, "pertence_ao_campus_de_codigo": 1},
        {"nome_da_unidade": "UNIDADE ACADEMICA DE SISTEMAS E COMPUTACAO - UASC", "codigo_da_unidade": 110202, "pertence_ao_centro_de_codigo": 1102},
        {"nome_do_curso": "CIÊNCIA DA COMPUTAÇÃO - DIURNO - BACHARELADO", "codigo_do_curso": 108095, "pertence_a_unidade_de_codigo": 110202},
    ]
    
    response = gerenciador.invoke(
        entidades=entidades,
        query="Quem são os estudantes que estão cursando com a professora Patrícia do curso de ciência da computação?",
        max_retries=3
    )

    print(f"""
    {response.content}

    • Contagem de Tokens:
    - Metadados: {response.usage_metadata},
    - input: {response.usage_metadata["input_tokens"]} tokens;
    - output: {response.usage_metadata["output_tokens"]} tokens;
    - reasoning: {response.usage_metadata["output_token_details"]["reasoning"]} tokens.
    """)
