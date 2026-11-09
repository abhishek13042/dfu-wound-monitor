"""Structured JSON logs that never carry images, tokens or user filenames (REQ-P10-S01-003).

``scrub`` runs on the final text of every record, after formatting and on the
traceback, so a secret is removed wherever it appears: in the message, an
argument or an exception.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import UTC, datetime
from typing import Any

from src.observability.context import current_request_id

REDACTED = "[redacted]"
_PATTERNS = [
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+"), f"Bearer {REDACTED}"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*"), REDACTED),           # JWT
    (re.compile(r"(?i)data:[a-z]+/[a-z0-9.+-]+;base64,[A-Za-z0-9+/=]+"), f"data:{REDACTED}"),  # inline images
    (re.compile(r"[A-Za-z0-9+/]{200,}={0,2}"), REDACTED),                                       # long base64 runs
    (re.compile(r"(?i)\b(signature|token|access_token|id_token|refresh_token|password|secret|api_key)=[^&\s\"']+"),
     rf"\1={REDACTED}"),
    (re.compile(r"(?i)\b(filename|original_filename)(\"?\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;}]+)"),
     rf"\1\2{REDACTED}"),
    (re.compile(r"\\x[0-9a-f]{2}(\\x[0-9a-f]{2}){15,}"), REDACTED),                              # repr of raw bytes
]
_RESERVED = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {"message", "asctime"}


def scrub(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        try:
            entry: dict[str, Any] = {
                "time": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
                "level": record.levelname,
                "service": self.service,
                "logger": record.name,
                "request_id": getattr(record, "request_id", None) or current_request_id(),
                "message": record.getMessage(),
            }
            for key, value in record.__dict__.items():
                if key not in _RESERVED and key not in entry and not key.startswith("_"):
                    entry[key] = value if isinstance(value, (int, float, bool, type(None))) else str(value)
            if record.exc_info:
                entry["exception"] = self.formatException(record.exc_info)
            return scrub(json.dumps(entry, default=str))
        except Exception:  # noqa: BLE001 - a log line must never raise
            return json.dumps({"level": "ERROR", "message": "log record could not be formatted"})


_configured = False


def configure_logging(service: str, *, stream: Any = None, force: bool = False) -> None:
    """Send the ``dfu`` loggers to one JSON handler.  ``DFU_LOG_FORMAT=plain`` keeps plain text for a terminal."""

    global _configured
    if _configured and not force:
        return
    handler = logging.StreamHandler(stream or sys.stderr)
    if os.environ.get("DFU_LOG_FORMAT", "json").lower() == "plain":
        handler.setFormatter(_PlainScrubbed("%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s"))
    else:
        handler.setFormatter(JsonFormatter(service))
    logger = logging.getLogger("dfu")
    for existing in [h for h in logger.handlers if getattr(h, "_dfu", False)]:
        logger.removeHandler(existing)
    handler._dfu = True  # type: ignore[attr-defined]
    logger.addHandler(handler)
    logger.setLevel(os.environ.get("DFU_LOG_LEVEL", "INFO").upper())
    logger.propagate = False
    _configured = True


class _PlainScrubbed(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record.request_id = getattr(record, "request_id", None) or current_request_id() or "-"
        return scrub(super().format(record))
