"""
Baseline Test Evaluation and Qualitative Review — DFU-WoundMonitor.

Specs: P02-S05 (Evaluation and Metrics) + P02-S06 (Qualitative Evaluation).

This module runs the final test-set evaluation using the best checkpoint
selected during training and generates qualitative visualization outputs.

SPLIT ISOLATION (REQ-P02-S05-001):
    This module is the ONLY place the test split is used.
    It is called AFTER training is complete and the checkpoint is selected.
    No test information was used to choose the architecture or hyperparameters.

CHECKPOINT PROVENANCE (REQ-P02-S05-002, REQ-P02-S07-004):
    The checkpoint used for evaluation is the one saved by the trainer
    using the predefined validation Dice criterion — not cherry-picked.

QUALITATIVE REVIEW (REQ-P02-S06-001 through REQ-P02-S06-007):
    Visualizations show: original image, ground truth mask, prediction, and overlay.
    Failure categories are evidence-based (observed, not assumed).
    No clinical claims are made from model errors (REQ-P02-S06-005).

Coding Style: Beginner-Understandable Python
"""

import json
import os
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # Non-interactive backend for server/script use
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from src.segmentation.metrics import (
    aggregate_metrics,
    compute_binary_segmentation_metrics,
    evaluate_batch,
)

# ============================================================
# TEST SET EVALUATION (P02-S05)
# ============================================================

def evaluate_on_test_set(
    model: nn.Module,
    test_loader: DataLoader,
    loss_fn: nn.Module,
    device: torch.device,
    prediction_threshold: float = 0.5,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """
    Evaluate the model on the test split and return metrics + per-sample results.

    This function uses ONLY the test split data (REQ-P02-S05-001).
    Every number in the output comes from an actual forward pass (REQ-P02-S05-008).

    Inputs:
        model: Loaded model with best checkpoint weights.
        test_loader: DataLoader for the test split (batch_size=1 recommended).
        loss_fn: Loss function for computing test loss.
        device: Compute device.
        prediction_threshold: Threshold to binarize predictions.

    Outputs:
        Tuple of:
            aggregate_results: Dict with mean_dice, mean_iou, mean_precision, mean_recall.
            per_sample_results: List of per-sample metric dicts.
    """
    model.eval()  # Evaluation mode — no gradient computation, no dropout

    all_per_sample_results: list[dict[str, Any]] = []
    total_test_loss = 0.0
    total_test_samples = 0

    print(f"\nRunning test set evaluation (threshold={prediction_threshold})...")

    with torch.no_grad():
        for image_batch, mask_batch, sample_ids in test_loader:
            image_batch = image_batch.to(device)
            mask_batch = mask_batch.to(device)

            # Forward pass
            prediction_logits = model(image_batch)

            # Loss
            loss = loss_fn(prediction_logits, mask_batch)
            batch_size = image_batch.shape[0]
            total_test_loss += loss.item() * batch_size
            total_test_samples += batch_size

            # Per-sample metrics
            batch_results = evaluate_batch(
                predictions_batch=torch.sigmoid(prediction_logits),
                targets_batch=mask_batch,
                sample_ids=list(sample_ids),
                prediction_threshold=prediction_threshold,
            )
            all_per_sample_results.extend(batch_results)

            # Print per-sample result
            for result in batch_results:
                print(
                    f"  [{result['sample_id']}] "
                    f"Dice={result['dice']:.4f} | "
                    f"IoU={result['iou']:.4f} | "
                    f"Prec={result['precision']:.4f} | "
                    f"Recall={result['recall']:.4f}"
                )

    average_test_loss = total_test_loss / max(total_test_samples, 1)
    aggregate_results = aggregate_metrics(all_per_sample_results)
    aggregate_results["test_loss"] = round(average_test_loss, 6)
    aggregate_results["prediction_threshold"] = prediction_threshold
    aggregate_results["num_samples"] = len(all_per_sample_results)

    print(
        f"\nTest set results ({len(all_per_sample_results)} samples):\n"
        f"  Mean Dice:      {aggregate_results['mean_dice']:.4f} ± {aggregate_results['std_dice']:.4f}\n"
        f"  Mean IoU:       {aggregate_results['mean_iou']:.4f}\n"
        f"  Mean Precision: {aggregate_results['mean_precision']:.4f}\n"
        f"  Mean Recall:    {aggregate_results['mean_recall']:.4f}\n"
        f"  Test Loss:      {aggregate_results['test_loss']:.4f}"
    )

    return aggregate_results, all_per_sample_results


# ============================================================
# QUALITATIVE VISUALIZATION (P02-S06)
# ============================================================

def collect_predictions_for_visualization(
    model: nn.Module,
    test_loader: DataLoader,
    device: torch.device,
    prediction_threshold: float = 0.5,
    normalize_mean: list[float] | None = None,
    normalize_std: list[float] | None = None,
) -> list[dict[str, Any]]:
    """
    Collect raw predictions, images, and masks for qualitative visualization.

    We denormalize images back to [0, 1] for display.

    Inputs:
        model: Model with loaded checkpoint weights.
        test_loader: DataLoader for the test split.
        device: Compute device.
        prediction_threshold: Threshold for binary prediction.
        normalize_mean: Per-channel mean used during preprocessing.
        normalize_std: Per-channel std used during preprocessing.

    Outputs:
        List of dicts, each with 'sample_id', 'image', 'ground_truth', 'prediction',
        'prediction_probs', 'dice', 'iou' for one test sample.
    """
    if normalize_mean is None:
        normalize_mean = [0.485, 0.456, 0.406]
    if normalize_std is None:
        normalize_std = [0.229, 0.224, 0.225]

    model.eval()
    visualization_data = []

    with torch.no_grad():
        for image_batch, mask_batch, sample_ids in test_loader:
            image_batch_device = image_batch.to(device)
            predictions = torch.sigmoid(model(image_batch_device))

            batch_size = image_batch.shape[0]
            for sample_index in range(batch_size):
                sample_id = sample_ids[sample_index]

                # Denormalize image for display
                # Image tensor shape: (3, H, W)
                image_chw = image_batch[sample_index].cpu().numpy()  # (3, H, W)

                # Reverse normalization: pixel = (normalized * std) + mean
                mean_array = np.array(normalize_mean, dtype=np.float32).reshape(3, 1, 1)
                std_array = np.array(normalize_std, dtype=np.float32).reshape(3, 1, 1)
                image_denorm = image_chw * std_array + mean_array

                # Clip to [0, 1] and convert to (H, W, 3) for matplotlib
                image_display = np.clip(image_denorm, 0.0, 1.0)
                image_display = np.transpose(image_display, (1, 2, 0))  # (H, W, 3)

                # Ground truth mask: (1, H, W) → (H, W)
                ground_truth = mask_batch[sample_index, 0].cpu().numpy()

                # Predicted probabilities: (1, H, W) → (H, W)
                prediction_probs = predictions[sample_index, 0].cpu().numpy()

                # Binary prediction
                prediction_binary = (prediction_probs >= prediction_threshold).astype(np.float32)

                # Compute metrics for this sample
                sample_metrics = compute_binary_segmentation_metrics(
                    predicted_mask=prediction_binary,
                    ground_truth_mask=ground_truth,
                )

                visualization_data.append({
                    "sample_id": sample_id,
                    "image_display": image_display,
                    "ground_truth": ground_truth,
                    "prediction_binary": prediction_binary,
                    "prediction_probs": prediction_probs,
                    "dice": sample_metrics["dice"],
                    "iou": sample_metrics["iou"],
                    "precision": sample_metrics["precision"],
                    "recall": sample_metrics["recall"],
                    "wound_area_gt": float(ground_truth.mean()),
                    "wound_area_pred": float(prediction_binary.mean()),
                })

    return visualization_data


def save_prediction_artifacts(
    visualization_data: list[dict[str, Any]],
    output_dir: str,
) -> list[str]:
    """Save per-sample probabilities, binary predictions, and ground truth.

    The compressed NumPy files are intentionally generated artifacts rather than
    Git-tracked source data. They keep the sample identifier next to both the
    prediction and its reference mask so the independent metric verifier can
    audit an evaluation without calling the production metric module.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    saved_paths: list[str] = []

    for sample_data in visualization_data:
        sample_id = str(sample_data["sample_id"])
        artifact_path = output_path / f"{sample_id}.npz"
        np.savez_compressed(
            artifact_path,
            sample_id=np.array(sample_id),
            prediction_probability=np.asarray(sample_data["prediction_probs"], dtype=np.float32),
            prediction_binary=np.asarray(sample_data["prediction_binary"], dtype=np.uint8),
            ground_truth_mask=np.asarray(sample_data["ground_truth"], dtype=np.uint8),
        )
        saved_paths.append(str(artifact_path))

    return saved_paths


def create_qualitative_visualization(
    visualization_data: list[dict[str, Any]],
    output_dir: str,
    experiment_id: str,
) -> list[str]:
    """
    Create qualitative visualization figures for test samples (REQ-P02-S06-001/002).

    For each sample shows: original image | ground truth | prediction | overlay.
    Samples are sorted by Dice score so we can identify best/mediocre/worst cases.

    Inputs:
        visualization_data: List of dicts from collect_predictions_for_visualization().
        output_dir: Directory to save figures.
        experiment_id: Used in filenames.

    Outputs:
        List of saved figure paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    saved_paths = []

    # Sort by Dice score to find best / mediocre / poor predictions
    sorted_samples = sorted(visualization_data, key=lambda x: x["dice"], reverse=True)

    print(f"\nGenerating qualitative visualizations for {len(sorted_samples)} test samples...")

    for rank, sample_data in enumerate(sorted_samples):
        sample_id = sample_data["sample_id"]
        image_display = sample_data["image_display"]
        ground_truth = sample_data["ground_truth"]
        prediction_binary = sample_data["prediction_binary"]
        prediction_probs = sample_data["prediction_probs"]
        dice = sample_data["dice"]
        iou = sample_data["iou"]

        # Determine quality label
        if dice >= 0.7:
            quality_label = "GOOD"
        elif dice >= 0.4:
            quality_label = "MEDIOCRE"
        else:
            quality_label = "POOR"

        # Create a seven-panel figure required by P02-S06:
        # image, ground truth, probability, binary prediction, ground-truth
        # overlay, prediction overlay, and TP/FP/FN error overlay.
        fig, axes = plt.subplots(1, 7, figsize=(28, 4))
        fig.suptitle(
            f"Sample: {sample_id} | Quality: {quality_label} | Dice={dice:.3f} | IoU={iou:.3f}",
            fontsize=12,
            fontweight="bold",
        )

        # Panel 1: Original image
        axes[0].imshow(image_display)
        axes[0].set_title("Input Image (denormalized)", fontsize=10)
        axes[0].axis("off")

        # Panel 2: Ground truth mask
        axes[1].imshow(ground_truth, cmap="Reds", vmin=0, vmax=1)
        axes[1].set_title(
            f"Ground Truth\n(wound area={sample_data['wound_area_gt']:.1%})",
            fontsize=10,
        )
        axes[1].axis("off")

        # Panel 3: Model prediction (probability map)
        im = axes[2].imshow(prediction_probs, cmap="hot", vmin=0, vmax=1)
        plt.colorbar(im, ax=axes[2], fraction=0.046)
        axes[2].set_title(
            f"Predicted Probabilities\n(wound area={sample_data['wound_area_pred']:.1%} after thresh)",
            fontsize=10,
        )
        axes[2].axis("off")

        # Panel 4: Binary prediction
        axes[3].imshow(prediction_binary, cmap="gray", vmin=0, vmax=1)
        axes[3].set_title("Binary Prediction", fontsize=10)
        axes[3].axis("off")

        # Build masks used by all overlay panels.
        tp_mask = (prediction_binary == 1) & (ground_truth == 1)
        fp_mask = (prediction_binary == 1) & (ground_truth == 0)
        fn_mask = (prediction_binary == 0) & (ground_truth == 1)

        # Panel 5: Ground-truth overlay
        ground_truth_overlay = image_display.copy()
        ground_truth_overlay[ground_truth == 1] = (
            0.6 * ground_truth_overlay[ground_truth == 1] + 0.4 * np.array([1.0, 0.0, 0.0])
        )
        axes[4].imshow(ground_truth_overlay)
        axes[4].set_title("Ground Truth Overlay", fontsize=10)
        axes[4].axis("off")

        # Panel 6: Prediction overlay
        prediction_overlay = image_display.copy()
        prediction_overlay[prediction_binary == 1] = (
            0.6 * prediction_overlay[prediction_binary == 1] + 0.4 * np.array([0.0, 0.4, 1.0])
        )
        axes[5].imshow(prediction_overlay)
        axes[5].set_title("Prediction Overlay", fontsize=10)
        axes[5].axis("off")

        # Panel 7: Overlay showing TP, FP, FN
        # Create RGB overlay:
        #   TP (wound in both GT and Pred): Green
        #   FP (wound in Pred, not GT): Blue
        #   FN (wound in GT, not Pred): Red
        #   TN (background in both): Black
        overlay = np.zeros((*ground_truth.shape, 3), dtype=np.float32)

        overlay[tp_mask] = [0.0, 0.8, 0.0]   # Green = True Positive
        overlay[fp_mask] = [0.2, 0.4, 1.0]   # Blue = False Positive
        overlay[fn_mask] = [1.0, 0.2, 0.2]   # Red = False Negative

        axes[6].imshow(overlay)
        tp_patch = mpatches.Patch(color=(0.0, 0.8, 0.0), label="TP")
        fp_patch = mpatches.Patch(color=(0.2, 0.4, 1.0), label="FP")
        fn_patch = mpatches.Patch(color=(1.0, 0.2, 0.2), label="FN")
        axes[6].legend(handles=[tp_patch, fp_patch, fn_patch], loc="lower right", fontsize=8)
        axes[6].set_title("TP / FP / FN", fontsize=10)
        axes[6].axis("off")

        plt.tight_layout()

        # Save figure
        figure_filename = f"{experiment_id}_rank{rank+1:02d}_{quality_label}_{sample_id}.png"
        figure_path = str(Path(output_dir) / figure_filename)
        plt.savefig(figure_path, dpi=100, bbox_inches="tight")
        plt.close(fig)

        saved_paths.append(figure_path)
        print(f"  Saved: {figure_path}")

    return saved_paths


# ============================================================
# FAILURE ANALYSIS (P02-S06)
# ============================================================

def analyze_failure_modes(
    visualization_data: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Identify and document observed failure categories (REQ-P02-S06-003/004).

    IMPORTANT: We only report failure categories actually observed
    in these results — not hypothetical categories (REQ-P02-S06-003).
    We do NOT convert model errors into clinical claims (REQ-P02-S06-005).

    Inputs:
        visualization_data: List of per-sample visualization dicts.

    Outputs:
        Dictionary of observed failure analysis with evidence.
    """
    failure_observations = []

    for sample_data in visualization_data:
        sample_id = sample_data["sample_id"]
        dice = sample_data["dice"]
        precision = sample_data["precision"]
        recall = sample_data["recall"]
        wound_area_gt = sample_data["wound_area_gt"]
        wound_area_pred = sample_data["wound_area_pred"]

        # Classify prediction quality
        if dice >= 0.7:
            prediction_quality = "good"
        elif dice >= 0.4:
            prediction_quality = "mediocre"
        else:
            prediction_quality = "poor"

        # Identify specific failure patterns
        observed_patterns = []

        if recall < 0.3:
            observed_patterns.append("under_segmentation")

        if precision < 0.3 and wound_area_pred > wound_area_gt * 2:
            observed_patterns.append("over_segmentation")

        if wound_area_gt < 0.05 and dice < 0.3:
            observed_patterns.append("small_wound_detection_failure")

        if precision < 0.5 and recall > 0.7:
            observed_patterns.append("false_positive_heavy")

        if precision > 0.7 and recall < 0.5:
            observed_patterns.append("false_negative_heavy")

        failure_observations.append({
            "sample_id": sample_id,
            "dice": round(dice, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "wound_area_gt": round(wound_area_gt, 4),
            "wound_area_pred": round(wound_area_pred, 4),
            "prediction_quality": prediction_quality,
            "observed_failure_patterns": observed_patterns,
        })

    # Aggregate failure category counts
    all_patterns = []
    for obs in failure_observations:
        all_patterns.extend(obs["observed_failure_patterns"])

    pattern_counts: dict[str, int] = {}
    for pattern in all_patterns:
        pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1

    poor_samples = [o for o in failure_observations if o["prediction_quality"] == "poor"]
    mediocre_samples = [o for o in failure_observations if o["prediction_quality"] == "mediocre"]
    good_samples = [o for o in failure_observations if o["prediction_quality"] == "good"]

    return {
        "total_samples_analyzed": len(failure_observations),
        "good_predictions": len(good_samples),
        "mediocre_predictions": len(mediocre_samples),
        "poor_predictions": len(poor_samples),
        "observed_failure_pattern_counts": pattern_counts,
        "_note_REQ_P02_S06_003": "Only failure categories actually observed in this evaluation are listed.",
        "_note_REQ_P02_S06_005": "Failure categories describe model prediction errors only. "
                                  "No clinical inferences are made from these technical observations.",
        "per_sample_observations": failure_observations,
    }


# ============================================================
# SAVE EVALUATION RESULTS
# ============================================================

def save_evaluation_results(
    aggregate_results: dict[str, Any],
    per_sample_results: list[dict[str, Any]],
    failure_analysis: dict[str, Any],
    visualization_paths: list[str],
    checkpoint_metadata: dict[str, Any],
    output_path: str,
    prediction_artifact_paths: list[str] | None = None,
    independent_verification_path: str | None = None,
) -> None:
    """
    Save complete test evaluation results to a JSON file (REQ-P02-S05-005).

    Inputs:
        aggregate_results: Mean/std metrics across test set.
        per_sample_results: Individual sample metrics.
        failure_analysis: Observed failure categories.
        visualization_paths: Paths to saved qualitative figures.
        checkpoint_metadata: Info about which checkpoint was evaluated.
        output_path: Path to write the results JSON.
        prediction_artifact_paths: Saved raw prediction artifact paths.
        independent_verification_path: Independent metric audit JSON path.
    """
    os.makedirs(Path(output_path).parent, exist_ok=True)

    results_document = {
        "_spec": "P02-S05 Baseline Evaluation and Metrics",
        "_requirement": "REQ-P02-S05-008: Every number comes from an actual run.",
        "checkpoint_evaluated": checkpoint_metadata,
        "aggregate_results": aggregate_results,
        "metric_definitions": {
            "dice": "2*TP / (2*TP + FP + FN). Range [0,1]. 1.0 = perfect overlap.",
            "iou": "TP / (TP + FP + FN). Stricter than Dice. Range [0,1].",
            "precision": "TP / (TP + FP). Fraction of predicted wound pixels that are correct.",
            "recall": "TP / (TP + FN). Fraction of actual wound pixels that were found.",
            "aggregation": "Macro-average: mean of per-sample scores. Treats all samples equally.",
            "why_not_accuracy": "~15% foreground → background-only predictor gets ~85% accuracy. "
                                "Dice/IoU focus on the foreground class.",
        },
        "per_sample_results": per_sample_results,
        "failure_analysis": failure_analysis,
        "qualitative_visualization_paths": visualization_paths,
        "prediction_artifact_paths": prediction_artifact_paths or [],
        "independent_metric_verification_path": independent_verification_path,
    }

    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(results_document, output_file, indent=2)

    print(f"\nEvaluation results saved to: {output_path}")
