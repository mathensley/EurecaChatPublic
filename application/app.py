import asyncio
import os
import sys

import asyncpg
import socketio
from dotenv import load_dotenv
from quart import Quart, g, request
from quart_cors import cors

from application.config import DB_URI
from application.http_client import close_client, init_client
from application.logs.logging_config import setup_logging

from .core.current_period import CurrentPeriodCache
from .core.metrics import (
    observe_http_request,
    start_metrics_server,
    start_timer,
    stop_metrics_server,
)
from .core.system import build_system
from .core.tracing import setup_tracing_phoenix
from .db.saver import create_postgres_pool, get_postgres_saver
from .routes import api, audio, chat, downloads, feedback, login, web
from .socket.handlers import register_socket_handlers
from .tasks.token_usage_cleanup import cleanup_old_token_usage


load_dotenv(override=True)
setup_logging() # Setup para o logging do sistema (em json)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

app = Quart(__name__, static_folder=None, template_folder=None)
app_origin = os.getenv("APP_ORIGIN", "*").strip() or "*"
app = cors(app, allow_origin=app_origin, allow_credentials=app_origin != "*")

socket_origins = app_origin
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=socket_origins,
    ping_timeout=120,
    ping_interval=30,
    max_http_buffer_size=25 * 1024 * 1024,
)
sio_app = socketio.ASGIApp(sio, app)

# Variáveis principais
app.system = None
app.checkpointer_pool = None
app.db_pool = None


@app.before_request
async def start_http_request_metrics():
    # Health checks e downloads não representam tráfego funcional da aplicação.
    if request.path.startswith(("/api/health/", "/downloads/")):
        return

    url_rule = getattr(request, "url_rule", None)
    g.prometheus_route = getattr(url_rule, "rule", None) or "unmatched"
    g.prometheus_started_at = start_timer()


@app.after_request
async def finish_http_request_metrics(response):
    started_at = getattr(g, "prometheus_started_at", None)
    if started_at is not None:
        observe_http_request(
            request.method,
            g.prometheus_route,
            response.status_code,
            started_at,
        )
    return response

@app.before_serving
async def setup():
    start_metrics_server()

    # Tracing Phoenix
    setup_tracing_phoenix()

    # Inicializa o cliente HTTP global
    await init_client()

    # O pool descarta conexões mortas e abre novas após reinícios/interrupções do Postgre
    app.checkpointer_pool = create_postgres_pool(DB_URI, min_size=1, max_size=2)
    await app.checkpointer_pool.open(wait=True)
    app.checkpointer = get_postgres_saver(app.checkpointer_pool)

    # Inicializa a pool do asyncpg, para lidar com as demais tabelas do sistema
    app.db_pool = await asyncpg.create_pool(
        dsn=DB_URI,
        min_size=1,
        max_size=5,
        server_settings={"application_name": "eureca-app"},
    )

    # O cache consulta o SIG somente quando não houver valor persistido válido.
    app.current_period_cache = CurrentPeriodCache(app.db_pool)

    # Inicializa o chat
    app.system = build_system(app.checkpointer)

    # Inicia a tarefa de limpeza da tabela token_usage
    asyncio.create_task(cleanup_old_token_usage(app.db_pool))

@app.after_serving
async def shutdown():
    await close_client()
    if app.db_pool is not None:
        await app.db_pool.close()
    if app.checkpointer_pool is not None:
        await app.checkpointer_pool.close()
    stop_metrics_server()

# Routes
app.register_blueprint(audio.bp)
app.register_blueprint(chat.bp)
app.register_blueprint(login.bp)
app.register_blueprint(api.bp)
app.register_blueprint(feedback.bp)
app.register_blueprint(downloads.bp)
app.register_blueprint(web.bp)

# Socket.IO
register_socket_handlers(sio, app)
