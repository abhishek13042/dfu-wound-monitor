"""P09-S04: test the annotation-protocol hypothesis, as fixed in reports/experiments/p09_s04_protocol.md.

No model is trained or tuned: the frozen v1.0.0 model and threshold predict
each accepted P06 external image again, and the labelled-but-missed region is
compared with what the model did find and with the skin just outside the label.

    python scripts/evaluation/run_annotation_hypothesis.py

Output: reports/final/p09_s04_annotation_hypothesis.json (numbers only; no image content).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.inference.engine import DEFAULT_INFERENCE_CONFIG, InferenceEngine, InferenceRequest  # noqa: E402

VALIDATION = PROJECT_ROOT / "reports/final/p06_validation_lowerlimb_external.json"
EXTERNAL = PROJECT_ROOT / "data/manifests/lowerlimb_v3_external_manifest.json"
FUSEG = PROJECT_ROOT / "data/manifests/fuseg2021_heldout_manifest.json"
OUTPUT = PROJECT_ROOT / "reports/final/p09_s04_annotation_hypothesis.json"
PROTOCOL = "reports/experiments/p09_s04_protocol.md"

# Fixed by the protocol; do not change after the first run.
MIN_REGION_PX = 50
RING_INNER_PX, RING_OUTER_PX = 5, 15
T1_SKIN_LIKE_SHARE = 0.60
T2_SOLIDITY_MARGIN = 0.05


def _summary(values):
    values = [v for v in values if v is not None]
    if not values:
        return {"n": 0}
    return {"n": len(values), "mean": round(statistics.fmean(values), 4), "median": round(statistics.median(values), 4),
            "p25": round(float(np.percentile(values, 25)), 4), "p75": round(float(np.percentile(values, 75)), 4)}


def load_mask(path: Path, size: tuple[int, int]) -> np.ndarray:
    mask = Image.open(path).convert("L")
    if mask.size != size:
        mask = mask.resize(size, Image.Resampling.NEAREST)
    return np.asarray(mask) >= 128


def solidity(mask: np.ndarray) -> float | None:
    """Contour area over convex-hull area for the largest connected part of the label."""

    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return None
    largest = max(contours, key=cv2.contourArea)
    hull = cv2.contourArea(cv2.convexHull(largest))
    return round(cv2.contourArea(largest) / hull, 4) if hull > 0 else None


def ring(mask: np.ndarray) -> np.ndarray:
    def grow(radius):
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1))
        return cv2.dilate(mask.astype(np.uint8), kernel).astype(bool)

    return grow(RING_OUTER_PX) & ~grow(RING_INNER_PX)


def colour_test(rgb: np.ndarray, gt: np.ndarray, pred: np.ndarray) -> dict | None:
    """T1 for one image: is the missed region closer in colour to the skin ring or to the hit region?"""

    hit, missed, skin = gt & pred, gt & ~pred, ring(gt)
    if min(hit.sum(), missed.sum(), skin.sum()) < MIN_REGION_PX:
        return None
    lab = cv2.cvtColor(rgb.astype(np.float32) / 255.0, cv2.COLOR_RGB2LAB)
    mean = {name: lab[region].mean(axis=0) for name, region in (("hit", hit), ("missed", missed), ("ring", skin))}
    to_ring = float(np.linalg.norm(mean["missed"] - mean["ring"]))
    to_hit = float(np.linalg.norm(mean["missed"] - mean["hit"]))
    return {"delta_e_missed_to_ring": round(to_ring, 2), "delta_e_missed_to_hit": round(to_hit, 2),
            "skin_like": to_ring < to_hit}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--limit", type=int, help="first N images per stratum (smoke runs only)")
    args = parser.parse_args(argv)

    manifest = {s["source_sample_id"]: s for s in json.loads(EXTERNAL.read_text(encoding="utf-8"))["samples"]}
    validation = json.loads(VALIDATION.read_text(encoding="utf-8"))

    def form(sample):
        return "native_331" if (sample["mask_width"], sample["mask_height"]) == (sample["width"], sample["height"]) \
            else "resized_224"

    strata: dict[str, list[dict]] = {"native_331": [], "resized_224": []}
    for row in validation["per_sample"]:
        if row["status"] == "COMPLETED":
            strata[form(manifest[row["sample_id"]])].append(row)

    engine = InferenceEngine.from_config()
    per_sample, report_strata = [], {}
    for name, rows in strata.items():
        rows = rows[: args.limit] if args.limit else rows
        tests, solid, share, missed_probability = [], [], [], []
        for row in rows:
            sample = manifest[row["sample_id"]]
            result = engine.predict(InferenceRequest(image=PROJECT_ROOT / sample["image_path"]))
            prob, pred = result.probability_mask, result.binary_mask.astype(bool)
            size = (prob.shape[1], prob.shape[0])
            gt = load_mask(PROJECT_ROOT / sample["annotation_path"], size)
            rgb = np.asarray(Image.open(PROJECT_ROOT / sample["image_path"]).convert("RGB").resize(size))
            missed = gt & ~pred
            entry = {"sample_id": row["sample_id"], "stratum": name, "p06_dice": row["metrics"]["dice"],
                     "label_solidity": solidity(gt), "label_area_share": round(float(gt.mean()), 4),
                     "mean_probability_in_missed": round(float(prob[missed].mean()), 4) if missed.any() else None,
                     "colour": colour_test(rgb, gt, pred)}
            per_sample.append(entry)
            solid.append(entry["label_solidity"])
            share.append(entry["label_area_share"])
            missed_probability.append(entry["mean_probability_in_missed"])
            if entry["colour"] is not None:
                tests.append(entry["colour"]["skin_like"])
            print(f"{name} {row['sample_id']}: solidity {entry['label_solidity']}, colour {entry['colour']}", flush=True)
        report_strata[name] = {
            "n": len(rows),
            "t1_eligible": len(tests),
            "t1_skin_like_share": round(sum(tests) / len(tests), 4) if tests else None,
            "label_solidity": _summary(solid),
            "label_area_share": _summary(share),
            "mean_probability_in_missed": _summary(missed_probability),
        }

    fuseg_solidity, fuseg_share = [], []
    for sample in json.loads(FUSEG.read_text(encoding="utf-8"))["samples"]:
        if sample["split"] != "test":
            continue
        gt = load_mask(PROJECT_ROOT / sample["annotation_path"], (sample["width"], sample["height"]))
        if gt.any():
            fuseg_solidity.append(solidity(gt))
            fuseg_share.append(round(float(gt.mean()), 4))
    fuseg = {"n_nonempty": len(fuseg_solidity), "label_solidity": _summary(fuseg_solidity),
             "label_area_share": _summary(fuseg_share)}

    native = report_strata["native_331"]
    t1 = native["t1_skin_like_share"] is not None and native["t1_skin_like_share"] >= T1_SKIN_LIKE_SHARE
    margin = native["label_solidity"].get("median", 0) - fuseg["label_solidity"].get("median", 0)
    t2 = margin >= T2_SOLIDITY_MARGIN
    outcome = {2: "H1 supported", 1: "H1 partly supported", 0: "H1 not supported; H0 stays the working explanation"}

    report = {
        "report": "P09-S04 annotation-protocol hypothesis",
        "protocol": PROTOCOL,
        "model_config": Path(DEFAULT_INFERENCE_CONFIG).resolve().relative_to(PROJECT_ROOT).as_posix(),
        "threshold": engine.config.threshold,
        "rules": {"min_region_px": MIN_REGION_PX, "ring_px": [RING_INNER_PX, RING_OUTER_PX],
                  "t1_skin_like_share": T1_SKIN_LIKE_SHARE, "t2_solidity_margin": T2_SOLIDITY_MARGIN},
        "complete_run": args.limit is None,
        "strata": report_strata,
        "fuseg2021_test": fuseg,
        "tests": {
            "T1_colour": {"supports_h1": t1, "native_331_skin_like_share": native["t1_skin_like_share"],
                          "eligible": native["t1_eligible"]},
            "T2_shape": {"supports_h1": t2, "native_331_median_solidity": native["label_solidity"].get("median"),
                         "fuseg2021_median_solidity": fuseg["label_solidity"].get("median"),
                         "difference": round(margin, 4)},
        },
        "outcome": outcome[int(t1) + int(t2)],
        "per_sample": per_sample,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("tests", "outcome")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
