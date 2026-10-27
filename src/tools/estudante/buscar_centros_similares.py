from ...helpers.request_utils import make_request
from ...helpers.tool_handlers.campi_for_tools import campi
from ...helpers.tool_handlers.fuzzy_matching import extract_most_similar


async def buscar_centros_similares(campus: str = "", centro: str = ""):
    params = { "tipo-setor": "CENTRO" }

    if campus != "":
        codigo_campus = (campus if (campus.isdigit() or campus == "") else extract_most_similar(campus, campi, "campus")[0][0]["codigo"])        
        params["campus"] = codigo_campus
    
    centros = await make_request("https://eureca.sti.ufcg.edu.br/das-sig/v1/setores", params=params)
    if centros:
        centros = [c for c in centros if "centro de" in c["descricao"].lower()]
        centro_similar = extract_most_similar(centro, centros, "descricao")
        return centro_similar
    
    return []
