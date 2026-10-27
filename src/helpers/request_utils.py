import httpx, traceback, logging
from typing import Any
import application.http_client as http_client

http_logger = logging.getLogger("http")

async def make_request(url: str, params: dict = {}, headers: dict | None = None) -> dict[str, Any] | None:
    """
    Faz uma requisição GET com tratamento de erros.
    Usa o cliente HTTP Global compartilhado.
    """
    endpoint = url.split("?")[0]

    if http_client.async_client is None:
        raise RuntimeError("Async HTTP client not initialized.")
    
    default_headers = {
        "Accept": "application/json",
    }

    if headers:
        default_headers.update(headers)

    try:
        response = await http_client.async_client.get(url, params=params, headers=default_headers, timeout=30.0)
        
        http_logger.info(
            "external_request",
            extra={
                "endpoint": endpoint,
                "method": "GET",
                "status": response.status_code
            }
        )

        response.raise_for_status()
        return response.json()
    
    except httpx.HTTPStatusError as e:
        status = e.response.status_code

        http_logger.warning(
            "external_request_failed",
            extra={"endpoint": endpoint, "status": status}
        )

        if status == 404:
            return None

        if status >= 500:
            raise RuntimeError("Serviço externo temporariamente indisponível.")

        raise RuntimeError(f"Erro HTTP {status}.")

    except httpx.TimeoutException:
        raise RuntimeError("Tempo limite da requisição excedido.")

    except httpx.RequestError:
        raise RuntimeError("Erro de conexão com serviço externo.")