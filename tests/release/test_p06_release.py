"""P06-S03 release checks: pinned artifacts, manifest, health semantics, wording."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from src.inference.engine import DEFAULT_INFERENCE_CONFIG, InferenceConfig

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLINICAL = re.compile(r"diagnos|\bheal(?:ing|ed|s)?\b|prognos|treat|infect|amputat|clinical|recommend", re.IGNORECASE)
NEGATION = re.compile(r"\b(not|never|no|without|must not|cannot)\b", re.IGNORECASE)


def test_release_config_pins_existing_training_config():
    config = InferenceConfig.load(DEFAULT_INFERENCE_CONFIG)
    assert re.fullmatch(r"[0-9a-f]{64}", config.checkpoint_sha256)
    assert config.training_config_path.is_file()
    assert config.model_version == "spec-02-03-resnet34-unet-512-v1"


def test_release_manifest_builds(tmp_path):
    output = tmp_path / "release_manifest.json"
    result = subprocess.run([sys.executable, "scripts/deployment/build_release_manifest.py", "--output", str(output)],
                            cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=600)
    manifest = json.loads(output.read_text(encoding="utf-8"))
    assert set(manifest["versions"]) >= {"service", "api", "model", "database_schema", "record_schema"}
    assert all(re.fullmatch(r"[0-9a-f]{64}", digest) for digest in manifest["configs"].values())
    assert manifest["limitations"] and set(manifest["commands"]) >= {"install", "serve", "smoke_test"}
    # exit code 1 only means the gitignored checkpoint or an evidence file is absent on this machine
    assert result.returncode in (0, 1), result.stderr


def test_health_separates_service_from_model(tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from src.api.app import ApiSettings, create_app

    settings = ApiSettings(data_dir=tmp_path, load_model=False)
    with TestClient(create_app(settings)) as client:
        assert client.get("/health/live").status_code == 200
        ready = client.get("/health/ready")
        assert ready.status_code == 503
        assert ready.json()["model"] == "NOT_READY" and ready.json()["database"] == "READY"


def _user_facing_sentences():
    from src.api.app import LIMITATIONS
    from src.longitudinal.comparison import TECHNICAL_LABEL
    from src.longitudinal.trends import TREND_LABEL

    texts = {"LIMITATIONS": " ".join(LIMITATIONS), "comparison": TECHNICAL_LABEL, "trend": TREND_LABEL}
    html = (PROJECT_ROOT / "src/dashboard/index.html").read_text(encoding="utf-8")
    texts["dashboard"] = re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", html, flags=re.S)
    release = PROJECT_ROOT / "docs/release/RELEASE.md"
    if release.is_file():
        # unwrap hard-wrapped markdown (and "> " quote markers) so each sentence is scanned whole
        lines = [line.lstrip("> ").rstrip() for line in release.read_text(encoding="utf-8").splitlines()]
        texts["RELEASE.md"] = " ".join(line if line else "\n" for line in lines)
    for source, text in texts.items():
        for sentence in re.split(r"(?<=[.!?])\s+|\n|\|", text):
            yield source, sentence


def test_no_unqualified_clinical_claims():
    offending = [(source, s.strip()) for source, s in _user_facing_sentences()
                 if CLINICAL.search(s) and not NEGATION.search(s) and "/health" not in s]
    assert not offending, offending
