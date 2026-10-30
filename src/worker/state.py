"""The analysis job state machine (REQ-P07-S05-002).

RUNNING may return to QUEUED, because a retry or a lost worker sends the job
back.  Finished states are final, which is what makes a redelivered message
harmless.
"""

from __future__ import annotations

QUEUED, RUNNING, COMPLETED, QUALITY_REJECTED, FAILED = "QUEUED", "RUNNING", "COMPLETED", "QUALITY_REJECTED", "FAILED"
ACTIVE = (QUEUED, RUNNING)
TRANSITIONS: dict[str, frozenset[str]] = {
    QUEUED: frozenset({RUNNING}),
    RUNNING: frozenset({QUEUED, COMPLETED, QUALITY_REJECTED, FAILED}),
    COMPLETED: frozenset(),
    QUALITY_REJECTED: frozenset(),
    FAILED: frozenset(),
}


class IllegalTransition(ValueError):
    pass


def require_transition(current: str, target: str) -> None:
    if target not in TRANSITIONS.get(current, frozenset()):
        raise IllegalTransition(f"An analysis job cannot go from {current} to {target}")
