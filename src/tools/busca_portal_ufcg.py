import os
from tavily import TavilyClient

os.environ.get("TAVILY_API_KEY")
client = TavilyClient()

def busca_portal_ufcg(query: str):
    """
    Busca informações no portal da UFCG.
    Fornece informações sobre notícias, comunicados, editais, contatos, páginas institucionais, processos seletivos, informações públicas recentes ou links do portal oficial da UFCG.
    Também é possível obter informações de vagas e do processo seletivo do sisu (ingressantes pelo sisu).
    NÃO fornece informações de cursos, disciplinas, ou informações pessoais de estudantes.
    NÃO use para responder perguntas sobre o que o assistente consegue fazer, suas capacidades, exemplos de ajuda, escopo de atendimento ou funcionamento interno.

    Args:
        - query: str. Pergunta sobre alguma informação da UFCG, como notícias, contatos, etc.
    
    Returns:
        dict: Informações como notícias, contatos, e informações simples da UFCG, além de links úteis.
    """

    print(f"🔍 Chamando busca_portal_ufcg ({query})")

    result = client.search(
        query=query,
        include_domains=["portal.ufcg.edu.br"],
        search_depth="advanced",
        max_results=5,
        include_answer=True
    )

    referencias = [
        {
            "url": r["url"]
        }
        for r in result.get("results", [])
    ]

    return {
        "resposta": result.get("answer"),
        "links_uteis": referencias
    }

#print(busca_portal_ufcg(query="como fazer matrícula"))
