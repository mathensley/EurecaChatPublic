import logging
import logging.config
import os

from pythonjsonlogger import jsonlogger


def get_logging_config():
    is_docker = os.getenv("DOCKER_ENV", "false").lower() == "true"
    observability_enabled = (
        os.getenv("ENABLE_GRAFANA_OBSERVABILITY", "false").lower() == "true"
    )

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": jsonlogger.JsonFormatter,
                "fmt": "%(asctime)s %(levelname)s %(name)s %(message)s",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json",
                "stream": "ext://sys.stdout"
            }
        },
        "loggers": {
            "app": {"handlers": ["console"], "level": "INFO", "propagate": False},
            "socket": {"handlers": ["console"], "level": "INFO", "propagate": False},
            "tool": {"handlers": ["console"], "level": "INFO", "propagate": False},
            "http": {"handlers": ["console"], "level": "INFO", "propagate": False},
            "security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
            "httpx": {"level": "WARNING"},
            "hypercorn": {"level": "INFO"},
            "asyncio": {"level": "WARNING"},
        },
        "root": {
            "level": "WARNING",
            "handlers": ["console"]
        }
    }
    
    if not is_docker or observability_enabled:
        log_filename = (
            "/var/log/eureca/backend.jsonl"
            if is_docker
            else "./application/logs/system_logs.jsonl"
        )
        os.makedirs(os.path.dirname(log_filename), exist_ok=True)
        config["handlers"]["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": log_filename,
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 2,
            "formatter": "json",
            "encoding": "utf-8",
        }
        for logger_name in ["app", "socket", "tool", "http", "security"]:
            config["loggers"][logger_name]["handlers"].append("file")
        config["root"]["handlers"].append("file")
    
    return config


def setup_logging():
    logging.config.dictConfig(get_logging_config())
