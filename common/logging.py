"""Structured JSON logging with request/interview correlation ids."""

from __future__ import annotations

import contextvars
import json
import logging
import sys
import time
from typing import Any

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)
interview_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "interview_id", default=None
)


def set_request_id(value: str | None) -> None:
    request_id_var.set(value)


def set_interview_id(value: str | None) -> None:
    interview_id_var.set(value)


def get_request_id() -> str | None:
    return request_id_var.get()


def get_interview_id() -> str | None:
    return interview_id_var.get()


class JsonFormatter(logging.Formatter):
    """Single-line JSON log records with correlation ids."""

    _RESERVED = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "taskName", "message", "asctime",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": f"{record.module}:{record.lineno}",
            "request_id": request_id_var.get(),
            "interview_id": interview_id_var.get(),
        }
        for key, value in record.__dict__.items():
            if key not in self._RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging(level: str = "INFO") -> None:
    """Replace root handlers with a JSON console handler."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
