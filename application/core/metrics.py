"""Métricas Prometheus do backend, expostas apenas na rede interna."""

from __future__ import annotations

import logging
import os
import platform
from time import perf_counter
from typing import Any

from prometheus_client import Counter, Gauge, Histogram, Info, start_http_server


logger = logging.getLogger("app")

METRICS_PORT = 9464

BACKEND_INFO = Info(
    "eureca_backend",
    "Informações estáticas do processo do backend."
)
HTTP_REQUESTS = Counter(
    "eureca_backend_http_requests_total",
    "Total de requisições HTTP concluídas.",
    ("method", "route", "status_class")
)
HTTP_REQUEST_DURATION = Histogram(
    "eureca_backend_http_request_duration_seconds",
    "Duração das requisições HTTP.",
    ("method", "route"),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)
)
SOCKET_CONNECTIONS = Gauge(
    "eureca_backend_socket_connections",
    "Quantidade atual de conexões Socket.IO."
)
SOCKET_EVENTS = Counter(
    "eureca_backend_socket_events_total",
    "Total de eventos Socket.IO processados.",
    ("event", "status")
)
CHAT_REQUESTS = Counter(
    "eureca_backend_chat_requests_total",
    "Total de chats processados.",
    ("authenticated", "status")
)
CHAT_DURATION = Histogram(
    "eureca_backend_chat_duration_seconds",
    "Duração total do processamento de chats.",
    ("authenticated", "status"),
    buckets=(0.5, 1, 2.5, 5, 10, 20, 30, 60, 120, 300)
)

_metrics_server: Any | None = None
_metrics_thread: Any | None = None


def observability_enabled() -> bool:
    return os.getenv("ENABLE_GRAFANA_OBSERVABILITY", "false").lower() == "true"


def start_metrics_server() -> None:
    """Inicia o endpoint Prometheus em uma porta separada da aplicação."""
    global _metrics_server, _metrics_thread

    if not observability_enabled() or _metrics_server is not None:
        return

    BACKEND_INFO.info(
        {
            "version": os.getenv("APP_VERSION", "local"),
            "python": platform.python_version()
        }
    )
    _metrics_server, _metrics_thread = start_http_server(METRICS_PORT, addr="0.0.0.0")
    logger.info("prometheus_metrics_started", extra={"port": METRICS_PORT})


def stop_metrics_server() -> None:
    """Encerra o servidor auxiliar durante o shutdown do Hypercorn."""
    global _metrics_server, _metrics_thread

    if _metrics_server is None:
        return

    _metrics_server.shutdown()
    _metrics_server.server_close()
    if _metrics_thread is not None:
        _metrics_thread.join(timeout=5)
    _metrics_server = None
    _metrics_thread = None


def start_timer() -> float:
    return perf_counter()


def observe_http_request(method: str, route: str, status_code: int, started_at: float) -> None:
    if not observability_enabled():
        return
    method = method.upper()
    status_class = f"{status_code // 100}xx"
    HTTP_REQUESTS.labels(method, route, status_class).inc()
    HTTP_REQUEST_DURATION.labels(method, route).observe(perf_counter() - started_at)


def socket_connected(active_connections: int) -> None:
    if observability_enabled():
        # anon_sessions armazena todas as conexões, inclusive autenticadas.
        # Usar o total atual evita deriva em reconexões e disconnects repetidos.
        SOCKET_CONNECTIONS.set(active_connections)
        SOCKET_EVENTS.labels("connect", "success").inc()


def socket_disconnected(active_connections: int) -> None:
    if not observability_enabled():
        return
    SOCKET_CONNECTIONS.set(active_connections)
    SOCKET_EVENTS.labels("disconnect", "success").inc()


def observe_socket_event(event: str, status: str) -> None:
    if observability_enabled():
        SOCKET_EVENTS.labels(event, status).inc()


def chat_started(authenticated: bool) -> tuple[str, float]:
    auth_label = "true" if authenticated else "false"
    return auth_label, perf_counter()


def chat_finished(auth_label: str, status: str, started_at: float) -> None:
    if not observability_enabled():
        return
    CHAT_REQUESTS.labels(auth_label, status).inc()
    CHAT_DURATION.labels(auth_label, status).observe(perf_counter() - started_at)
