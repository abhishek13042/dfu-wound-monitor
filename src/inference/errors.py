"""Typed failures for the P03-S01 inference contract.

Every failure carries a stable ``code`` and a ``category``.  The category is
what callers (the API, the reliability taxonomy) use to tell an input problem
from a model-artifact problem from an unexpected runtime failure:

* ``INPUT``  - the caller supplied something unusable (missing, unreadable,
  unsupported format, too large).
* ``MODEL``  - the model artifact or its configuration is missing, corrupt or
  incompatible, or the forward pass failed.
* ``CONFIG`` - the inference configuration itself is malformed.
"""

from __future__ import annotations

from typing import Any


class InferenceError(Exception):
    category = "MODEL"
    code = "INFERENCE_ERROR"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {"category": self.category, "code": self.code, "message": self.message, "details": self.details}


class InputError(InferenceError):
    category = "INPUT"
    code = "INPUT_INVALID"


class InputMissingError(InputError):
    code = "INPUT_MISSING"


class InputUnreadableError(InputError):
    code = "INPUT_UNREADABLE"


class UnsupportedFormatError(InputError):
    code = "INPUT_UNSUPPORTED_FORMAT"


class InputTooLargeError(InputError):
    code = "INPUT_TOO_LARGE"


class ConfigError(InferenceError):
    category = "CONFIG"
    code = "CONFIG_INVALID"


class CheckpointMissingError(InferenceError):
    code = "CHECKPOINT_MISSING"


class CheckpointCorruptError(InferenceError):
    code = "CHECKPOINT_CORRUPT"


class CheckpointChecksumError(InferenceError):
    code = "CHECKPOINT_CHECKSUM_MISMATCH"


class CheckpointIncompatibleError(InferenceError):
    code = "CHECKPOINT_INCOMPATIBLE"


class ModelExecutionError(InferenceError):
    code = "MODEL_EXECUTION_FAILED"
