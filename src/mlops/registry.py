"""P10-S04 model registry: one record per model version, and a log of every promotion and rollback.

The registry is a JSON file kept in git (``configs/models/registry.json``), so
each change is reviewed and its history is the git log as well as the
``events`` list.  There are few models, so a file is enough (spec §11).

A record has ``model_version``, ``sha256``, ``runtime``, ``dataset_refs``,
``metrics``, ``limitations``, ``status`` and ``approved_by`` (spec §9), plus the
``inference_config`` that loads it and the ``evidence`` reports the gates read.
Exactly one record is ``ACTIVE`` once any has been promoted.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = PROJECT_ROOT / "configs/models/registry.json"
STATUSES = ("CANDIDATE", "CANARY", "ACTIVE", "RETIRED")
REQUIRED = ("model_version", "sha256", "runtime", "dataset_refs", "metrics", "limitations", "status", "approved_by")
RUNTIMES = ("pytorch", "onnx")


class RegistryError(ValueError):
    """A record or a change the registry refuses."""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def validate(record: dict[str, Any]) -> None:
    """Refuse a record that lacks any field the contract names (REQ-P10-S04-001)."""

    missing = [name for name in REQUIRED if name not in record]
    if missing:
        raise RegistryError(f"Missing fields: {', '.join(missing)}")
    if not re.fullmatch(r"[0-9a-f]{64}", str(record["sha256"])):
        raise RegistryError("sha256 must be 64 lowercase hex characters")
    if record["runtime"] not in RUNTIMES:
        raise RegistryError(f"runtime must be one of {RUNTIMES}")
    if not record["dataset_refs"] or not all(ref.get("dataset") and ref.get("version")
                                             for ref in record["dataset_refs"]):
        raise RegistryError("dataset_refs needs at least one {dataset, version}")
    if not isinstance(record["metrics"], dict) or not record["metrics"]:
        raise RegistryError("metrics must not be empty")
    if not record["limitations"] or not all(isinstance(text, str) and text.strip() for text in record["limitations"]):
        raise RegistryError("limitations must list at least one limitation")
    if record["status"] not in STATUSES:
        raise RegistryError(f"status must be one of {STATUSES}")
    if record["status"] in ("CANARY", "ACTIVE") and not record["approved_by"]:
        raise RegistryError("A CANARY or ACTIVE model needs approved_by")


class Registry:
    def __init__(self, path: Path = DEFAULT_REGISTRY, root: Path = PROJECT_ROOT) -> None:
        self.path, self.root = path, root  # artifact and evidence paths are relative to root
        if path.exists():
            self.data = json.loads(path.read_text(encoding="utf-8"))
        else:
            self.data = {"schema": "p10-s04-v1", "models": [], "events": []}
        for record in self.data["models"]:
            validate(record)
        if len([r for r in self.data["models"] if r["status"] == "ACTIVE"]) > 1:
            raise RegistryError("More than one ACTIVE model")

    # ------------------------------------------------------------------ reads
    def get(self, model_version: str) -> dict[str, Any]:
        for record in self.data["models"]:
            if record["model_version"] == model_version:
                return record
        raise RegistryError(f"No model {model_version!r} in the registry")

    def active(self) -> dict[str, Any] | None:
        return next((r for r in self.data["models"] if r["status"] == "ACTIVE"), None)

    def verify_artifact(self, record: dict[str, Any]) -> None:
        """The artifact on disk must match the recorded hash (spec §10: the active version is hash-verified)."""

        path = self.root / record["artifact_path"]
        if not path.exists():
            raise RegistryError(f"Artifact not found: {record['artifact_path']}")
        if file_sha256(path) != record["sha256"]:
            raise RegistryError(f"Artifact hash does not match the record for {record['model_version']}")

    # ----------------------------------------------------------------- writes
    def register(self, record: dict[str, Any]) -> dict[str, Any]:
        record = {**deepcopy(record), "status": "CANDIDATE", "approved_by": None, "registered_at": _now()}
        validate(record)
        if any(r["model_version"] == record["model_version"] for r in self.data["models"]):
            raise RegistryError(f"{record['model_version']} is already registered; versions are never reused")
        self.data["models"].append(record)
        self._event("REGISTER", record["model_version"], None, None)
        return record

    def promote(self, model_version: str, approved_by: str, gates: dict[str, Any], to: str = "ACTIVE") -> None:
        """Make a candidate CANARY or ACTIVE.  The gates must all have passed, and a person must approve."""

        if not approved_by or not approved_by.strip():
            raise RegistryError("Promotion needs a named approver (REQ-P10-S04-002)")
        if not gates or not all(gate["passed"] for gate in gates.values()):
            raise RegistryError("Promotion refused: a gate did not pass")
        record = self.get(model_version)
        if record["status"] not in ("CANDIDATE", "CANARY") or (to == "CANARY" and record["status"] != "CANDIDATE"):
            raise RegistryError(f"{model_version} is {record['status']} and cannot become {to}")
        previous = self.active()
        if to == "ACTIVE" and previous is not None:
            previous["status"] = "RETIRED"
            record["replaces"] = previous["model_version"]
        record["status"], record["approved_by"] = to, approved_by.strip()
        self._event(f"PROMOTE_{to}", model_version, previous["model_version"] if previous else None, approved_by,
                    gates=gates)

    def rollback(self, approved_by: str) -> str:
        """Put back the model the active one replaced (REQ-P10-S04-003).  Returns the version now active."""

        if not approved_by or not approved_by.strip():
            raise RegistryError("Rollback needs a named person")
        current = self.active()
        if current is None or not current.get("replaces"):
            raise RegistryError("There is no earlier model to roll back to")
        earlier = self.get(current["replaces"])
        current["status"], earlier["status"] = "RETIRED", "ACTIVE"
        self._event("ROLLBACK", earlier["model_version"], current["model_version"], approved_by)
        return earlier["model_version"]

    def stop_canary(self, model_version: str, reason: str) -> None:
        record = self.get(model_version)
        if record["status"] != "CANARY":
            raise RegistryError(f"{model_version} is not a canary")
        record["status"] = "CANDIDATE"
        self._event("STOP_CANARY", model_version, None, None, reason=reason)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2) + "\n", encoding="utf-8")

    def _event(self, action: str, model_version: str, previous: str | None, by: str | None, **extra: Any) -> None:
        self.data["events"].append({"at": _now(), "action": action, "model_version": model_version,
                                    "previous": previous, "by": by, **extra})
