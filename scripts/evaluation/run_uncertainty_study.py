"""REQ-P09-S02-003: does flip-TTA disagreement track segmentation error on internal validation?

Runs the frozen engine on the FUSeg2021 ``internal_val`` split only (the held-out test split is never loaded, so it
plays no part in choosing a signal), pairs each image's ``tta_disagreement`` with its Dice, and decides whether the
summary value may be shown to users.

Decision rule, fixed before the run: show the summary only if the Spearman correlation between disagreement and Dice
is at most -0.3 and the upper end of its 95% bootstrap interval is below zero. Otherwise the heatmap stays and the
number is hidden.

    python scripts/evaluation/run_uncertainty_study.py [--limit N]
        -> reports/final/p09_s02_uncertainty.json

After a run, set ``summary_shown`` in configs/inference/uncertainty_v1.json to the report's ``decision.show_summary``.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.inference.engine import DEFAULT_INFERENCE_CONFIG, InferenceEngine, InferenceRequest  # noqa: E402
from src.segmentation.dataset import load_manifest_samples  # noqa: E402
from src.segmentation.inference import load_binary_mask  # noqa: E402

MANIFEST = ROOT / "data" / "manifests" / "fuseg2021_heldout_manifest.json"
MAX_RHO, BOOTSTRAP, SEED = -0.3, 2000, 20261105
POOR_DICE = 0.5


def dice(prediction: np.ndarray, truth: np.ndarray) -> float:
    total = int(prediction.sum() + truth.sum())
    return 1.0 if total == 0 else 2.0 * int(np.logical_and(prediction, truth).sum()) / total


def bootstrap_rho(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    rng = np.random.default_rng(SEED)
    values = []
    for _ in range(BOOTSTRAP):
        index = rng.integers(0, len(x), len(x))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", stats.ConstantInputWarning)   # a resample of one value; skipped below
            rho = stats.spearmanr(x[index], y[index]).statistic
        if np.isfinite(rho):
            values.append(rho)
    return float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))


def auroc(scores: np.ndarray, positives: np.ndarray) -> float | None:
    if positives.all() or not positives.any():
        return None
    ranks = stats.rankdata(scores)
    n_pos, n_neg = int(positives.sum()), int((~positives).sum())
    return float((ranks[positives].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=str(DEFAULT_INFERENCE_CONFIG))
    parser.add_argument("--limit", type=int, default=None, help="first N images only, for a smoke run")
    parser.add_argument("--out", type=Path, default=ROOT / "reports" / "final" / "p09_s02_uncertainty.json")
    args = parser.parse_args(argv)

    samples = load_manifest_samples(str(MANIFEST), "val")
    samples = [s for s in samples if s.get("heldout_role", "internal_val") == "internal_val"][:args.limit]
    engine = InferenceEngine.from_config(args.config)
    rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    for sample in samples:
        image_path = Path(sample["image_path"])
        result = engine.predict(InferenceRequest(image_path))
        truth = load_binary_mask(Path(sample["annotation_path"]),
                                 (result.binary_mask.shape[1], result.binary_mask.shape[0])).astype(bool)
        summary = result.uncertainty or {}
        rows.append({"sample_id": sample["source_sample_id"], "dice": round(dice(result.binary_mask.astype(bool), truth), 6),
                     "tta_disagreement": summary.get("tta_disagreement"), "region": summary.get("region"),
                     "empty_mask": summary.get("empty_mask")})
    elapsed = time.perf_counter() - started

    x = np.array([r["tta_disagreement"] for r in rows], dtype=float)
    y = np.array([r["dice"] for r in rows], dtype=float)
    rho = float(stats.spearmanr(x, y).statistic)
    low, high = bootstrap_rho(x, y)
    show = rho <= MAX_RHO and high < 0
    order = np.argsort(x)
    quartiles = []
    for index, chunk in enumerate(np.array_split(order, 4), start=1):
        quartiles.append({"quartile": index, "images": int(len(chunk)),
                          "disagreement_range": [round(float(x[chunk].min()), 6), round(float(x[chunk].max()), 6)],
                          "mean_dice": round(float(y[chunk].mean()), 4), "median_dice": round(float(np.median(y[chunk])), 4)})
    poor = y < POOR_DICE
    report = {
        "spec": "P09-S02", "requirement": "REQ-P09-S02-003", "created_at": datetime.now(UTC).isoformat(),
        "split": "FUSeg2021 internal_val", "held_out_test_used": False,
        "engine": {key: value for key, value in engine.describe().items() if key in ("model_version", "architecture")},
        "uncertainty_config": engine.uncertainty_config.version,
        "environment": {"python": platform.python_version(), "device": str(engine.device),
                        "seconds": round(elapsed, 1)},
        "images": len(rows), "empty_predictions": int(sum(bool(r["empty_mask"]) for r in rows)),
        "dice": {"mean": round(float(y.mean()), 4), "median": round(float(np.median(y)), 4)},
        "disagreement": {"median": round(float(np.median(x)), 6), "min": round(float(x.min()), 6),
                         "max": round(float(x.max()), 6)},
        "spearman_rho_disagreement_vs_dice": round(rho, 4),
        "spearman_rho_95ci": [round(low, 4), round(high, 4)],
        "auroc_flags_dice_below_0_5": None if (a := auroc(x, poor)) is None else round(a, 4),
        "images_dice_below_0_5": int(poor.sum()),
        "by_disagreement_quartile": quartiles,
        "decision": {"rule": f"show the summary only if rho <= {MAX_RHO} and the 95% CI upper bound < 0",
                     "show_summary": bool(show),
                     "reason": ("disagreement tracks lower Dice on internal validation" if show else
                                "the association with Dice is too weak to show the number; the heatmap stays")},
        "limitations": ["Internal validation comes from the same source as training; on other cameras or clinics the "
                        "signal may not track error.", "Flip views share one model, so this is weak evidence of "
                        "uncertainty, not a probability that a result is correct."],
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("images", "dice", "spearman_rho_disagreement_vs_dice",
                                             "spearman_rho_95ci", "auroc_flags_dice_below_0_5", "decision")}, indent=2))
    print(f"mean seconds per image: {elapsed / max(1, len(rows)):.2f}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
