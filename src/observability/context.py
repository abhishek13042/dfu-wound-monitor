"""The one ID that follows a request through the API, the queue and the worker (REQ-P10-S01-001)."""

from __future__ import annotations

import re
import uuid
from contextvars import ContextVar

HEADER = "X-Request-ID"
# A caller may supply its own ID; anything else is replaced, so a header cannot inject log content.
_VALID = re.compile(r"^[A-Za-z0-9._:-]{8,64}$")
_current: ContextVar[str | None] = ContextVar("dfu_request_id", default=None)


def new_request_id() -> str:
    return f"req_{uuid.uuid4().hex}"


def accept_request_id(supplied: str | None) -> str:
    return supplied if supplied and _VALID.match(supplied) else new_request_id()


def bind_request_id(request_id: str | None) -> str:
    request_id = request_id or new_request_id()
    _current.set(request_id)
    return request_id


def current_request_id() -> str | None:
    return _current.get()
