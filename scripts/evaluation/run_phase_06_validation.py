"""P06-S01 end-to-end validation of the full analysis workflow.

Every sample of a manifest split is pushed through the production path
(``AnalysisPipeline``: decode -> quality gate -> segmentation -> measurement)
and compared with its ground-truth mask:

* segmentation: Dice, IoU, precision, recall, recomputed here with plain
  numpy (independent of ``src.segmentation.metrics``);
* measurement: the same measurement engine applied to the ground-truth mask
  gives reference area / perimeter / Feret values, so the reported error is
  the error a user would see, in pixels;
* quality gate: acceptance rate and reason codes on curated data;
* repeatability: the first ``--repeat`` samples are analysed twice and their
  mask hashes compared (REQ-P06-S02-001).

Each sample is assigned one observed failure category by fixed rules
(``CATEGORY_RULES``).  Hypotheses about causes are *not* produced by this
script; they live, labelled as such, in the written report.

Example::

    python scripts/evaluation/run_phase_06_validation.py --split test
    python scripts/evaluation/run_phase_06_validation.py \
        --manifest data/manifests/lowerlimb_v3_external_manifest.json --split external_test \
        --limit 150 --tag lowerlimb_external
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.inference.engine import DEFAULT_INFERENCE_CONFIG, InferenceEngine, sha256_file  # noqa: E402
from src.inference.pipeline import COMPLETED, AnalysisPipeline  # noqa: E402
from src.measurement.engine import measure  # noqa: E402

GOOD_DICE = 0.80
LOW_DICE = 0.50
CATEGORY_RULES = {
    "QUALITY_REJECTED": "the quality gate rejected the image; no segmentation was produced",
    "CORRECT_EMPTY": "ground truth empty and prediction empty",
    "FALSE_POSITIVE_ON_EMPTY": "ground truth empty but the model segmented a region",
    "MISSED_WOUND": "ground truth non-empty but the prediction is empty",
    "LOW_OVERLAP": f"both non-empty and Dice < {LOW_DICE}",
    "UNDER_SEGMENTATION": f"{LOW_DICE} <= Dice < {GOOD_DICE} and predicted area < ground-truth area",
    "OVER_SEGMENTATION": f"{LOW_DICE} <= Dice < {GOOD_DICE} and predicted area >= ground-truth area",
    "GOOD": f"Dice >= {GOOD_DICE}",
}
FLAG_RULES = {
    "SMALL_WOUND": "ground-truth area < 0.5% of the image",
    "FRAGMENTED_PREDICTION": "more predicted components than ground-truth components",
    "TOUCHES_BORDER": "predicted region touches the image border",
}


def overlap(pred: np.ndarray, gt: np.ndarray) -> Dict[str, Optional[float]]:
    p, g = pred.astype(bool), gt.astype(bool)
    tp, fp, fn = int((p & g).sum()), int((p & ~g).sum()), int((~p & g).sum())
    if tp + fp + fn == 0:
        return {"dice": 1.0, "iou": 1.0, "precision": None, "recall": None, "tp": 0, "fp": 0, "fn": 0}
    return {"dice": 2 * tp / (2 * tp + fp + fn), "iou": tp / (tp + fp + fn),
            "precision": tp / (tp + fp) if tp + fp else None, "recall": tp / (tp + fn) if tp + fn else None,
            "tp": tp, "fp": fp, "fn": fn}


def load_gt(path: Path, size) -> np.ndarray:
    mask = Image.open(path).convert("L")
    if mask.size != size:  # documented manifest policy: nearest-neighbour to image size
        mask = mask.resize(size, Image.Resampling.NEAREST)
    return (np.asarray(mask) > 127).astype(np.uint8)


def categorise(status: str, metrics: Dict[str, Any], pred_area: int, gt_area: int) -> str:
    if status != COMPLETED:
        return "QUALITY_REJECTED"
    if gt_area == 0:
        return "CORRECT_EMPTY" if pred_area == 0 else "FALSE_POSITIVE_ON_EMPTY"
    if pred_area == 0:
        return "MISSED_WOUND"
    if metrics["dice"] < LOW_DICE:
        return "LOW_OVERLAP"
    if metrics["dice"] < GOOD_DICE:
        return "UNDER_SEGMENTATION" if pred_area < gt_area else "OVER_SEGMENTATION"
    return "GOOD"


def quantiles(values: List[float]) -> Optional[Dict[str, float]]:
    if not values:
        return None
    arr = np.asarray(values, dtype=np.float64)
    return {"n": int(arr.size), "mean": float(arr.mean()), "std": float(arr.std()), "min": float(arr.min()),
            "p10": float(np.percentile(arr, 10)), "p25": float(np.percentile(arr, 25)),
            "median": float(np.median(arr)), "p75": float(np.percentile(arr, 75)),
            "p90": float(np.percentile(arr, 90)), "max": float(arr.max())}


def histogram(values: List[float], edges: List[float]) -> Dict[str, int]:
    counts, _ = np.histogram(np.clip(values, edges[0], edges[-1]), bins=edges)
    return {f"[{lo:g},{hi:g})": int(c) for lo, hi, c in zip(edges[:-1], edges[1:], counts)}


def summarise(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    done = [r for r in rows if r["status"] == COMPLETED]
    nonempty = [r for r in done if r["gt"]["area_px"] > 0]
    both = [r for r in nonempty if r["pred"]["area_px"] > 0]
    tp = sum(r["metrics"]["tp"] for r in done)
    fp = sum(r["metrics"]["fp"] for r in done)
    fn = sum(r["metrics"]["fn"] for r in done)
    categories: Dict[str, int] = {name: 0 for name in CATEGORY_RULES}
    flags: Dict[str, int] = {name: 0 for name in FLAG_RULES}
    reasons: Dict[str, int] = {}
    for r in rows:
        categories[r["category"]] += 1
        for flag in r["flags"]:
            flags[flag] += 1
        for code in r["quality_reasons"]:
            reasons[code] = reasons.get(code, 0) + 1
    rel_area = [r["measurement_error"]["area_rel"] for r in both]
    sizes = sorted(r["gt"]["area_px"] for r in nonempty)
    by_size = {}
    if len(sizes) >= 3:
        cuts = [sizes[len(sizes) // 3], sizes[2 * len(sizes) // 3]]
        for name, lo, hi in (("small", 0, cuts[0]), ("medium", cuts[0], cuts[1]), ("large", cuts[1], float("inf"))):
            group = [r["metrics"]["dice"] for r in nonempty if lo <= r["gt"]["area_px"] < hi]
            by_size[name] = {"gt_area_px_range": [lo, None if hi == float("inf") else hi], **(quantiles(group) or {})}
    return {
        "samples": len(rows),
        "quality": {"accepted": len(done), "rejected": len(rows) - len(done),
                    "acceptance_rate": len(done) / len(rows) if rows else None, "reason_counts": reasons},
        "segmentation_on_accepted": {
            "macro_dice": quantiles([r["metrics"]["dice"] for r in done]),
            "macro_dice_nonempty_gt": quantiles([r["metrics"]["dice"] for r in nonempty]),
            "macro_iou": quantiles([r["metrics"]["iou"] for r in done]),
            "pooled_dice": 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else None,
            "pooled_iou": tp / (tp + fp + fn) if tp + fp + fn else None,
            "dice_histogram": histogram([r["metrics"]["dice"] for r in done],
                                        [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0000001]),
            "dice_by_gt_size_tercile": by_size,
        },
        "measurement_error_where_both_nonempty": {
            "n": len(both),
            "area_relative_error": quantiles(rel_area),
            "area_absolute_relative_error": quantiles([abs(v) for v in rel_area]),
            "area_relative_error_histogram": histogram(rel_area, [-1, -0.5, -0.25, -0.1, 0, 0.1, 0.25, 0.5, 1, 10]),
            "max_feret_relative_error": quantiles([r["measurement_error"]["max_feret_rel"] for r in both]),
            "perimeter_relative_error": quantiles([r["measurement_error"]["perimeter_rel"] for r in both]),
            "area_pearson_r": float(np.corrcoef([r["pred"]["area_px"] for r in both],
                                                [r["gt"]["area_px"] for r in both])[0, 1]) if len(both) > 2 else None,
        },
        "failure_categories": categories,
        "flags": flags,
        "latency_s": quantiles([r["seconds"] for r in rows]),
    }


def reference_check(rows: List[Dict[str, Any]], reference_path: Optional[Path]) -> Optional[Dict[str, Any]]:
    """Compare per-sample Dice against the Phase 02 held-out evaluation (independent code path)."""

    if not reference_path or not reference_path.is_file():
        return None
    ref = {s["sample_id"]: s["dice"] for s in json.loads(reference_path.read_text())["per_sample_metrics"]}
    diffs = [abs(r["metrics"]["dice"] - ref[r["sample_id"]]) for r in rows
             if r["status"] == COMPLETED and r["sample_id"] in ref]
    return {"reference": reference_path.relative_to(PROJECT_ROOT).as_posix(), "compared": len(diffs),
            "max_abs_dice_difference": max(diffs) if diffs else None,
            "samples_differing_by_more_than_0.01": sum(d > 0.01 for d in diffs)}


def plot(rows: List[Dict[str, Any]], out_dir: Path, tag: str) -> List[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir.mkdir(parents=True, exist_ok=True)
    done = [r for r in rows if r["status"] == COMPLETED]
    both = [r for r in done if r["gt"]["area_px"] > 0 and r["pred"]["area_px"] > 0]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    axes[0].hist([r["metrics"]["dice"] for r in done], bins=np.linspace(0, 1, 21), color="#2a6fbb", edgecolor="white")
    axes[0].set(xlabel="Per-image Dice", ylabel="Images", title=f"Dice distribution (n={len(done)})")
    gt = np.array([r["gt"]["area_px"] for r in both], dtype=float)
    pred = np.array([r["pred"]["area_px"] for r in both], dtype=float)
    if len(both):
        axes[1].loglog(gt, pred, "o", ms=4, alpha=0.6, color="#2a6fbb")
        lim = [max(1.0, min(gt.min(), pred.min()) * 0.8), max(gt.max(), pred.max()) * 1.25]
        axes[1].plot(lim, lim, "-", color="#888", lw=1)
    axes[1].set(xlabel="Ground-truth area (px)", ylabel="Predicted area (px)", title="Area agreement (log-log)")
    fig.tight_layout()
    path = out_dir / f"{tag}_dice_and_area.png"
    fig.savefig(path, dpi=120, metadata={"Software": None})
    plt.close(fig)
    return [path.relative_to(PROJECT_ROOT).as_posix()]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", type=Path, default=PROJECT_ROOT / "data/manifests/fuseg2021_heldout_manifest.json")
    parser.add_argument("--split", default="test")
    parser.add_argument("--limit", type=int, default=0, help="evenly subsample to this many samples (0 = all)")
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--config", type=Path, default=DEFAULT_INFERENCE_CONFIG)
    parser.add_argument("--reference", type=Path,
                        default=PROJECT_ROOT / "reports/experiments/spec-02-03/cpu_verification/heldout_test_evaluation.json")
    parser.add_argument("--tag", default="fuseg2021_test")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "reports/final")
    args = parser.parse_args(argv)

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    samples = [s for s in manifest["samples"] if s.get("split") == args.split]
    if args.limit and len(samples) > args.limit:
        idx = np.linspace(0, len(samples) - 1, args.limit).round().astype(int)
        samples = [samples[i] for i in idx]
    if not samples:
        parser.error(f"no samples with split={args.split!r}")

    engine = InferenceEngine.from_config(args.config)
    pipeline = AnalysisPipeline(engine)
    rows: List[Dict[str, Any]] = []
    integrity_failures: List[str] = []
    started = time.perf_counter()
    for i, sample in enumerate(samples, 1):
        image_path = PROJECT_ROOT / sample["image_path"]
        data = image_path.read_bytes()
        if hashlib.sha256(data).hexdigest() != sample["checksum_sha256"]:
            integrity_failures.append(sample["source_sample_id"])
            continue
        t0 = time.perf_counter()
        outcome = pipeline.analyze(data, request_id=f"p06-{sample['source_sample_id']}")
        seconds = time.perf_counter() - t0
        gt = load_gt(PROJECT_ROOT / sample["annotation_path"], (outcome.decoded.width, outcome.decoded.height))
        gt_m = measure(gt).pixel
        row: Dict[str, Any] = {
            "sample_id": sample["source_sample_id"], "status": outcome.status, "seconds": round(seconds, 4),
            "quality_reasons": outcome.quality.reason_codes,
            "gt": {"area_px": gt_m["area_px"], "components": gt_m["component_count"]},
            "metrics": {"dice": None, "iou": None, "tp": 0, "fp": 0, "fn": 0}, "flags": [],
        }
        pred_area = 0
        if outcome.status == COMPLETED:
            p = outcome.measurement.pixel
            pred_area = p["area_px"]
            row["pred"] = {"area_px": p["area_px"], "components": p["component_count"],
                           "mask_sha256": hashlib.sha256(outcome.inference.binary_mask.tobytes()).hexdigest()}
            row["metrics"] = {k: (round(v, 6) if isinstance(v, float) else v)
                              for k, v in overlap(outcome.inference.binary_mask, gt).items()}
            if gt_m["area_px"] and pred_area:
                rel = lambda a, b: round((a - b) / b, 6) if b else None  # noqa: E731
                row["measurement_error"] = {"area_rel": rel(p["area_px"], gt_m["area_px"]),
                                            "perimeter_rel": rel(p["perimeter_px"], gt_m["perimeter_px"]),
                                            "max_feret_rel": rel(p["max_feret_px"], gt_m["max_feret_px"])}
            if gt_m["area_px"] and p["component_count"] > gt_m["component_count"]:
                row["flags"].append("FRAGMENTED_PREDICTION")
            if "TOUCHES_IMAGE_BORDER" in {w["code"] for w in outcome.measurement.warnings}:
                row["flags"].append("TOUCHES_BORDER")
        else:
            row["pred"] = {"area_px": 0, "components": 0, "mask_sha256": None}
        if 0 < gt_m["area_px"] < 0.005 * gt.size:
            row["flags"].append("SMALL_WOUND")
        row["category"] = categorise(outcome.status, row["metrics"], pred_area, gt_m["area_px"])
        rows.append(row)
        if i % 20 == 0 or i == len(samples):
            print(f"[{i}/{len(samples)}] {time.perf_counter() - started:.0f}s", flush=True)

    repeat = []
    for row, sample in zip(rows[: args.repeat], samples[: args.repeat]):
        outcome = pipeline.analyze((PROJECT_ROOT / sample["image_path"]).read_bytes())
        again = (hashlib.sha256(outcome.inference.binary_mask.tobytes()).hexdigest()
                 if outcome.status == COMPLETED else None)
        repeat.append({"sample_id": row["sample_id"], "identical": again == row["pred"]["mask_sha256"]})

    report = {
        "report": "P06-S01 end-to-end validation",
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "command": "python " + " ".join([Path(sys.argv[0]).as_posix()] + (argv if argv is not None else sys.argv[1:])),
        "provenance": {
            "manifest": args.manifest.resolve().relative_to(PROJECT_ROOT).as_posix(),
            "manifest_sha256": sha256_file(args.manifest),
            "manifest_version": manifest.get("manifest_version"),
            "dataset": manifest.get("dataset_name"), "dataset_version": manifest.get("dataset_version"),
            "split": args.split, "split_policy": manifest.get("split_policy"),
            "sample_selection": f"evenly spaced subsample of {len(samples)}" if args.limit else "all samples in split",
            "model": engine.describe(),
            "hardware": {"platform": platform.platform(), "processor": platform.processor(),
                         "python": platform.python_version()},
        },
        "category_rules": CATEGORY_RULES, "flag_rules": FLAG_RULES,
        "integrity": {"checksum_failures": integrity_failures},
        "summary": summarise(rows),
        "phase_02_cross_check": reference_check(rows, args.reference) if args.split == "test" else None,
        "repeatability": {"policy": engine.config.determinism_policy, "checked": len(repeat),
                          "identical": sum(r["identical"] for r in repeat), "samples": repeat},
        "figures": plot(rows, PROJECT_ROOT / "reports/figures/p06", args.tag),
        "per_sample": rows,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out = args.output_dir / f"p06_validation_{args.tag}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    s = report["summary"]
    print(json.dumps({"output": str(out), "quality": s["quality"],
                      "pooled_dice": s["segmentation_on_accepted"]["pooled_dice"],
                      "macro_dice": (s["segmentation_on_accepted"]["macro_dice"] or {}).get("mean"),
                      "categories": s["failure_categories"],
                      "cross_check": report["phase_02_cross_check"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
