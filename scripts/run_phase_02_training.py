"""
Phase 02 Baseline Training Script — DFU-WoundMonitor.

Spec: P02-S04 — Baseline Training and Checkpointing.

Usage:
    python scripts/run_phase_02_training.py
    python scripts/run_phase_02_training.py --config configs/training/baseline_segmentation.json

This script:
    1. Loads training configuration from JSON.
    2. Creates DataLoaders from Phase 01 manifest.
    3. Initializes the LightweightUNet model and BCEDiceLoss.
    4. Runs the training loop (train + validate per epoch).
    5. Saves the best checkpoint by validation Dice score.
    6. Writes the training log to reports/experiments/.

SPLIT ISOLATION:
    Training: train split only.
    Validation: val split only (for checkpoint selection).
    Test split: NOT used here. Run scripts/run_phase_02_evaluation.py after training.

Coding Style: Beginner-Understandable Python
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add project root to Python path so 'src' imports work
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import torch

from src.segmentation.dataset import create_dataloaders
from src.segmentation.model import (
    BCEDiceLoss,
    LightweightUNet,
    count_model_parameters,
    verify_model_forward_pass,
)
from src.segmentation.trainer import select_device, set_random_seeds, train_baseline_model


def load_config(config_path: str) -> dict:
    """Load training configuration from a JSON file."""
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}. "
            "Ensure configs/training/baseline_segmentation.json exists."
        )
    with open(config_file, "r", encoding="utf-8") as config_handle:
        config = json.load(config_handle)
    print(f"Configuration loaded from: {config_path}")
    return config


def main():
    # ---- Parse command-line arguments ----
    parser = argparse.ArgumentParser(
        description="Run Phase 02 baseline segmentation training."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/training/baseline_segmentation.json",
        help="Path to training configuration JSON file.",
    )
    args = parser.parse_args()

    # ---- Load configuration ----
    config = load_config(args.config)
    experiment_id = config.get("experiment_id", "P02-baseline")
    print(f"\n{'='*60}")
    print(f"Experiment: {experiment_id}")
    print(f"{'='*60}\n")

    # ---- Set random seeds (REQ-P02-S04-002) ----
    random_seed = config["training"].get("random_seed", 42)
    set_random_seeds(seed=random_seed)

    # ---- Select device (REQ-P02-S03-007) ----
    device_config = config.get("device", {})
    device = select_device(
        preferred=device_config.get("preferred", "cuda"),
        fallback=device_config.get("fallback", "cpu"),
    )

    # ---- Create DataLoaders from Phase 01 manifest (REQ-P02-S02-001) ----
    data_config = config.get("data", {})
    preprocessing_config = config.get("preprocessing", {})
    training_config = config.get("training", {})
    augmentation_config = config.get("augmentation", {})

    manifest_path = data_config.get("manifest_path", "data/manifests/dataset_manifest.json")

    print(f"\nLoading data from manifest: {manifest_path}")

    train_loader, val_loader, test_loader = create_dataloaders(
        manifest_path=manifest_path,
        input_height=preprocessing_config.get("input_height", 256),
        input_width=preprocessing_config.get("input_width", 256),
        normalize_mean=preprocessing_config.get("normalize_mean", [0.485, 0.456, 0.406]),
        normalize_std=preprocessing_config.get("normalize_std", [0.229, 0.224, 0.225]),
        mask_threshold=preprocessing_config.get("mask_threshold", 128),
        batch_size=training_config.get("batch_size", 2),
        horizontal_flip_prob=augmentation_config.get("train_horizontal_flip_prob", 0.5),
        num_workers=0,
    )

    # ---- Verify visual inspection (REQ-P02-S02-010) ----
    # Confirm first train batch loads correctly
    print("\nVisual inspection: loading first training batch...")
    first_batch_images, first_batch_masks, first_batch_ids = next(iter(train_loader))
    print(
        f"  First batch: images={tuple(first_batch_images.shape)}, "
        f"masks={tuple(first_batch_masks.shape)}, "
        f"sample_ids={list(first_batch_ids)}"
    )
    assert first_batch_images.shape[1] == 3, "Expected 3-channel RGB images"
    assert first_batch_masks.shape[1] == 1, "Expected single-channel binary masks"
    assert first_batch_images.shape[2] == preprocessing_config.get("input_height", 256)
    assert first_batch_images.shape[3] == preprocessing_config.get("input_width", 256)
    assert first_batch_masks.min().item() >= 0.0, "Mask values must be >= 0"
    assert first_batch_masks.max().item() <= 1.0, "Mask values must be <= 1"
    print("  Batch shape validation PASSED.")

    # ---- Initialize model (REQ-P02-S03-001) ----
    model_config = config.get("model", {})
    model = LightweightUNet(
        encoder_channels=model_config.get("encoder_channels", [32, 64, 128, 256]),
        num_classes=model_config.get("num_classes", 1),
    )
    model = model.to(device)

    # ---- Report model parameters (REQ-P02-S03-005) ----
    param_counts = count_model_parameters(model)
    print(
        f"\nModel: {model_config.get('architecture', 'LightweightUNet')}\n"
        f"  Total parameters:      {param_counts['total_parameters']:,}\n"
        f"  Trainable parameters:  {param_counts['trainable_parameters']:,}\n"
        f"  Non-trainable:         {param_counts['non_trainable_parameters']:,}"
    )

    # ---- Verify forward pass (REQ-P02-S03-006) ----
    print("\nRunning forward pass verification...")
    forward_pass_results = verify_model_forward_pass(
        model=model,
        input_height=preprocessing_config.get("input_height", 256),
        input_width=preprocessing_config.get("input_width", 256),
        batch_size=2,
        device=device,
    )
    print(f"  Input shape:    {forward_pass_results['input_shape']}")
    print(f"  Output shape:   {forward_pass_results['actual_output_shape']}")
    print(f"  Output range:   [{forward_pass_results['output_min']}, {forward_pass_results['output_max']}]")
    print(f"  Test loss:      {forward_pass_results['loss_value']}")
    print(f"  Forward pass:   {'PASSED' if forward_pass_results['forward_pass_success'] else 'FAILED'}")
    assert forward_pass_results["forward_pass_success"], "Forward pass verification failed!"

    # ---- Initialize loss function ----
    loss_config = config.get("loss", {})
    loss_fn = BCEDiceLoss(
        bce_weight=loss_config.get("bce_weight", 0.5),
        dice_weight=loss_config.get("dice_weight", 0.5),
    )

    # ---- Run training (REQ-P02-S04-004, REQ-P02-S04-007) ----
    print(f"\n{'='*60}")
    print("Starting training loop")
    print(f"  Epochs: {training_config.get('num_epochs', 20)}")
    print(f"  Batch size: {training_config.get('batch_size', 2)}")
    print(f"  Learning rate: {training_config.get('learning_rate', 0.001)}")
    print(f"  Loss: {loss_config.get('name', 'BCEDiceLoss')}")
    print(f"  Seed: {random_seed}")
    print(f"  Device: {device}")
    print(f"{'='*60}")

    training_log = train_baseline_model(
        model=model,
        loss_fn=loss_fn,
        train_loader=train_loader,
        val_loader=val_loader,
        config=config,
        device=device,
    )

    # ---- Save training log (REQ-P02-S04-007) ----
    output_config = config.get("output", {})
    log_file_path = output_config.get(
        "log_file",
        f"reports/experiments/{experiment_id}_training_log.json"
    )
    os.makedirs(Path(log_file_path).parent, exist_ok=True)

    # Attach parameter and config snapshot to log
    training_log["model_parameters"] = param_counts
    training_log["config"] = config
    training_log["forward_pass_verification"] = forward_pass_results

    with open(log_file_path, "w", encoding="utf-8") as log_file:
        json.dump(training_log, log_file, indent=2)

    print(f"\nTraining log saved to: {log_file_path}")

    # ---- Summary ----
    best_epoch = None
    best_val_dice = -1.0
    for epoch_log in training_log["epoch_logs"]:
        if epoch_log["val_dice"] > best_val_dice:
            best_val_dice = epoch_log["val_dice"]
            best_epoch = epoch_log["epoch"]

    print(
        f"\n{'='*60}\n"
        f"Training complete!\n"
        f"  Best epoch: {best_epoch}\n"
        f"  Best val Dice: {best_val_dice:.4f}\n"
        f"  Checkpoint: {training_log['checkpoint_path']}\n"
        f"  Log: {log_file_path}\n"
        f"{'='*60}\n"
        f"Next step: run evaluation:\n"
        f"  python scripts/run_phase_02_evaluation.py\n"
    )


if __name__ == "__main__":
    main()
