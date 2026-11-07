"""Optional error reporting.  Off unless ``SENTRY_DSN`` is set and ``sentry_sdk`` is installed.

The account is the deployer's; nothing here sends data by default.  Every event
passes through ``scrub_event`` first, so it carries no image, token or filename.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from src.observability.logs import scrub

log = logging.getLogger("dfu.errors")


def scrub_event(event: dict[str, Any], hint: Any = None) -> dict[str, Any] | None:
    try:
        event.pop("request", None)  # headers, cookies and bodies stay out entirely
        return json.loads(scrub(json.dumps(event, default=str)))
    except Exception:  # noqa: BLE001 - an event that cannot be cleaned is dropped, never sent raw
        return None


def init_error_reporting(service: str) -> bool:
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return False
    try:
        import sentry_sdk
    except ImportError:
        log.warning("SENTRY_DSN is set but sentry_sdk is not installed; error reporting is off")
        return False
    sentry_sdk.init(dsn=dsn, before_send=scrub_event, send_default_pii=False, traces_sample_rate=0.0,
                    server_name=service, release=os.environ.get("DFU_RELEASE"))
    return True
