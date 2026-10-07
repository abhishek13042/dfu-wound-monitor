"""
Baseline Training Engine — DFU-WoundMonitor.

Spec: P02-S04 — Baseline Training and Checkpointing.

This module orchestrates the baseline segmentation training loop.
It manages: random seed setting, device selection, training/validation loops,
checkpointing, logging, and reproducibility.

SPLIT ISOLATION RULE (REQ-P02-S04-004):
    Training: Uses ONLY the train split.
    Validation: Used to select the best checkpoint.
    Test: NEVER touched until final evaluation (separate script).

CHECKPOINT SELECTION (REQ-P02-S04-006):
    The checkpoint selection metric is defined BEFORE training begins.
    It is: best validation Dice score (higher is better).
    This is documented in the config and not changed based on test results.

RANDOM SEEDS (REQ-P02-S04-002):
    Seeds are set for: torch, numpy, random.
    Known nondeterminism: DataLoader with multiple workers may have nondeterministic
    ordering. We use num_workers=0 (main process only) to eliminate this.
    CUDA operations may still have minor nondeterminism on some GPUs
    (cudnn.benchmark=True vs False tradeoff). Not applicable for CPU-only training.

OPTIMIZER (REQ-P02-S04-003):
    Adam optimizer is selected.
    Rationale: Adam (Adaptive Moment Estimation) maintains per-parameter learning rate
    estimates. It converges faster than SGD on small datasets without extensive
    learning rate tuning. The default betas (0.9, 0.999) work well for most tasks.
    Weight decay (L2 regularization) provides mild regularization for a tiny dataset.

Coding Style: Beginner-Understandable Python
"""

import json
import os
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from src.segmentation.metrics import EpochMetricAccumulator, evaluate_batch


# ============================================================
# REPRODUCIBILITY: Seed setting
# ============================================================

def set_random_seeds(seed: int) -> None:
    """
    Set random seeds for reproducible training (REQ-P02-S04-002).

    WHY WE SET MULTIPLE SEEDS:
        PyTorch uses its own random number generator (torch.manual_seed).
        Python's random module is separate (random.seed).
        NumPy has its own generator (numpy.random.seed).
        All three must be seeded to ensure reproducible behavior across
        weight initialization, data augmentation (random flips), and
        any NumPy-based operations.

    KNOWN NONDETERMINISM:
        DataLoader shuffling in training will differ between runs even with
        seeds set, unless we also set the worker_init_fn. For our baseline
        (num_workers=0), this is not an issue.
        GPU cuDNN operations may have non-deterministic results. Not applicable
        for our CPU baseline.

    Inputs:
        seed: Integer seed value.
    """
    random.seed(seed)               # Python built-in random
    np.random.seed(seed)            # NumPy
    torch.manual_seed(seed)         # PyTorch CPU RNG
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)   # PyTorch GPU RNG (if available)

    print(f"Random seeds set to: {seed}")


# ============================================================
# DEVICE SELECTION
# ============================================================

def select_device(preferred: str = "cuda", fallback: str = "cpu") -> torch.device:
    """
    Select compute device (REQ-P02-S03-007).

    Checks if preferred device is available; falls back gracefully.
    Does not assume GPU availability.

    Inputs:
        preferred: 'cuda' or 'cpu'.
        fallback: Device to use if preferred is unavailable.

    Outputs:
        torch.device object for use in model.to(device) and tensor.to(device).
    """
    if preferred == "cuda" and torch.cuda.is_available():
        device = torch.device("cuda")
        device_name = torch.cuda.get_device_name(0)
        print(f"Device selected: CUDA ({device_name})")
    else:
        device = torch.device(fallback)
        if preferred == "cuda":
            print("Note: CUDA not available. Falling back to CPU.")
        print(f"Device selected: {device}")

    return device


# ============================================================
# ONE TRAINING EPOCH
# ============================================================

def run_training_epoch(
    model: nn.Module,
    train_loader: DataLoader,
    loss_fn: nn.Module,
    optimizer: torch.optim.Optimizer,
    device: torch.device,
    epoch_number: int,
    prediction_threshold: float = 0.5,
) -> Dict[str, float]:
    """
    Run one full pass through the training data.

    This function:
        1. Sets model to training mode (enables BatchNorm and Dropout updates).
        2. Iterates all batches in train_loader.
        3. For each batch: forward pass → compute loss → backward pass → update weights.
        4. Accumulates loss and metrics.

    Inputs:
        model: The segmentation model.
        train_loader: DataLoader for the training split.
        loss_fn: Loss function (BCEDiceLoss).
        optimizer: Optimizer (Adam).
        device: Compute device.
        epoch_number: Current epoch index (for logging).
        prediction_threshold: Threshold to binarize predictions for metric computation.

    Outputs:
        Dictionary with 'train_loss', 'train_dice', 'train_iou', 'train_precision', 'train_recall'.
    """
    model.train()  # Training mode — BatchNorm uses batch statistics, gradients are tracked

    epoch_accumulator = EpochMetricAccumulator()

    num_batches = len(train_loader)

    for batch_index, (image_batch, mask_batch, sample_ids) in enumerate(train_loader):
        # Move tensors to compute device
        image_batch = image_batch.to(device)
        mask_batch = mask_batch.to(device)

        # Zero gradients from previous batch
        # (PyTorch accumulates gradients; we must reset them each step)
        optimizer.zero_grad()

        # FORWARD PASS: model makes predictions
        predictions = model(image_batch)

        # LOSS COMPUTATION: compare predictions to ground truth
        loss = loss_fn(predictions, mask_batch)

        # Check for non-finite loss (NaN or Inf) — fail clearly (REQ-P02-S04-008)
        if not torch.isfinite(loss):
            raise RuntimeError(
                f"Non-finite loss detected at epoch {epoch_number}, batch {batch_index}. "
                f"Loss value: {loss.item()}. "
                "Check for malformed inputs, label values outside {0, 1}, or very large inputs."
            )

        # BACKWARD PASS: compute gradients via backpropagation
        loss.backward()

        # WEIGHT UPDATE: optimizer adjusts model parameters using computed gradients
        optimizer.step()

        # Accumulate loss (weighted by batch size for correct averaging)
        batch_size = image_batch.shape[0]
        epoch_accumulator.update_loss(loss.item(), batch_size=batch_size)

        # Compute per-sample metrics for training monitoring
        batch_sample_results = evaluate_batch(
            predictions_batch=predictions,
            targets_batch=mask_batch,
            sample_ids=list(sample_ids),
            prediction_threshold=prediction_threshold,
        )
        epoch_accumulator.update_sample_metrics(batch_sample_results)

        # Print batch progress for small datasets
        if (batch_index + 1) % max(1, num_batches // 3) == 0:
            print(
                f"  Epoch {epoch_number} | Batch {batch_index + 1}/{num_batches} "
                f"| Loss: {loss.item():.4f}"
            )

    # Compute epoch-level averages
    average_train_loss = epoch_accumulator.get_average_loss()
    train_metrics = epoch_accumulator.get_aggregate_metrics()

    return {
        "train_loss": average_train_loss,
        "train_dice": train_metrics.get("mean_dice", 0.0),
        "train_iou": train_metrics.get("mean_iou", 0.0),
        "train_precision": train_metrics.get("mean_precision", 0.0),
        "train_recall": train_metrics.get("mean_recall", 0.0),
    }


# ============================================================
# ONE VALIDATION EPOCH
# ============================================================

def run_validation_epoch(
    model: nn.Module,
    val_loader: DataLoader,
    loss_fn: nn.Module,
    device: torch.device,
    prediction_threshold: float = 0.5,
) -> Dict[str, float]:
    """
    Run one full pass through the validation data.

    IMPORTANT: No gradient computation or weight updates here.
    Validation is read-only — it measures how well the model generalizes
    to unseen samples from the same dataset (REQ-P02-S04-004).

    Inputs:
        model: The segmentation model.
        val_loader: DataLoader for the validation split.
        loss_fn: Loss function (BCEDiceLoss).
        device: Compute device.
        prediction_threshold: Threshold to binarize predictions.

    Outputs:
        Dictionary with 'val_loss', 'val_dice', 'val_iou', 'val_precision', 'val_recall'.
    """
    model.eval()  # Evaluation mode — BatchNorm uses stored statistics, no dropout

    epoch_accumulator = EpochMetricAccumulator()

    with torch.no_grad():  # Disable gradient tracking to save memory and speed up
        for image_batch, mask_batch, sample_ids in val_loader:
            image_batch = image_batch.to(device)
            mask_batch = mask_batch.to(device)

            # Forward pass only (no backward pass for validation)
            predictions = model(image_batch)
            loss = loss_fn(predictions, mask_batch)

            batch_size = image_batch.shape[0]
            epoch_accumulator.update_loss(loss.item(), batch_size=batch_size)

            batch_sample_results = evaluate_batch(
                predictions_batch=predictions,
                targets_batch=mask_batch,
                sample_ids=list(sample_ids),
                prediction_threshold=prediction_threshold,
            )
            epoch_accumulator.update_sample_metrics(batch_sample_results)

    average_val_loss = epoch_accumulator.get_average_loss()
    val_metrics = epoch_accumulator.get_aggregate_metrics()

    return {
        "val_loss": average_val_loss,
        "val_dice": val_metrics.get("mean_dice", 0.0),
        "val_iou": val_metrics.get("mean_iou", 0.0),
        "val_precision": val_metrics.get("mean_precision", 0.0),
        "val_recall": val_metrics.get("mean_recall", 0.0),
    }


# ============================================================
# CHECKPOINT SAVING AND LOADING
# ============================================================

def save_checkpoint(
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    epoch: int,
    val_dice: float,
    config: Dict[str, Any],
    checkpoint_path: str,
) -> None:
    """
    Save a model checkpoint to disk (REQ-P02-S04-005).

    A checkpoint preserves:
        - Model state dict (all weights and biases)
        - Optimizer state dict (Adam's momentum terms — useful for resuming)
        - Epoch number (to know how far training progressed)
        - Validation Dice score (the metric used to select this checkpoint)
        - Configuration (to verify the checkpoint matches the run)

    Inputs:
        model: The trained model.
        optimizer: Optimizer (Adam) — state saved for potential resume.
        epoch: Current epoch number (1-indexed).
        val_dice: Validation Dice score that triggered this save.
        config: Training configuration dictionary.
        checkpoint_path: Full path to save the .pth file.
    """
    checkpoint_dir = Path(checkpoint_path).parent
    os.makedirs(checkpoint_dir, exist_ok=True)

    checkpoint_data = {
        "epoch": epoch,
        "val_dice": val_dice,
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "config_snapshot": {
            "experiment_id": config.get("experiment_id", "unknown"),
            "architecture": config.get("model", {}).get("architecture", "unknown"),
            "encoder_channels": config.get("model", {}).get("encoder_channels"),
            "num_classes": config.get("model", {}).get("num_classes", 1),
            "input_height": config.get("preprocessing", {}).get("input_height"),
            "input_width": config.get("preprocessing", {}).get("input_width"),
            "loss_name": config.get("loss", {}).get("name", "unknown"),
            "random_seed": config.get("training", {}).get("random_seed", 42),
        }
    }

    try:
        torch.save(checkpoint_data, checkpoint_path)
        print(f"  Checkpoint saved: {checkpoint_path} (epoch={epoch}, val_dice={val_dice:.4f})")
    except Exception as save_error:
        # Fail clearly on checkpoint-write failures (REQ-P02-S04-008)
        raise RuntimeError(
            f"Failed to save checkpoint to '{checkpoint_path}'.\n"
            f"Error: {save_error}"
        )


def load_checkpoint(
    checkpoint_path: str,
    model: nn.Module,
    device: torch.device,
    optimizer: Optional[torch.optim.Optimizer] = None,
) -> Dict[str, Any]:
    """
    Load a saved checkpoint and restore model weights.

    Inputs:
        checkpoint_path: Path to the .pth checkpoint file.
        model: Model to load weights into (must have matching architecture).
        device: Target device for loading.
        optimizer: If provided, also restores optimizer state.

    Outputs:
        Dictionary with checkpoint metadata (epoch, val_dice, config_snapshot).

    Raises:
        FileNotFoundError: If checkpoint file does not exist.
    """
    checkpoint_file = Path(checkpoint_path)
    if not checkpoint_file.exists():
        raise FileNotFoundError(
            f"Checkpoint not found: {checkpoint_path}. "
            "Ensure training has been run and the checkpoint was saved."
        )

    checkpoint_data = torch.load(checkpoint_path, map_location=device, weights_only=False)

    model.load_state_dict(checkpoint_data["model_state_dict"])

    if optimizer is not None and "optimizer_state_dict" in checkpoint_data:
        optimizer.load_state_dict(checkpoint_data["optimizer_state_dict"])

    print(
        f"Checkpoint loaded from: {checkpoint_path}\n"
        f"  Epoch: {checkpoint_data.get('epoch', 'unknown')}\n"
        f"  Val Dice: {checkpoint_data.get('val_dice', 'unknown')}"
    )

    return {
        "epoch": checkpoint_data.get("epoch"),
        "val_dice": checkpoint_data.get("val_dice"),
        "config_snapshot": checkpoint_data.get("config_snapshot", {}),
    }


# ============================================================
# MAIN TRAINING LOOP
# ============================================================

def train_baseline_model(
    model: nn.Module,
    loss_fn: nn.Module,
    train_loader: DataLoader,
    val_loader: DataLoader,
    config: Dict[str, Any],
    device: torch.device,
) -> Dict[str, Any]:
    """
    Full training loop: train for num_epochs, validate each epoch,
    save best checkpoint, log all metrics.

    Split isolation: Only train_loader and val_loader are used here.
    The test split is never touched (REQ-P02-S04-004).

    Checkpoint selection metric is defined before training starts
    using config['checkpointing']['checkpoint_selection_metric'] (REQ-P02-S04-006).

    Inputs:
        model: LightweightUNet model (initialized, moved to device).
        loss_fn: BCEDiceLoss instance.
        train_loader: DataLoader for train split only.
        val_loader: DataLoader for val split only.
        config: Full training configuration dictionary.
        device: Compute device.

    Outputs:
        Training log dict with epoch-by-epoch metrics, best epoch, and paths.
    """
    training_config = config.get("training", {})
    checkpoint_config = config.get("checkpointing", {})
    evaluation_config = config.get("evaluation", {})

    num_epochs = training_config.get("num_epochs", 20)
    learning_rate = training_config.get("learning_rate", 0.001)
    weight_decay = training_config.get("weight_decay", 0.0001)
    random_seed = training_config.get("random_seed", 42)
    prediction_threshold = evaluation_config.get("prediction_threshold", 0.5)

    checkpoint_dir = checkpoint_config.get("checkpoint_dir", "models/checkpoints")
    checkpoint_filename = checkpoint_config.get(
        "checkpoint_filename_template", "baseline_best.pth"
    )
    checkpoint_path = str(Path(checkpoint_dir) / checkpoint_filename)

    # Set seeds for reproducibility
    set_random_seeds(seed=random_seed)

    # ---- OPTIMIZER (REQ-P02-S04-003) ----
    # Adam: Adaptive Moment Estimation.
    # Maintains per-parameter learning rate using running estimates of
    # first moment (mean of gradients) and second moment (mean of squared gradients).
    # lr: global learning rate (scaled per parameter by Adam's adaptive mechanism).
    # weight_decay: L2 penalty on weights to reduce overfitting.
    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=learning_rate,
        weight_decay=weight_decay,
    )

    # ---- CHECKPOINT SELECTION METRIC ----
    # Defined BEFORE training starts (REQ-P02-S04-006)
    checkpoint_metric = checkpoint_config.get("checkpoint_selection_metric", "val_dice")
    checkpoint_mode = checkpoint_config.get("checkpoint_selection_mode", "max")

    # Initialize best metric value
    if checkpoint_mode == "max":
        best_metric_value = -float("inf")
    else:
        best_metric_value = float("inf")

    print(f"\nCheckpoint selection: best '{checkpoint_metric}' ({checkpoint_mode})")
    print(f"Training for {num_epochs} epochs on device: {device}\n")

    # ---- TRAINING LOG ----
    epoch_logs: List[Dict[str, Any]] = []
    training_start_time = time.time()

    # ---- EPOCH LOOP ----
    for epoch in range(1, num_epochs + 1):
        epoch_start_time = time.time()
        print(f"Epoch {epoch}/{num_epochs}")

        # Training pass
        train_metrics = run_training_epoch(
            model=model,
            train_loader=train_loader,
            loss_fn=loss_fn,
            optimizer=optimizer,
            device=device,
            epoch_number=epoch,
            prediction_threshold=prediction_threshold,
        )

        # Validation pass (REQ-P02-S04-007)
        val_metrics = run_validation_epoch(
            model=model,
            val_loader=val_loader,
            loss_fn=loss_fn,
            device=device,
            prediction_threshold=prediction_threshold,
        )

        epoch_duration_seconds = time.time() - epoch_start_time
        current_lr = optimizer.param_groups[0]["lr"]

        # Log epoch metrics
        epoch_log_entry = {
            "epoch": epoch,
            "train_loss": round(train_metrics["train_loss"], 6),
            "train_dice": round(train_metrics["train_dice"], 6),
            "val_loss": round(val_metrics["val_loss"], 6),
            "val_dice": round(val_metrics["val_dice"], 6),
            "val_iou": round(val_metrics["val_iou"], 6),
            "val_precision": round(val_metrics["val_precision"], 6),
            "val_recall": round(val_metrics["val_recall"], 6),
            "learning_rate": current_lr,
            "epoch_duration_seconds": round(epoch_duration_seconds, 2),
        }
        epoch_logs.append(epoch_log_entry)

        print(
            f"  train_loss={train_metrics['train_loss']:.4f} | "
            f"train_dice={train_metrics['train_dice']:.4f} | "
            f"val_loss={val_metrics['val_loss']:.4f} | "
            f"val_dice={val_metrics['val_dice']:.4f} | "
            f"val_iou={val_metrics['val_iou']:.4f} | "
            f"lr={current_lr:.6f} | "
            f"time={epoch_duration_seconds:.1f}s"
        )

        # ---- CHECKPOINT SAVING ----
        current_metric_value = val_metrics.get(checkpoint_metric, 0.0)

        is_new_best = (
            (checkpoint_mode == "max" and current_metric_value > best_metric_value) or
            (checkpoint_mode == "min" and current_metric_value < best_metric_value)
        )

        if is_new_best:
            best_metric_value = current_metric_value
            save_checkpoint(
                model=model,
                optimizer=optimizer,
                epoch=epoch,
                val_dice=val_metrics["val_dice"],
                config=config,
                checkpoint_path=checkpoint_path,
            )

    total_training_time = time.time() - training_start_time

    print(
        f"\nTraining complete.\n"
        f"  Best {checkpoint_metric}: {best_metric_value:.4f}\n"
        f"  Checkpoint: {checkpoint_path}\n"
        f"  Total training time: {total_training_time:.1f}s"
    )

    training_log = {
        "experiment_id": config.get("experiment_id", "unknown"),
        "total_epochs_completed": num_epochs,
        "best_metric_name": checkpoint_metric,
        "best_metric_value": round(best_metric_value, 6),
        "checkpoint_path": checkpoint_path,
        "total_training_time_seconds": round(total_training_time, 2),
        "epoch_logs": epoch_logs,
    }

    return training_log
