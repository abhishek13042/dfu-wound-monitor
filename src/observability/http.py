"""ASGI middleware: one request ID per request, response header, access log and request metrics."""

from __future__ import annotations

import ipaddress
import logging
import time
from typing import Any

from src.observability.context import HEADER, accept_request_id, bind_request_id
from src.observability.metrics import record_request

log = logging.getLogger("dfu.api.access")
_SKIP_LOG = ("/health/live", "/metrics")
_HEADER_KEY = HEADER.lower().encode()


class RequestContextMiddleware:
    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        supplied = next((value.decode("latin-1") for key, value in scope.get("headers", [])
                         if key == _HEADER_KEY), None)
        request_id = bind_request_id(accept_request_id(supplied))
        scope.setdefault("state", {})["request_id"] = request_id
        started, status = time.perf_counter(), 500

        async def send_with_id(message: dict[str, Any]) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                headers = list(message.get("headers", []))
                if not any(key.lower() == _HEADER_KEY for key, _ in headers):  # an error response may already carry it
                    headers.append((_HEADER_KEY, request_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            seconds = time.perf_counter() - started
            route = getattr(scope.get("route"), "path", None) or "unmatched"
            record_request(scope["method"], route, status, seconds)
            if scope["path"] not in _SKIP_LOG:
                # The route template, never the raw path, so IDs in URLs stay out of the log fields.
                log.info("request", extra={"method": scope["method"], "route": route, "status": status,
                                           "duration_ms": round(seconds * 1000, 1)})


def client_is_private(scope: dict[str, Any]) -> bool:
    client = scope.get("client")
    if not client:
        return False
    try:
        address = ipaddress.ip_address(client[0])
    except ValueError:
        return client[0] in ("testclient", "localhost")
    return address.is_private or address.is_loopback
