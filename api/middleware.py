"""FastAPI middleware: request ID injection into logging context."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, Request

from common.logging import get_logger, request_id_var

logger = get_logger("api.middleware")


def add_request_id_middleware(app: FastAPI, header_name: str = "X-Request-ID") -> None:
    """Inject a per-request correlation id and attach it to every log line."""

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next: Any) -> Any:
        rid = request.headers.get(header_name.lower())
        if not rid:
            rid = str(uuid.uuid4())
        request_id_var.set(rid)
        response = await call_next(request)
        response.headers[header_name] = rid
        return response
