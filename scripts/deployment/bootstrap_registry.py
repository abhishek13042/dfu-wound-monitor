"""P10-S04: create ``configs/models/registry.json`` from the models that existed before the registry.

The PyTorch model was already serving when the registry was introduced
(decision 23), so it is recorded ACTIVE with the approval marked as a bootstrap,
not as a review that never happened.  The ONNX export is registered as a
CANDIDATE: it is promoted only through ``promote_model.py``, by a named person,
after its gates pass.

    python scripts/deployment/bootstrap_registry.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.mlops.registry import DEFAULT_REGISTRY, Registry, RegistryError, file_sha256  # noqa: E402

BOOTSTRAP_APPROVAL = "bootstrap: serving before the registry existed (decision 23); not a gate review"
FUSEG = {"dataset": "FUSeg2021", "version": "FUSeg2021-official-source-commit-42a272d",
         "manifest": "data/manifests/fuseg2021_heldout_manifest.json", "use": "training and held-out test"}
LOWER_LIMB = {"dataset": "LowerLimbFeetWoundV3", "version": "lowerlimb-v3-external-v1",
              "manifest": "data/manifests/lowerlimb_v3_external_manifest.json", "use": "external test only"}
LIMITATIONS = [
    "Trained and tuned on FUSeg2021 diabetic foot ulcer photographs only.",
    "External lower-limb wounds: pooled Dice 0.256 (P06), so results outside foot ulcers are unreliable.",
    "Measures pixels unless a reference marker is calibrated; it does not diagnose or stage a wound.",
]


def _report(name: str) -> dict:
    return json.loads((PROJECT_ROOT / "reports/final" / name).read_text(encoding="utf-8"))


def records() -> list[dict]:
    pytorch_config = json.loads((PROJECT_ROOT / "configs/inference/spec_02_03_inference.json").read_text())
    onnx_config = json.loads((PROJECT_ROOT / "configs/inference/spec_02_03_onnx_inference.json").read_text())
    fuseg, external = _report("p06_validation_fuseg2021_test.json"), _report("p06_validation_lowerlimb_external.json")
    parity = _report("p07_s06_onnx_parity.json")
    pytorch_bench, onnx_bench = _report("p07_s06_pytorch_benchmark.json"), _report("p07_s06_onnx_benchmark.json")

    pytorch_path = pytorch_config["model"]["checkpoint_path"]
    onnx_path = onnx_config["onnx"]["model_path"]
    return [
        {"model_version": pytorch_config["model"]["model_version"], "runtime": "pytorch",
         "artifact_path": pytorch_path, "sha256": file_sha256(PROJECT_ROOT / pytorch_path),
         "inference_config": "configs/inference/spec_02_03_inference.json",
         "dataset_refs": [FUSEG, LOWER_LIMB],
         "metrics": {"fuseg2021_test_pooled_dice": round(fuseg["summary"]["segmentation_on_accepted"]["pooled_dice"], 4),
                     "lowerlimb_external_pooled_dice":
                         round(external["summary"]["segmentation_on_accepted"]["pooled_dice"], 4),
                     "p50_total_latency_s": pytorch_bench["latency_s"]["total"]["p50"]},
         "limitations": LIMITATIONS,
         "evidence": {"validation": {"fuseg2021_test": "reports/final/p06_validation_fuseg2021_test.json",
                                     "lowerlimb_external": "reports/final/p06_validation_lowerlimb_external.json"},
                      "benchmark": "reports/final/p07_s06_pytorch_benchmark.json"},
         "status": "CANDIDATE", "approved_by": None},
        {"model_version": onnx_config["onnx"]["model_version"], "runtime": "onnx",
         "artifact_path": onnx_path, "sha256": file_sha256(PROJECT_ROOT / onnx_path),
         "inference_config": "configs/inference/spec_02_03_onnx_inference.json",
         "exported_from": pytorch_config["model"]["model_version"],
         "dataset_refs": [FUSEG],
         "metrics": {"fuseg2021_test_pooled_dice": parity["pooled_dice"]["onnx"],
                     "p50_total_latency_s": onnx_bench["latency_s"]["total"]["p50"]},
         "limitations": LIMITATIONS + ["Not yet scored on the external lower-limb set."],
         "evidence": {"validation": {"fuseg2021_test": "reports/final/p07_s06_onnx_parity.json"},
                      "parity": "reports/final/p07_s06_onnx_parity.json",
                      "benchmark": "reports/final/p07_s06_onnx_benchmark.json"},
         "status": "CANDIDATE", "approved_by": None},
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    args = parser.parse_args(argv)
    if args.registry.exists():
        print(f"Refused: {args.registry} already exists", file=sys.stderr)
        return 2
    registry = Registry(args.registry)
    try:
        pytorch, onnx = records()
        registry.register(pytorch)
        registry.register(onnx)
        active = registry.get(pytorch["model_version"])
        active["status"], active["approved_by"] = "ACTIVE", BOOTSTRAP_APPROVAL
        registry._event("BOOTSTRAP_ACTIVE", active["model_version"], None, BOOTSTRAP_APPROVAL)
    except RegistryError as error:
        print(f"Refused: {error}", file=sys.stderr)
        return 2
    registry.save()
    print(f"Wrote {args.registry}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
