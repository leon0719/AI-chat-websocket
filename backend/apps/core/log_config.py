"""Structured logging configuration using Loguru."""

import json
import os
import sys
import traceback
from contextvars import ContextVar

from loguru import logger

# Context variables for request tracking
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
user_id_var: ContextVar[str] = ContextVar("user_id", default="-")


def get_log_context() -> dict:
    """Get current logging context."""
    return {
        "request_id": request_id_var.get(),
        "user_id": user_id_var.get(),
    }


def json_sink(message):
    """JSON formatter for production logs."""
    record = message.record
    log_record = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "module": record["name"],
        "function": record["function"],
        "line": record["line"],
        **get_log_context(),
        **record.get("extra", {}),
    }
    if record["exception"]:
        # record["exception"] is a tuple of (type, value, traceback)
        exc_type, exc_value, exc_tb = record["exception"]
        if exc_value is not None:
            log_record["exception"] = "".join(
                traceback.format_exception(exc_type, exc_value, exc_tb)
            )
    sys.stdout.write(json.dumps(log_record, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _add_context(record):
    """Add context variables to log record."""
    record["extra"]["request_id"] = request_id_var.get()


def setup_logging():
    """Configure logging based on environment."""
    logger.remove()

    env = os.getenv("ENV", "local")

    if env == "prod":
        logger.add(
            json_sink,
            level="INFO",
            format="{message}",
        )
    else:
        logger.add(
            sys.stderr,
            format=(
                "<green>{time:HH:mm:ss}</green> | "
                "<level>{level: <7}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan> | "
                "<magenta>[{extra[request_id]}]</magenta> | "
                "<level>{message}</level>"
            ),
            level="DEBUG",
            colorize=True,
        )

    logger.configure(patcher=_add_context)


setup_logging()
