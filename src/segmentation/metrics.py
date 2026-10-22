"""
Segmentation Evaluation Metrics — DFU-WoundMonitor.

Spec: P02-S05 — Baseline Evaluation and Metrics.

This module computes and reports segmentation metrics for the baseline.
All metrics are computed from binary masks (prediction vs ground truth).

METRIC DEFINITIONS (REQ-P02-S05-004):

Confusion Matrix elements (for each pixel):
    TP (True Positive):  Predicted wound, is wound.
    FP (False Positive): Predicted wound, is background.
    TN (True Negative):  Predicted background, is background.
    FN (False Negative): Predicted background, is wound (missed wound).

1. Dice Coefficient (also called F1 score for segmentation):
    Dice = 2 * TP / (2 * TP + FP + FN)
    = 2 * |P ∩ G| / (|P| + |G|)
    Range: [0, 1]. 1.0 = perfect overlap.
    High value: Model predicts wound boundaries accurately.
    Low value: Model misses wound or over-predicts.
    Edge case: If both P and G are empty (no wound), Dice is conventionally set to 1.0.

2. Intersection over Union (IoU, also called Jaccard Index):
    IoU = TP / (TP + FP + FN)
    = |P ∩ G| / |P ∪ G|
    Range: [0, 1]. 1.0 = perfect overlap.
    Relationship: Dice = 2 * IoU / (1 + IoU).
    IoU is stricter than Dice (penalizes false positives and negatives more).
    Edge case: Same as Dice — empty prediction and empty target → 1.0.

3. Precision:
    Precision = TP / (TP + FP)
    "Of all pixels predicted as wound, what fraction actually are?"
    High precision → few false positives (model does not over-segment).
    Low precision → many false positives (model over-segments / spurious predictions).
    Edge case: No positive predictions → Precision = 1.0 (vacuously true).

4. Recall / Sensitivity:
    Recall = TP / (TP + FN)
    "Of all actual wound pixels, what fraction did the model find?"
    High recall → few false negatives (model finds most of the wound).
    Low recall → many missed wound pixels (under-segmentation).
    Edge case: No positive ground truth → Recall = 1.0 (vacuously true).

WHY NOT USE ACCURACY? (REQ-P02-S05-007)
    Accuracy = (TP + TN) / (TP + TN + FP + FN)
    With ~15% wound area (foreground), a model that predicts all pixels as
    background achieves ~85% accuracy — but identifies ZERO wound pixels.
    This is completely misleading. Dice, IoU, Precision, and Recall focus on
    the foreground class and are therefore appropriate for imbalanced segmentation.

AGGREGATION METHOD (REQ-P02-S05-006, REQ-SPEC-02-03-006):
    Primary: macro-average. Each metric is computed per sample, then averaged,
    so each sample counts equally regardless of wound size.
    Reported alongside, under separate keys (never mixed into the macro mean):
      * pooled_*     - TP/FP/FN summed over the dataset first (FUSeg leaderboard style)
      * nonempty_*   - macro mean over images whose ground truth has wound pixels,
                       plus empty_false_positive_rate for the empty images
      * *_hd95       - 95th-percentile boundary distance (pixels); undefined
                       when exactly one of prediction/ground truth is empty

Coding Style: Beginner-Understandable Python
"""

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch


# ============================================================
# PER-SAMPLE METRIC COMPUTATION
# ============================================================

def compute_binary_segmentation_metrics(
    predicted_mask: np.ndarray,
    ground_truth_mask: np.ndarray,
    epsilon: float = 1e-7,
) -> Dict[str, float]:
    """
    Compute Dice, IoU, Precision, and Recall for a single binary mask pair.

    Inputs:
        predicted_mask: Binary numpy array, shape (H, W), values in {0, 1}.
                        This is the thresholded model output.
        ground_truth_mask: Binary numpy array, shape (H, W), values in {0, 1}.
                           This is the ground truth wound mask.
        epsilon: Small value to prevent division by zero.

    Outputs:
        Dictionary with keys: 'dice', 'iou', 'precision', 'recall'.
        All values are floats in [0, 1].

    Assumptions:
        - Both arrays have the same shape.
        - Values are strictly binary {0, 1} (already thresholded).
    """
    if predicted_mask.shape != ground_truth_mask.shape:
        raise ValueError(
            f"Shape mismatch: predicted {predicted_mask.shape} vs "
            f"ground truth {ground_truth_mask.shape}"
        )
    if epsilon <= 0:
        raise ValueError("epsilon must be positive")
    if not np.isfinite(predicted_mask).all() or not np.isfinite(ground_truth_mask).all():
        raise ValueError("Segmentation masks must contain finite values")
    if not set(np.unique(predicted_mask)).issubset({0, 1}) or not set(
        np.unique(ground_truth_mask)
    ).issubset({0, 1}):
        raise ValueError("Segmentation masks must contain only binary values {0, 1}")

    # Flatten to 1D for simple element-wise operations
    predicted_flat = predicted_mask.flatten().astype(np.float32)
    ground_truth_flat = ground_truth_mask.flatten().astype(np.float32)

    # Confusion matrix elements
    # TP: pixels that are 1 in both prediction and ground truth
    true_positives = np.sum(predicted_flat * ground_truth_flat)

    # FP: pixels predicted as 1 but actually 0 in ground truth
    false_positives = np.sum(predicted_flat * (1.0 - ground_truth_flat))

    # FN: pixels predicted as 0 but actually 1 in ground truth
    false_negatives = np.sum((1.0 - predicted_flat) * ground_truth_flat)

    # ---- Dice Coefficient ----
    # Dice = 2*TP / (2*TP + FP + FN)
    dice_numerator = 2.0 * true_positives
    dice_denominator = 2.0 * true_positives + false_positives + false_negatives

    if dice_denominator < epsilon:
        # Edge case: both predicted and ground truth are all zeros (no wound in image)
        # By convention, when both are empty, Dice = 1.0 (perfect agreement on "no wound")
        dice = 1.0
    else:
        dice = dice_numerator / dice_denominator

    # ---- IoU (Intersection over Union / Jaccard Index) ----
    # IoU = TP / (TP + FP + FN)
    iou_numerator = true_positives
    iou_denominator = true_positives + false_positives + false_negatives

    if iou_denominator < epsilon:
        # Same edge case as Dice: both empty → 1.0
        iou = 1.0
    else:
        iou = iou_numerator / iou_denominator

    # ---- Precision ----
    # Precision = TP / (TP + FP)
    precision_denominator = true_positives + false_positives

    if precision_denominator < epsilon:
        # No positive predictions made → precision is undefined
        # Convention: 1.0 (vacuously true — no false alarms if no predictions)
        precision = 1.0
    else:
        precision = true_positives / precision_denominator

    # ---- Recall / Sensitivity ----
    # Recall = TP / (TP + FN)
    recall_denominator = true_positives + false_negatives

    if recall_denominator < epsilon:
        # No positive ground truth → recall is undefined
        # Convention: 1.0 (trivially all wounds found if there are none)
        recall = 1.0
    else:
        recall = true_positives / recall_denominator

    return {
        "dice": float(dice),
        "iou": float(iou),
        "precision": float(precision),
        "recall": float(recall),
        "true_positives": int(true_positives),
        "false_positives": int(false_positives),
        "false_negatives": int(false_negatives),
    }


# ============================================================
# AGGREGATE METRICS
# ============================================================

def aggregate_metrics(
    per_sample_results: List[Dict[str, Any]],
) -> Dict[str, float]:
    """
    Compute macro-average of metrics across all samples.

    Macro-averaging: compute each metric per sample, then mean.
    This treats every sample equally regardless of wound size.

    Inputs:
        per_sample_results: List of dicts, each containing 'dice', 'iou',
                            'precision', 'recall' for one sample.

    Outputs:
        Dictionary with 'mean_dice', 'mean_iou', 'mean_precision', 'mean_recall',
        'std_dice', 'std_iou', 'num_samples'.

    REQ-P02-S05-006: Aggregation method is macro-average (documented here).
    """
    if len(per_sample_results) == 0:
        return {
            "mean_dice": 0.0,
            "mean_iou": 0.0,
            "mean_precision": 0.0,
            "mean_recall": 0.0,
            "std_dice": 0.0,
            "std_iou": 0.0,
            "num_samples": 0,
        }

    dice_scores = [result["dice"] for result in per_sample_results]
    iou_scores = [result["iou"] for result in per_sample_results]
    precision_scores = [result["precision"] for result in per_sample_results]
    recall_scores = [result["recall"] for result in per_sample_results]

    aggregate = {
        "mean_dice": float(np.mean(dice_scores)),
        "mean_iou": float(np.mean(iou_scores)),
        "mean_precision": float(np.mean(precision_scores)),
        "mean_recall": float(np.mean(recall_scores)),
        "std_dice": float(np.std(dice_scores)),
        "std_iou": float(np.std(iou_scores)),
        "num_samples": len(per_sample_results),
        "_aggregation_method": "macro_average (mean of per-sample scores)",
        "_note": "Why not accuracy: ~15% foreground → a background-only predictor gets ~85% accuracy. "
                 "Dice/IoU focus on the foreground class and are appropriate for imbalanced segmentation.",
    }
    # Supplementary aggregates are reported under explicit names so they are
    # never confused with the macro-average primary metric.
    if all(key in result for result in per_sample_results for key in ("true_positives", "false_positives", "false_negatives")):
        aggregate.update(compute_pooled_metrics(per_sample_results))
    if all("wound_area_ratio_ground_truth" in result for result in per_sample_results):
        aggregate.update(compute_nonempty_subset_metrics(per_sample_results))
    hd95_values = [result["hd95"] for result in per_sample_results if result.get("hd95") is not None]
    if hd95_values:
        aggregate["mean_hd95"] = float(np.mean(hd95_values))
        aggregate["median_hd95"] = float(np.median(hd95_values))
        aggregate["hd95_num_samples"] = len(hd95_values)
    return aggregate


def compute_pooled_metrics(per_sample_results: List[Dict[str, Any]]) -> Dict[str, float]:
    """Dataset-level (micro / pooled) Dice and IoU.

    TP, FP and FN are summed over all images before the ratio is taken:

        pooled_dice = 2*ΣTP / (2*ΣTP + ΣFP + ΣFN)

    This is the aggregation used by the FUSeg2021 challenge leaderboard.  It
    weights large wounds more heavily and is unaffected by the empty/empty
    convention, so it complements the macro average instead of replacing it.
    """
    tp = float(sum(result["true_positives"] for result in per_sample_results))
    fp = float(sum(result["false_positives"] for result in per_sample_results))
    fn = float(sum(result["false_negatives"] for result in per_sample_results))
    dice_denominator = 2.0 * tp + fp + fn
    iou_denominator = tp + fp + fn
    return {
        "pooled_dice": float(2.0 * tp / dice_denominator) if dice_denominator > 0 else 1.0,
        "pooled_iou": float(tp / iou_denominator) if iou_denominator > 0 else 1.0,
        "pooled_precision": float(tp / (tp + fp)) if tp + fp > 0 else 1.0,
        "pooled_recall": float(tp / (tp + fn)) if tp + fn > 0 else 1.0,
    }


def compute_nonempty_subset_metrics(per_sample_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Macro metrics on images whose ground truth contains wound pixels.

    Empty/empty images score Dice 1.0 by convention and can inflate the macro
    mean.  Reporting the non-empty subset and the empty-image false-positive
    rate separately makes that effect visible.
    """
    nonempty = [result for result in per_sample_results if result["wound_area_ratio_ground_truth"] > 0]
    empty = [result for result in per_sample_results if result["wound_area_ratio_ground_truth"] == 0]
    metrics: Dict[str, Any] = {
        "nonempty_num_samples": len(nonempty),
        "empty_num_samples": len(empty),
    }
    if nonempty:
        metrics["nonempty_mean_dice"] = float(np.mean([result["dice"] for result in nonempty]))
        metrics["nonempty_mean_iou"] = float(np.mean([result["iou"] for result in nonempty]))
    if empty:
        false_alarms = sum(
            result.get("false_positives", 0) > 0 or result.get("wound_area_ratio_predicted", 0.0) > 0
            for result in empty
        )
        metrics["empty_false_positive_rate"] = float(false_alarms / len(empty))
    return metrics


def compute_hd95(
    predicted_mask: np.ndarray,
    ground_truth_mask: np.ndarray,
    pixel_spacing: float = 1.0,
) -> Optional[float]:
    """95th-percentile symmetric Hausdorff distance between mask boundaries.

    Distances are in pixels multiplied by ``pixel_spacing`` (pass the
    native-resolution spacing to get millimetres once calibration exists).

    Edge cases:
        both masks empty       -> 0.0 (perfect agreement)
        exactly one mask empty -> None (undefined; counted separately)
    """
    from scipy import ndimage

    if predicted_mask.shape != ground_truth_mask.shape:
        raise ValueError("HD95 masks must have the same shape")
    prediction = predicted_mask.astype(bool)
    ground_truth = ground_truth_mask.astype(bool)
    if not prediction.any() and not ground_truth.any():
        return 0.0
    if not prediction.any() or not ground_truth.any():
        return None

    def boundary(mask: np.ndarray) -> np.ndarray:
        return mask & ~ndimage.binary_erosion(mask, border_value=0)

    prediction_boundary = boundary(prediction)
    ground_truth_boundary = boundary(ground_truth)
    distance_to_ground_truth = ndimage.distance_transform_edt(~ground_truth_boundary)
    distance_to_prediction = ndimage.distance_transform_edt(~prediction_boundary)
    distances = np.concatenate([
        distance_to_ground_truth[prediction_boundary],
        distance_to_prediction[ground_truth_boundary],
    ])
    return float(np.percentile(distances, 95) * pixel_spacing)


# ============================================================
# BATCH EVALUATION
# ============================================================

def evaluate_batch(
    predictions_batch: torch.Tensor,
    targets_batch: torch.Tensor,
    sample_ids: List[str],
    prediction_threshold: float = 0.5,
    include_hd95: bool = False,
) -> List[Dict[str, Any]]:
    """
    Evaluate a batch of predictions and targets.

    ``include_hd95`` adds the boundary metric; it is off during training
    epochs because the distance transform is comparatively slow.

    Inputs:
        predictions_batch: Tensor of shape (B, 1, H, W), values in [0, 1].
        targets_batch: Tensor of shape (B, 1, H, W), values in {0.0, 1.0}.
        sample_ids: List of sample identifier strings (length B).
        prediction_threshold: Threshold to convert probabilities to binary mask.

    Outputs:
        List of per-sample result dicts (length B).
    """
    batch_results = []

    batch_size = predictions_batch.shape[0]

    if predictions_batch.shape != targets_batch.shape:
        raise ValueError(
            f"Prediction/target batch shape mismatch: {predictions_batch.shape} vs "
            f"{targets_batch.shape}"
        )
    if predictions_batch.ndim != 4 or predictions_batch.shape[1] != 1:
        raise ValueError("Batch metrics expect tensors with shape (B, 1, H, W)")
    if len(sample_ids) != batch_size:
        raise ValueError(f"Expected {batch_size} sample IDs, got {len(sample_ids)}")
    if not 0.0 <= prediction_threshold <= 1.0:
        raise ValueError("prediction_threshold must be in [0, 1]")
    if not torch.isfinite(predictions_batch).all() or not torch.isfinite(targets_batch).all():
        raise ValueError("Prediction probabilities and targets must be finite")

    for sample_index in range(batch_size):
        # Extract single sample from batch
        # Shape: (1, H, W) → remove batch and channel dims → (H, W)
        prediction_probs = predictions_batch[sample_index, 0].detach().cpu().numpy()
        ground_truth = targets_batch[sample_index, 0].detach().cpu().numpy()

        # Apply threshold to convert probabilities to binary predictions
        predicted_binary = (prediction_probs >= prediction_threshold).astype(np.float32)

        # Compute metrics for this sample
        sample_metrics = compute_binary_segmentation_metrics(
            predicted_mask=predicted_binary,
            ground_truth_mask=ground_truth.astype(np.float32),
        )

        # Record additional metadata
        sample_result = {
            "sample_id": sample_ids[sample_index],
            "prediction_threshold": prediction_threshold,
            "wound_area_ratio_predicted": float(predicted_binary.mean()),
            "wound_area_ratio_ground_truth": float(ground_truth.mean()),
            **sample_metrics,
        }
        if include_hd95:
            sample_result["hd95"] = compute_hd95(predicted_binary, ground_truth)

        batch_results.append(sample_result)

    return batch_results


# ============================================================
# LOSS TRACKING HELPER
# ============================================================

class EpochMetricAccumulator:
    """
    Accumulates loss and metrics across batches within one epoch.

    Usage:
        accumulator = EpochMetricAccumulator()
        for batch in dataloader:
            loss = ...
            accumulator.update_loss(loss.item(), batch_size=len(batch))
        avg_loss = accumulator.get_average_loss()
    """

    def __init__(self):
        self.total_loss = 0.0
        self.total_samples = 0
        self.all_sample_metrics: List[Dict[str, Any]] = []

    def update_loss(self, loss_value: float, batch_size: int) -> None:
        """Add loss from one batch."""
        self.total_loss += loss_value * batch_size
        self.total_samples += batch_size

    def update_sample_metrics(self, batch_sample_results: List[Dict[str, Any]]) -> None:
        """Add per-sample metrics from one batch."""
        self.all_sample_metrics.extend(batch_sample_results)

    def get_average_loss(self) -> float:
        """Return weighted average loss over all samples seen."""
        if self.total_samples == 0:
            return 0.0
        return self.total_loss / self.total_samples

    def get_aggregate_metrics(self) -> Dict[str, float]:
        """Return macro-averaged metrics over all samples seen."""
        return aggregate_metrics(self.all_sample_metrics)

    def reset(self) -> None:
        """Clear all accumulated values."""
        self.total_loss = 0.0
        self.total_samples = 0
        self.all_sample_metrics = []
