"""P07-S06 PyTorch-vs-ONNX parity on the FUSeg2021 held-out test split (REQ-P07-S06-003).

Runs both engines on every held-out test image at the frozen threshold, minimum
component area and flip TTA, and records:

* pooled Dice of each engine against the reference masks, and the difference
  (the gate is |difference| <= 0.001);
* probability-map agreement: max and mean absolute difference per image, and
  how many pixels change side of the threshold.

Example::

    python scripts/evaluation/run_onnx_parity.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.inference.engine import DEFAULT_INFERENCE_CONFIG, InferenceEngine, InferenceRequest  # noqa: E402
from src.inference.onnx_engine import DEFAULT_ONNX_CONFIG, OnnxEngine  # noqa: E402
from src.segmentation.inference import load_binary_mask  # noqa: E402

DICE_TOLERANCE = 0.001


def pooled_dice(counts: np.ndarray) -> float:
    tp, fp, fn = counts
    return float(2 * tp / (2 * tp + fp + fn)) if tp + fp + fn else 1.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", type=Path, default=PROJECT_ROOT / "data/manifests/fuseg2021_heldout_manifest.json")
    parser.add_argument("--config", type=Path, default=DEFAULT_INFERENCE_CONFIG)
    parser.add_argument("--onnx-config", type=Path, default=DEFAULT_ONNX_CONFIG)
    parser.add_argument("--limit", type=int, default=None, help="Score only the first N images (smoke runs)")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "reports/final/p07_s06_onnx_parity.json")
    args = parser.parse_args(argv)

    samples = [s for s in json.loads(args.manifest.read_text())["samples"] if s["split"] == "test"][: args.limit]
    torch_engine = InferenceEngine.from_config(args.config)
    onnx_engine = OnnxEngine.from_config(args.onnx_config)
    threshold = torch_engine.config.threshold

    counts = {"pytorch": np.zeros(3, dtype=np.int64), "onnx": np.zeros(3, dtype=np.int64)}
    max_abs, mean_abs, flipped, mask_differs = [], [], 0, 0
    for sample in samples:
        decoded = torch_engine.decode((PROJECT_ROOT / sample["image_path"]).read_bytes())
        truth = load_binary_mask(PROJECT_ROOT / sample["annotation_path"], (decoded.width, decoded.height)).astype(bool)
        results = {"pytorch": torch_engine.predict(InferenceRequest(decoded)),
                   "onnx": onnx_engine.predict(InferenceRequest(decoded))}
        for name, result in results.items():
            mask = result.binary_mask.astype(bool)
            counts[name] += [np.sum(mask & truth), np.sum(mask & ~truth), np.sum(~mask & truth)]
        a, b = results["pytorch"].probability_mask, results["onnx"].probability_mask
        diff = np.abs(a - b)
        max_abs.append(float(diff.max()))
        mean_abs.append(float(diff.mean()))
        flipped += int(np.sum((a >= threshold) != (b >= threshold)))
        mask_differs += int(not np.array_equal(results["pytorch"].binary_mask, results["onnx"].binary_mask))

    dice = {name: pooled_dice(value) for name, value in counts.items()}
    difference = dice["onnx"] - dice["pytorch"]
    report = {
        "report": "P07-S06 ONNX parity on the FUSeg2021 held-out test split",
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "command": "python scripts/evaluation/run_onnx_parity.py " + " ".join(argv if argv is not None else sys.argv[1:]),
        "images": len(samples),
        "manifest": args.manifest.relative_to(PROJECT_ROOT).as_posix(),
        "pytorch": {"model_version": torch_engine.config.model_version,
                    "checkpoint_sha256": torch_engine.checkpoint_info["checkpoint_sha256"]},
        "onnx": {"model_version": onnx_engine.describe()["model_version"],
                 "model_sha256": onnx_engine.checkpoint_info["checkpoint_sha256"],
                 "opset": onnx_engine.onnx["opset"], "onnxruntime": onnx_engine.checkpoint_info["onnxruntime_version"]},
        "postprocessing": {"threshold": threshold, "min_component_area": torch_engine.config.min_component_area,
                           "tta": torch_engine.config.tta},
        "pooled_dice": {**{k: round(v, 6) for k, v in dice.items()}, "difference": round(difference, 6),
                        "tolerance": DICE_TOLERANCE},
        "probability_agreement": {"max_abs_difference": max(max_abs), "mean_abs_difference": float(np.mean(mean_abs)),
                                  "pixels_changing_side_of_threshold": flipped,
                                  "images_with_any_mask_difference": mask_differs},
        "parity_passed": abs(difference) <= DICE_TOLERANCE,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["parity_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
