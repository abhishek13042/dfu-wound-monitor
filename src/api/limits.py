"""P10-S03 rate limits and security headers.

Limits are a sliding window per key, held in this process's memory, so each
API replica counts on its own: N replicas allow up to N times the limit.  The
window holds only a key (a client address or a user ID) and request times,
never request content (REQ-P10-S03-004).

The per-address limit runs before sign-in and is set loose, because people
behind one proxy share an address; the per-user limit runs after sign-in and
is the one that bites.
"""

from __future__ import annotations

import math
import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from typing import Any

from src.api.errors import ApiError, error_response

MAX_KEYS = 10_000  # oldest keys are dropped beyond this, so memory stays bounded


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float = 60.0, clock: Callable[[], float] = time.monotonic) -> None:
        self.limit = limit
        self.window = window_seconds
        self.clock = clock
        self._hits: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = threading.Lock()

    def check(self, key: str) -> float | None:
        """Count one request for ``key``.  Returns ``None`` if allowed, else seconds until the next is."""

        if self.limit <= 0:
            return None
        now = self.clock()
        with self._lock:
            hits = self._hits.pop(key, None) or deque()
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            self._hits[key] = hits
            if len(self._hits) > MAX_KEYS:
                self._hits.popitem(last=False)
            if len(hits) >= self.limit:
                return hits[0] + self.window - now
            hits.append(now)
            return None

    def enforce(self, key: str) -> None:
        wait = self.check(key)
        if wait is not None:
            raise limited(wait)


def limited(wait: float) -> ApiError:
    seconds = max(1, math.ceil(wait))
    return ApiError("BUSY", "RATE_LIMITED", "Too many requests; try again shortly",
                    {"retry_after_seconds": seconds})


class AddressLimitMiddleware:
    """The per-address limit for ``/api/`` routes; health checks and metrics are not counted."""

    def __init__(self, app: Any, limiter: RateLimiter) -> None:
        self.app = app
        self.limiter = limiter

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] == "http" and scope["path"].startswith("/api/") and scope["method"] != "OPTIONS":
            address = (scope.get("client") or ("unknown", 0))[0]
            wait = self.limiter.check(f"ip:{address}")
            if wait is not None:
                await error_response(limited(wait))(scope, receive, send)
                return
        await self.app(scope, receive, send)


_COMMON = [
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
    (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),
]
# JSON and signed-link routes are never rendered or framed.  The v1 dashboard is
# left out of these two, because a Hugging Face Space shows it inside a frame.
_API_ONLY = [
    (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
    (b"x-frame-options", b"DENY"),
]


class SecurityHeadersMiddleware:
    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        extra = _COMMON + (_API_ONLY if scope["path"].startswith(("/api/", "/health", "/metrics")) else [])

        async def send_with_headers(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {key.lower() for key, _ in headers}
                headers += [(key, value) for key, value in extra if key not in present]
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)
