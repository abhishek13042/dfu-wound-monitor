"""P10-S01 observability: request IDs, scrubbed JSON logs and Prometheus metrics.

Every part of this package is best effort.  A telemetry failure is swallowed so
it can never fail a user request (P10-S01 invariant).
"""

from src.observability.context import bind_request_id, current_request_id, new_request_id
from src.observability.logs import configure_logging, scrub

__all__ = ["bind_request_id", "configure_logging", "current_request_id", "new_request_id", "scrub"]
