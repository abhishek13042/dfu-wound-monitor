"""Container / Hugging Face Space packaging: checkpoint fetch is hash-gated, Space layout is complete."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.deployment import build_hf_space, fetch_checkpoint

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _config_with_checkpoint(tmp_path: Path, payload: bytes) -> Path:
    config = json.loads((PROJECT_ROOT / "configs/inference/spec_02_03_inference.json").read_text(encoding="utf-8"))
    config["model"]["checkpoint_path"] = str(tmp_path / "placed" / "model.pth")
    config["model"]["checkpoint_sha256"] = hashlib.sha256(payload).hexdigest()
    config["model"]["training_config_path"] = str(PROJECT_ROOT / config["model"]["training_config_path"])
    path = tmp_path / "inference.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def test_fetch_installs_only_a_matching_checkpoint(tmp_path, monkeypatch):
    monkeypatch.delenv("DFU_CHECKPOINT_REPO", raising=False)
    config = _config_with_checkpoint(tmp_path, b"good weights")
    good, bad = tmp_path / "good.pth", tmp_path / "bad.pth"
    good.write_bytes(b"good weights")
    bad.write_bytes(b"tampered weights")
    placed = tmp_path / "placed" / "model.pth"

    assert fetch_checkpoint.main(["--config", str(config)]) == 1          # nothing to fetch from
    assert fetch_checkpoint.main(["--config", str(config), "--source", str(bad)]) == 2
    assert not placed.exists()
    assert fetch_checkpoint.main(["--config", str(config), "--source", str(good)]) == 0
    assert placed.read_bytes() == b"good weights"
    assert fetch_checkpoint.main(["--config", str(config)]) == 0          # already present and verified


def test_space_bundle_has_docker_front_matter_and_runtime_files(tmp_path):
    output = build_hf_space.build(tmp_path / "space")
    readme = (output / "README.md").read_text(encoding="utf-8")
    front_matter = readme.split("---")[1]
    assert "sdk: docker" in front_matter and "app_port: 7860" in front_matter
    for required in ["Dockerfile", "requirements.txt", "docker/production/entrypoint.sh",
                     "configs/inference/spec_02_03_inference.json", "configs/training/segmentation_resnet34_unet_512.json",
                     "src/api/app.py", "src/dashboard/index.html", "scripts/deployment/fetch_checkpoint.py"]:
        assert (output / required).is_file(), required
    assert b"\r\n" not in (output / "docker/production/entrypoint.sh").read_bytes()
    assert not list(output.rglob("*.pth")) and not list(output.rglob("__pycache__"))
    dockerfile = (output / "Dockerfile").read_text(encoding="utf-8")
    for line in dockerfile.splitlines():
        if line.startswith("COPY "):
            source = line.split()[-2]
            assert (output / source).exists(), f"Dockerfile copies missing path {source}"
