"""
Phase 02 Baseline Evaluation Script — DFU-WoundMonitor.

Specs: P02-S05 (Evaluation) + P02-S06 (Qualitative Review).

Usage:
    python scripts/evaluation/run_phase_02_evaluation.py
    python scripts/evaluation/run_phase_02_evaluation.py --config configs/training/baseline_segmentation.json

This script:
    1. Loads the best checkpoint saved during training.
    2. Runs evaluation on the test split ONLY.
    3. Computes Dice, IoU, Precision, Recall per sample and aggregated.
    4. Generates qualitative visualizations (image / GT / prediction / overlay).
    5. Produces a failure analysis of observed error patterns.
    6. Saves all results to reports/evaluation/.

SPLIT ISOLATION:
    This is the first and only time the test split is used.
    The checkpoint used was selected solely by validation Dice — not test metrics.

Coding Style: Beginner-Understandable Python
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))


from scripts.verification.verify_phase_02_metrics import verify_saved_predictions
from src.data.splitting import validate_manifest_for_training
from src.segmentation.dataset import create_dataloaders
from src.segmentation.evaluator import (
    analyze_failure_modes,
    collect_predictions_for_visualization,
    create_qualitative_visualization,
    evaluate_on_test_set,
    save_evaluation_results,
    save_prediction_artifacts,
)
from src.segmentation.model import BCEDiceLoss, LightweightUNet
from src.segmentation.trainer import load_checkpoint, select_device


def load_config(config_path: str) -> dict:
    """Load training/evaluation configuration from a JSON file."""
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_file, encoding="utf-8") as config_handle:
        config = json.load(config_handle)
    print(f"Configuration loaded from: {config_path}")
    return config


def main():
    # ---- Parse arguments ----
    parser = argparse.ArgumentParser(
        description="Run Phase 02 baseline test evaluation and qualitative review."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/training/baseline_segmentation.json",
        help="Path to training configuration JSON file.",
    )
    args = parser.parse_args()

    # ---- Load config ----
    config = load_config(args.config)
    experiment_id = config.get("experiment_id", "P02-baseline")
    print(f"\n{'='*60}")
    print(f"Evaluation: {experiment_id}")
    print(f"{'='*60}\n")

    # ---- Select device ----
    device_config = config.get("device", {})
    device = select_device(
        preferred=device_config.get("preferred", "cuda"),
        fallback=device_config.get("fallback", "cpu"),
    )

    # ---- Load DataLoaders (test loader only used here) ----
    data_config = config.get("data", {})
    preprocessing_config = config.get("preprocessing", {})
    training_config = config.get("training", {})

    manifest_path = data_config.get("manifest_path", "data/manifests/dataset_manifest.json")

    print(f"Loading data from manifest: {manifest_path}")
    validate_manifest_for_training(manifest_path, require_real_data=True)
    _, _, test_loader = create_dataloaders(
        manifest_path=manifest_path,
        input_height=preprocessing_config.get("input_height", 256),
        input_width=preprocessing_config.get("input_width", 256),
        normalize_mean=preprocessing_config.get("normalize_mean", [0.485, 0.456, 0.406]),
        normalize_std=preprocessing_config.get("normalize_std", [0.229, 0.224, 0.225]),
        mask_threshold=preprocessing_config.get("mask_threshold", 128),
        batch_size=training_config.get("batch_size", 2),
        horizontal_flip_prob=0.0,  # No augmentation for evaluation
        num_workers=0,
    )

    # ---- Initialize model with same config as training ----
    model_config = config.get("model", {})
    model = LightweightUNet(
        encoder_channels=model_config.get("encoder_channels", [32, 64, 128, 256]),
        num_classes=model_config.get("num_classes", 1),
    )
    model = model.to(device)

    # ---- Load best checkpoint (REQ-P02-S05-002, REQ-P02-S07-004) ----
    checkpoint_config = config.get("checkpointing", {})
    checkpoint_dir = checkpoint_config.get("checkpoint_dir", "models/checkpoints")
    checkpoint_filename = checkpoint_config.get(
        "checkpoint_filename_template", "P02-baseline-unet-bce-dice-v1_best_val_dice.pth"
    )
    checkpoint_path = str(Path(checkpoint_dir) / checkpoint_filename)

    print(f"\nLoading checkpoint: {checkpoint_path}")
    checkpoint_metadata = load_checkpoint(
        checkpoint_path=checkpoint_path,
        model=model,
        device=device,
    )

    # ---- Initialize loss function ----
    loss_config = config.get("loss", {})
    loss_fn = BCEDiceLoss(
        bce_weight=loss_config.get("bce_weight", 0.5),
        dice_weight=loss_config.get("dice_weight", 0.5),
    )

    # ---- Run test evaluation (REQ-P02-S05-001 through REQ-P02-S05-009) ----
    evaluation_config = config.get("evaluation", {})
    prediction_threshold = evaluation_config.get("prediction_threshold", 0.5)

    aggregate_results, per_sample_results = evaluate_on_test_set(
        model=model,
        test_loader=test_loader,
        loss_fn=loss_fn,
        device=device,
        prediction_threshold=prediction_threshold,
    )

    # ---- Collect visualization data (REQ-P02-S06-002) ----
    print("\nCollecting predictions for qualitative visualization...")
    visualization_data = collect_predictions_for_visualization(
        model=model,
        test_loader=test_loader,
        device=device,
        prediction_threshold=prediction_threshold,
        normalize_mean=preprocessing_config.get("normalize_mean", [0.485, 0.456, 0.406]),
        normalize_std=preprocessing_config.get("normalize_std", [0.229, 0.224, 0.225]),
    )

    output_config = config.get("output", {})
    prediction_output_dir = output_config.get(
        "prediction_output_dir",
        f"outputs/predictions/{experiment_id}",
    )
    prediction_artifact_paths = save_prediction_artifacts(
        visualization_data=visualization_data,
        output_dir=prediction_output_dir,
    )

    # ---- Create qualitative visualization figures ----
    qualitative_output_dir = output_config.get(
        "qualitative_output_dir",
        "outputs/visualizations/phase_02_qualitative"
    )

    visualization_paths = create_qualitative_visualization(
        visualization_data=visualization_data,
        output_dir=qualitative_output_dir,
        experiment_id=experiment_id,
    )

    # ---- Failure analysis (REQ-P02-S06-003, REQ-P02-S06-004) ----
    print("\nAnalyzing failure modes...")
    failure_analysis = analyze_failure_modes(visualization_data=visualization_data)

    print(
        f"\nFailure analysis:\n"
        f"  Good predictions (Dice>=0.7):     {failure_analysis['good_predictions']}\n"
        f"  Mediocre predictions (Dice 0.4-0.7): {failure_analysis['mediocre_predictions']}\n"
        f"  Poor predictions (Dice<0.4):       {failure_analysis['poor_predictions']}\n"
        f"  Observed failure patterns: {failure_analysis['observed_failure_pattern_counts']}"
    )

    # ---- Save evaluation results ----
    evaluation_results_path = output_config.get(
        "evaluation_results_file",
        f"reports/evaluation/{experiment_id}_test_results.json"
    )
    os.makedirs(Path(evaluation_results_path).parent, exist_ok=True)

    save_evaluation_results(
        aggregate_results=aggregate_results,
        per_sample_results=per_sample_results,
        failure_analysis=failure_analysis,
        visualization_paths=visualization_paths,
        checkpoint_metadata=checkpoint_metadata,
        output_path=evaluation_results_path,
        prediction_artifact_paths=prediction_artifact_paths,
        independent_verification_path=output_config.get(
            "independent_metric_verification_file",
            f"reports/evaluation/{experiment_id}_independent_metric_verification.json",
        ),
    )

    independent_verification_path = output_config.get(
        "independent_metric_verification_file",
        f"reports/evaluation/{experiment_id}_independent_metric_verification.json",
    )
    independent_report = verify_saved_predictions(
        predictions_dir=prediction_output_dir,
        evaluation_results_path=evaluation_results_path,
        output_path=independent_verification_path,
    )

    # ---- Final summary ----
    print(
        f"\n{'='*60}\n"
        f"Evaluation complete!\n"
        f"  Test Dice:      {aggregate_results['mean_dice']:.4f}\n"
        f"  Test IoU:       {aggregate_results['mean_iou']:.4f}\n"
        f"  Test Precision: {aggregate_results['mean_precision']:.4f}\n"
        f"  Test Recall:    {aggregate_results['mean_recall']:.4f}\n"
        f"  Results: {evaluation_results_path}\n"
        f"  Independent metrics: {independent_verification_path} ({independent_report['verification_status']})\n"
        f"  Predictions: {prediction_output_dir}\n"
        f"  Visualizations: {qualitative_output_dir}\n"
        f"{'='*60}\n"
        f"DISCLAIMER: These results are from a monitoring prototype on 3 test samples.\n"
        f"Do NOT use for clinical diagnosis or treatment decisions.\n"
        f"{'='*60}\n"
    )


if __name__ == "__main__":
    main()
