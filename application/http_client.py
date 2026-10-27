import httpx

async_client: httpx.AsyncClient | None = None

async def init_client():
    """
    Inicializa um único AsyncClient compartilhado para toda a aplicação.
    """
    global async_client
    if async_client is None:
        async_client = httpx.AsyncClient(timeout=30.0)

async def close_client():
    """
    Fecha o cliente global ao encerrar o servidor.
    """
    global async_client
    if async_client is not None:
        await async_client.aclose()
        async_client = None