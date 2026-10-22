"""P06-S01 follow-up: is the LowerLimb drop a model failure or an annotation-protocol difference?

LowerLimb V3 ships masks in two forms: 224x224 masks (nearest-resized to the
331x331 image) and native 331x331 masks.  This script splits the external
validation results by that mask form and, for a few images per group, measures
the model's probability inside the labelled-but-unpredicted region.  Low
probability there means the model sees no wound where the label says there is one.
A threshold just below the frozen value would then not recover the region.

Outputs
    reports/final/p06_lowerlimb_annotation_check.json        (committed)
    reports/figures/p06/local/lowerlimb_mask_styles.png      (gitignored: contains dataset images)
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.inference.engine import InferenceEngine, InferenceRequest  # noqa: E402

VALIDATION = PROJECT_ROOT / "reports/final/p06_validation_lowerlimb_external.json"
MANIFEST = PROJECT_ROOT / "data/manifests/lowerlimb_v3_external_manifest.json"
OUTPUT = PROJECT_ROOT / "reports/final/p06_lowerlimb_annotation_check.json"
FIGURE = PROJECT_ROOT / "reports/figures/p06/local/lowerlimb_mask_styles.png"
TILE = 220


def _summary(values):
    values = list(values)
    if not values:
        return {"n": 0}
    return {"n": len(values), "mean": round(statistics.fmean(values), 4), "median": round(statistics.median(values), 4)}


def _gt(path: Path, size) -> np.ndarray:
    mask = Image.open(path).convert("L")
    if mask.size != size:
        mask = mask.resize(size, Image.Resampling.NEAREST)
    return np.asarray(mask) >= 128


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--per-group", type=int, default=6, help="images per mask form for the probability check")
    args = parser.parse_args(argv)

    manifest = {s["source_sample_id"]: s for s in json.loads(MANIFEST.read_text(encoding="utf-8"))["samples"]}
    validation = json.loads(VALIDATION.read_text(encoding="utf-8"))
    completed = [x for x in validation["per_sample"] if x["status"] == "COMPLETED"]

    def form(sample_id):
        s = manifest[sample_id]
        return "native_331" if (s["mask_width"], s["mask_height"]) == (s["width"], s["height"]) else "resized_224"

    groups = {"native_331": [], "resized_224": []}
    for x in completed:
        groups[form(x["sample_id"])].append(x)

    engine = InferenceEngine.from_config()
    threshold = engine.config.threshold
    report = {"report": "P06 LowerLimb annotation-form check", "validation_source": VALIDATION.relative_to(PROJECT_ROOT).as_posix(),
              "mask_forms_in_full_dataset": {"native_331": sum(1 for s in manifest.values() if form(s["source_sample_id"]) == "native_331"),
                                             "resized_224": sum(1 for s in manifest.values() if form(s["source_sample_id"]) == "resized_224")},
              "groups": {}}
    tiles = []
    for name, rows in groups.items():
        dice = [x["metrics"]["dice"] for x in rows]
        precision = [x["metrics"]["precision"] for x in rows if x["pred"]["area_px"] > 0]
        recall = [x["metrics"]["recall"] for x in rows]
        gt_fraction = [x["gt"]["area_px"] / (manifest[x["sample_id"]]["width"] * manifest[x["sample_id"]]["height"]) for x in rows]
        step = max(1, len(rows) // args.per_group)
        probes = []
        for x in rows[::step][: args.per_group]:
            sample = manifest[x["sample_id"]]
            result = engine.predict(InferenceRequest(image=PROJECT_ROOT / sample["image_path"]))
            prob, pred = result.probability_mask, result.binary_mask.astype(bool)
            gt = _gt(PROJECT_ROOT / sample["annotation_path"], (prob.shape[1], prob.shape[0]))
            missed = gt & ~pred
            probes.append({"sample_id": x["sample_id"], "dice": x["metrics"]["dice"],
                           "missed_px": int(missed.sum()),
                           "mean_probability_in_missed_region": round(float(prob[missed].mean()), 4) if missed.any() else None,
                           "share_of_missed_above_0.2": round(float((prob[missed] > 0.2).mean()), 4) if missed.any() else None})
            image = Image.open(PROJECT_ROOT / sample["image_path"]).convert("RGB").resize((TILE, TILE))
            def overlay(mask, colour):
                layer = Image.fromarray((mask * 255).astype(np.uint8)).resize((TILE, TILE), Image.Resampling.NEAREST)
                return Image.composite(Image.blend(image, Image.new("RGB", image.size, colour), 0.5), image, layer)
            tiles.append((image, overlay(gt, (255, 0, 0)), overlay(pred, (0, 160, 255))))
        report["groups"][name] = {"n": len(rows), "dice": _summary(dice), "precision_nonempty_pred": _summary(precision),
                                  "recall": _summary(recall), "gt_area_fraction": _summary(gt_fraction),
                                  "probability_probe": probes}
    report["threshold"] = threshold

    OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    sheet = Image.new("RGB", (TILE * 3, TILE * len(tiles)), "white")
    for row, images in enumerate(tiles):
        for col, tile in enumerate(images):
            sheet.paste(tile, (col * TILE, row * TILE))
    sheet.save(FIGURE)
    print(json.dumps({k: {kk: v[kk] for kk in ("n", "dice", "recall", "gt_area_fraction")} for k, v in report["groups"].items()}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
