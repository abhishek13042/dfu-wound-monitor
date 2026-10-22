"""P06-S03 release manifest: every version, config and artifact hash in one file.

    python scripts/deployment/build_release_manifest.py

Writes ``reports/final/release_manifest.json``.  The checkpoint itself is not
in git (293 MB); the manifest pins its SHA-256, so a downloaded copy can be
verified before use (the service also refuses a checkpoint whose hash differs).
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.api.app import LIMITATIONS, SERVICE_VERSION  # noqa: E402
from src.api.schemas import API_VERSION  # noqa: E402
from src.inference.engine import DEFAULT_INFERENCE_CONFIG, ENGINE_VERSION, InferenceConfig, sha256_file  # noqa: E402
from src.longitudinal.comparison import CompatibilityPolicy  # noqa: E402
from src.longitudinal.records import SCHEMA_VERSION as RECORD_SCHEMA_VERSION  # noqa: E402
from src.longitudinal.trends import TREND_VERSION  # noqa: E402
from src.measurement.engine import ENGINE_VERSION as MEASUREMENT_VERSION  # noqa: E402
from src.quality.gate import DEFAULT_QUALITY_CONFIG  # noqa: E402
from src.storage.database import SCHEMA_VERSION as DB_SCHEMA_VERSION  # noqa: E402

MEASUREMENT_CONFIG = PROJECT_ROOT / "configs/measurement/measurement_v1.json"
EVIDENCE = [
    "reports/experiments/spec_02_03_report.md",
    "reports/experiments/spec-02-03/cpu_verification/heldout_test_evaluation.json",
    "reports/quality/quality_gate_calibration.json",
    "reports/final/p06_validation_fuseg2021_test.json",
    "reports/final/p06_validation_lowerlimb_external.json",
    "reports/final/p06_benchmark.json",
    "reports/final/phase_06_validation_report.md",
    "docs/release/RELEASE.md",
]


def rel(path: Path) -> str:
    return Path(path).resolve().relative_to(PROJECT_ROOT).as_posix()


def git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> int:
    config = InferenceConfig.load(DEFAULT_INFERENCE_CONFIG)
    checkpoint_present = config.checkpoint_path.is_file()
    manifest = {
        "release": "DFU-WoundMonitor research prototype",
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git": {"commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain"))},
        "versions": {
            "service": SERVICE_VERSION, "api": API_VERSION, "inference_engine": ENGINE_VERSION,
            "measurement_engine": MEASUREMENT_VERSION, "record_schema": RECORD_SCHEMA_VERSION,
            "database_schema": DB_SCHEMA_VERSION, "comparison_policy": CompatibilityPolicy().version,
            "trend": TREND_VERSION, "model": config.model_version,
        },
        "model_artifact": {
            "checkpoint_path": rel(config.checkpoint_path),
            "checkpoint_sha256": config.checkpoint_sha256,
            "present": checkpoint_present,
            "verified": checkpoint_present and sha256_file(config.checkpoint_path) == config.checkpoint_sha256,
            "in_git": False,
        },
        "configs": {rel(p): sha256_file(p) for p in (DEFAULT_INFERENCE_CONFIG, config.training_config_path,
                                                     DEFAULT_QUALITY_CONFIG, MEASUREMENT_CONFIG,
                                                     PROJECT_ROOT / "requirements.txt")},
        "evidence": {path: (sha256_file(PROJECT_ROOT / path) if (PROJECT_ROOT / path).is_file() else None)
                     for path in EVIDENCE},
        "build_environment": {"python": platform.python_version(), "platform": platform.platform()},
        "commands": {
            "install": "python -m pip install -r requirements.txt",
            "tests": "python -m pytest -q",
            "serve": "python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000",
            "smoke_test": "python scripts/deployment/smoke_test.py",
            "validation": "python scripts/evaluation/run_phase_06_validation.py --split test",
            "benchmark": "python scripts/evaluation/run_phase_06_benchmark.py --images 20",
        },
        "limitations": LIMITATIONS,
    }
    out = PROJECT_ROOT / "reports/final/release_manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    missing = [path for path, digest in manifest["evidence"].items() if digest is None]
    print(json.dumps({"output": rel(out), "model_verified": manifest["model_artifact"]["verified"],
                      "missing_evidence": missing, "git": manifest["git"]}, indent=2))
    return 0 if manifest["model_artifact"]["verified"] and not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
