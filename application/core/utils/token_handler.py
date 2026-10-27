import httpx

from application import http_client


INVALID_TOKEN_STATUS_CODES = frozenset({400, 401, 403})


def parse_user_profile(profile):
    """Normaliza os campos do perfil retornado pelo serviço de autenticação."""
    if not isinstance(profile, dict):
        return None, None, None, None

    cpf = str(profile["id"]) if profile.get("id") is not None else None
    attributes = profile.get("attributes")
    user_identifier = None
    if isinstance(attributes, dict):
        user_identifier = next(
            (str(value) for value in attributes.values() if value is not None),
            None,
        )
    return profile.get("name"), cpf, user_identifier, profile.get("type")

async def fetch_profile(token):
    """Busca o perfil e preserva o status HTTP para classificar falhas de sessão."""
    url = "https://eureca.sti.ufcg.edu.br/as-sig/profile"
    headers = {
        "accept": "application/json",
        "token-de-autenticacao": token
    }
    
    client = http_client.async_client
    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=30.0)

    try:
        response = await client.get(url, headers=headers)
        if response.status_code != 200:
            return None, response.status_code

        payload = response.json()
        return (payload if isinstance(payload, dict) else None), response.status_code
    except (httpx.HTTPError, ValueError):
        return None, None
    finally:
        if owns_client:
            await client.aclose()


async def get_info(token):
    """Retorna o perfil quando o token é válido, mantendo a API legada."""
    profile, status_code = await fetch_profile(token)
    return profile if status_code == 200 else None
