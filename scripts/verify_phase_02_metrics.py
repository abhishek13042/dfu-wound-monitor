"""Independent Phase 02 segmentation-metric verification.

This routine intentionally does not import ``src.segmentation.metrics``. It
reads saved per-sample prediction artifacts and computes the confusion counts
and metrics directly from NumPy arrays. It can then compare those values with
the evaluator JSON produced by the Phase 02 evaluation script.

Usage::

    python scripts/verify_phase_02_metrics.py \
        --predictions-dir outputs/predictions/P02-baseline-unet-bce-dice-v1-real \
        --evaluation-results reports/evaluation/P02-baseline-unet-bce-dice-v1-real_test_results.json \
        --output reports/evaluation/P02-baseline-unet-bce-dice-v1-real_independent_metric_verification.json
"""

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


def independently_compute_metrics(
    prediction_mask: np.ndarray,
    ground_truth_mask: np.ndarray,
    epsilon: float = 1e-7,
) -> Dict[str, Any]:
    """Compute segmentation metrics directly from two binary arrays.

    The formulas are deliberately written out here rather than delegated to
    the production evaluator. Empty-set behavior matches the Phase 02 metric
    specification: empty-empty overlap metrics are 1.0, while undefined
    precision/recall denominators use the documented vacuous-truth convention.
    """
    prediction = np.asarray(prediction_mask).astype(bool)
    ground_truth = np.asarray(ground_truth_mask).astype(bool)
    if prediction.shape != ground_truth.shape:
        raise ValueError(
            f"Prediction/ground-truth shape mismatch: {prediction.shape} vs "
            f"{ground_truth.shape}"
        )

    true_positives = int(np.count_nonzero(prediction & ground_truth))
    false_positives = int(np.count_nonzero(prediction & ~ground_truth))
    false_negatives = int(np.count_nonzero(~prediction & ground_truth))

    dice_denominator = 2 * true_positives + false_positives + false_negatives
    union_denominator = true_positives + false_positives + false_negatives
    precision_denominator = true_positives + false_positives
    recall_denominator = true_positives + false_negatives

    dice = (
        1.0
        if dice_denominator < epsilon
        else (2.0 * true_positives) / dice_denominator
    )
    iou = 1.0 if union_denominator < epsilon else true_positives / union_denominator
    precision = (
        1.0
        if precision_denominator < epsilon
        else true_positives / precision_denominator
    )
    recall = 1.0 if recall_denominator < epsilon else true_positives / recall_denominator

    return {
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "dice": float(dice),
        "iou": float(iou),
        "precision": float(precision),
        "recall": float(recall),
    }


def _close(left: float, right: float, tolerance: float = 1e-6) -> bool:
    """Return whether two metric values agree within floating-point tolerance."""
    return math.isclose(left, right, rel_tol=tolerance, abs_tol=tolerance)


def verify_saved_predictions(
    predictions_dir: str,
    evaluation_results_path: Optional[str] = None,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Verify saved prediction artifacts and optionally compare evaluator output."""
    prediction_files = sorted(Path(predictions_dir).glob("*.npz"))
    if not prediction_files:
        raise FileNotFoundError(
            f"No .npz prediction artifacts found in '{predictions_dir}'. "
            "Run real-data evaluation first; synthetic demo artifacts are not a "
            "valid Phase 02 result."
        )

    evaluator_results: Dict[str, Dict[str, Any]] = {}
    if evaluation_results_path is not None:
        with Path(evaluation_results_path).open("r", encoding="utf-8") as results_handle:
            results_document = json.load(results_handle)
        evaluator_results = {
            result["sample_id"]: result
            for result in results_document.get("per_sample_results", [])
        }

    sample_results: List[Dict[str, Any]] = []
    all_match = True
    for prediction_file in prediction_files:
        with np.load(prediction_file) as artifact:
            sample_id = str(np.asarray(artifact["sample_id"]).item())
            prediction_mask = artifact["prediction_binary"]
            ground_truth_mask = artifact["ground_truth_mask"]

        independent_metrics = independently_compute_metrics(prediction_mask, ground_truth_mask)
        evaluator_sample = evaluator_results.get(sample_id)
        comparison: Dict[str, Any] = {"evaluator_result_present": evaluator_sample is not None}

        if evaluator_sample is not None:
            compared_fields = [
                "true_positives",
                "false_positives",
                "false_negatives",
                "dice",
                "iou",
                "precision",
                "recall",
            ]
            field_matches = {}
            for field in compared_fields:
                independent_value = independent_metrics[field]
                evaluator_value = evaluator_sample.get(field)
                if field in {"dice", "iou", "precision", "recall"}:
                    field_matches[field] = evaluator_value is not None and _close(
                        float(independent_value), float(evaluator_value)
                    )
                else:
                    field_matches[field] = independent_value == evaluator_value
            comparison["field_matches"] = field_matches
            comparison["matches_evaluator"] = all(field_matches.values())
            all_match = all_match and comparison["matches_evaluator"]
        else:
            comparison["matches_evaluator"] = None

        sample_results.append(
            {
                "sample_id": sample_id,
                "artifact_path": str(prediction_file),
                "independent_metrics": independent_metrics,
                "comparison": comparison,
            }
        )

    metric_names = ["dice", "iou", "precision", "recall"]
    aggregate_results = {
        f"mean_{metric_name}": float(
            np.mean(
                [
                    sample["independent_metrics"][metric_name]
                    for sample in sample_results
                ]
            )
        )
        for metric_name in metric_names
    }
    verification_status = "PASS" if all_match else "FAIL"
    report = {
        "verification_status": verification_status,
        "routine": "scripts/verify_phase_02_metrics.py",
        "production_metric_module_used": False,
        "predictions_dir": str(predictions_dir),
        "evaluation_results_path": evaluation_results_path,
        "sample_count": len(sample_results),
        "aggregate_results": aggregate_results,
        "sample_results": sample_results,
        "formulae": {
            "dice": "2*TP / (2*TP + FP + FN)",
            "iou": "TP / (TP + FP + FN)",
            "precision": "TP / (TP + FP)",
            "recall": "TP / (TP + FN)",
        },
        "notes": "Independent values are computed from saved binary predictions and ground-truth masks.",
    }

    if output_path is not None:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with output_file.open("w", encoding="utf-8") as report_handle:
            json.dump(report, report_handle, indent=2)

    if verification_status != "PASS":
        raise RuntimeError("Independent metric verification FAILED; evaluator values do not agree.")

    return report


def main() -> None:
    """Parse command-line arguments and run the independent verification."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions-dir", required=True)
    parser.add_argument("--evaluation-results", default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    report = verify_saved_predictions(
        predictions_dir=args.predictions_dir,
        evaluation_results_path=args.evaluation_results,
        output_path=args.output,
    )
    print(
        f"Independent metric verification: {report['verification_status']} "
        f"({report['sample_count']} samples)"
    )


if __name__ == "__main__":
    main()
