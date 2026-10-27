import os

from dotenv import load_dotenv

from application.core.chat_model import create_chat_model

load_dotenv(override=True)


# VARIÁVEIS PARA CRIAR O DB NO DOCKER
POSTGRES_USER       = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD   = os.getenv("POSTGRES_PASSWORD")
POSTGRES_DB         = os.getenv("POSTGRES_DB")
POSTGRES_PORT       = os.getenv("POSTGRES_PORT")
POSTGRES_HOST       = os.getenv("POSTGRES_HOST", "localhost")

# URI DO DB (Postgres)
DB_URI = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}?sslmode=disable"

# NOME DOS MODELOS
AGENT_MODEL         = os.getenv("AGENT_MODEL")
CHECK_MSG_MODEL     = os.getenv("CHECK_MSG_MODEL")
SUMMARIZER_MODEL    = os.getenv("SUMMARIZER_MODEL")
TOOL_SELECTOR_MODEL = os.getenv("TOOL_SELECTOR_MODEL")
CHAT_TITLE_MODEL    = os.getenv("CHAT_TITLE_MODEL")
SQL_MODEL           = os.getenv("SQL_MODEL")

# URL DA API DO EURECA
URL_BASE            = "https://eureca.sti.ufcg.edu.br/das/v2"       # SCAO
URL_SIG             = "https://eureca.sti.ufcg.edu.br/das-sig/v1/"  # SIGAA

# Eureca Agent
agent_model = create_chat_model(AGENT_MODEL, streaming=True)

# Check User Message
check_msg_model = create_chat_model(CHECK_MSG_MODEL)

# Sumarizador (Config)
summary_config = {
    "model": create_chat_model(SUMMARIZER_MODEL),
    "limit": 8, # limite de quantos pares de mensagens (HumanMessage - AIMessage) serão considerados para sumarização
    "last_n_pairs": 1 # últimos pares de mensagens (HumanMessage - AIMessage) que não serão considerados para sumarizar
}

# Tool Selector (Config)
tool_selector_config = None
# tool_selector_config = {
#     'model': create_chat_model(TOOL_SELECTOR_MODEL),
#     'max_tools': 5,
#     'max_message_chars': 2_000,
#     'strategy': 'LLM',
#     'llm_mode': 'PROMPT',
#     #'always_include': [], # não entram na contagem de max_tools
# }

# Modelo para gerador de título do chat do frontend
title_model = create_chat_model(CHAT_TITLE_MODEL)

# Modelo para SQL
#chat_sql = ChatOpenAI(model=SQL_MODEL, base_url="https://api.deepinfra.com/v1/openai", api_key=api_key)
chat_sql = create_chat_model(SQL_MODEL)

# Modelo para análise de anomalias
analysis_model = create_chat_model(AGENT_MODEL)
