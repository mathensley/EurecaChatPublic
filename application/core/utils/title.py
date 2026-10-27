import json
from langchain_core.language_models import BaseChatModel
from openinference.instrumentation import suppress_tracing

async def generate_chat_title(text: str, llm: BaseChatModel):
    """
    """

    with suppress_tracing():
        resposta = await llm.ainvoke(
                f"""
                "Gere um título de até 3 palavras para o texto a seguir:
                {text}
                
                *IMPORTANTE*:
                - Você sempre deve gerar um título, não faça nada além disso.
                - Sempre gere no seguinte formato: {{"titulo": "titulo_gerado"}}
                """
            )
    
    resumo = resposta.content if hasattr(resposta, "content") else str(resposta)
    resumo = resumo.replace("'", '"')
    return json.loads(resumo)
