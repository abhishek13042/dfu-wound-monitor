"""Reproducible train/validation engine for SPEC-02-01."""

from __future__ import annotations

import json
import logging
import os
import platform
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from src.segmentation.metrics import EpochMetricAccumulator, evaluate_batch

LOGGER = logging.getLogger(__name__)


def set_random_seeds(seed: int, deterministic: bool = True) -> None:
    """Seed Python, NumPy, PyTorch, and CUDA generators where available."""

    os.environ["PYTHONHASHSEED"] = str(seed)
    if deterministic:
        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.benchmark = not deterministic
        torch.backends.cudnn.deterministic = deterministic
    try:
        torch.use_deterministic_algorithms(deterministic)
    except RuntimeError as error:
        if deterministic:
            LOGGER.warning("Deterministic PyTorch algorithms unavailable: %s", error)


def select_device(preferred: str = "cuda", fallback: str = "cpu") -> torch.device:
    """Select the requested available device, otherwise use the configured fallback."""

    def available_device(specification: str) -> Optional[torch.device]:
        try:
            candidate = torch.device(specification)
        except RuntimeError as error:
            raise ValueError(f"Unsupported device specification '{specification}'") from error
        if candidate.type == "cpu":
            return candidate
        if candidate.type == "cuda":
            if not torch.cuda.is_available():
                return None
            index = 0 if candidate.index is None else candidate.index
            if index >= torch.cuda.device_count():
                return None
            return candidate
        if candidate.type == "mps":
            mps_backend = getattr(torch.backends, "mps", None)
            if mps_backend is not None and mps_backend.is_available():
                return candidate
            return None
        raise ValueError(f"Unsupported device type '{candidate.type}'")

    selected = available_device(preferred)
    if selected is not None:
        return selected
    fallback_device = available_device(fallback)
    if fallback_device is None:
        raise RuntimeError(
            f"Neither preferred device '{preferred}' nor fallback device '{fallback}' is available"
        )
    LOGGER.info("Device '%s' unavailable; using fallback '%s'", preferred, fallback_device)
    return fallback_device


def collect_environment_metadata(device: torch.device) -> Dict[str, Any]:
    """Collect factual runtime information for a training artifact."""

    metadata: Dict[str, Any] = {
        "python_version": sys.version,
        "platform": platform.platform(),
        "pytorch_version": torch.__version__,
        "numpy_version": np.__version__,
        "device": str(device),
        "cuda_available": bool(torch.cuda.is_available()),
        "cuda_version": torch.version.cuda,
        "cpu_count": os.cpu_count(),
    }
    if torch.cuda.is_available():
        cuda_index = device.index if device.type == "cuda" and device.index is not None else torch.cuda.current_device()
        metadata["cuda_device_index"] = cuda_index
        metadata["cuda_device_name"] = torch.cuda.get_device_name(cuda_index)
    return metadata


def _metric_probabilities(model_output: torch.Tensor) -> torch.Tensor:
    """Convert the model's raw logits to probabilities for thresholded metrics."""

    return torch.sigmoid(model_output)


def _check_finite_gradients(model: nn.Module, epoch: int, batch_index: int) -> None:
    for parameter in model.parameters():
        if parameter.grad is not None and not torch.isfinite(parameter.grad).all():
            raise RuntimeError(
                f"Non-finite gradient detected at epoch {epoch}, batch {batch_index}."
            )


def run_training_epoch(
    model: nn.Module,
    train_loader: DataLoader,
    loss_fn: nn.Module,
    optimizer: torch.optim.Optimizer,
    device: torch.device,
    epoch_number: int,
    prediction_threshold: float = 0.5,
) -> Dict[str, float]:
    """Run one train epoch and return loss plus macro per-sample metrics."""

    model.train()
    if hasattr(train_loader.dataset, "set_epoch"):
        train_loader.dataset.set_epoch(epoch_number)
    accumulator = EpochMetricAccumulator()
    if len(train_loader) == 0:
        raise RuntimeError("Training DataLoader is empty")

    for batch_index, (images, masks, sample_ids) in enumerate(train_loader):
        images = images.to(device, non_blocking=True)
        masks = masks.to(device, non_blocking=True)
        optimizer.zero_grad(set_to_none=True)
        logits = model(images)
        loss = loss_fn(logits, masks)
        if not torch.isfinite(loss):
            raise RuntimeError(f"Non-finite loss at epoch {epoch_number}, batch {batch_index}")
        loss.backward()
        _check_finite_gradients(model, epoch_number, batch_index)
        optimizer.step()

        probabilities = _metric_probabilities(logits.detach())
        accumulator.update_loss(float(loss.item()), images.shape[0])
        accumulator.update_sample_metrics(
            evaluate_batch(probabilities, masks, list(sample_ids), prediction_threshold)
        )

    metrics = accumulator.get_aggregate_metrics()
    return {
        "train_loss": accumulator.get_average_loss(),
        "train_dice": metrics.get("mean_dice", 0.0),
        "train_iou": metrics.get("mean_iou", 0.0),
        "train_precision": metrics.get("mean_precision", 0.0),
        "train_recall": metrics.get("mean_recall", 0.0),
    }


def run_validation_epoch(
    model: nn.Module,
    val_loader: DataLoader,
    loss_fn: nn.Module,
    device: torch.device,
    prediction_threshold: float = 0.5,
) -> Dict[str, float]:
    """Run deterministic validation without gradients or parameter updates."""

    model.eval()
    accumulator = EpochMetricAccumulator()
    if len(val_loader) == 0:
        raise RuntimeError("Validation DataLoader is empty")
    with torch.no_grad():
        for images, masks, sample_ids in val_loader:
            images = images.to(device, non_blocking=True)
            masks = masks.to(device, non_blocking=True)
            logits = model(images)
            loss = loss_fn(logits, masks)
            if not torch.isfinite(loss):
                raise RuntimeError("Non-finite validation loss detected")
            probabilities = _metric_probabilities(logits)
            accumulator.update_loss(float(loss.item()), images.shape[0])
            accumulator.update_sample_metrics(
                evaluate_batch(probabilities, masks, list(sample_ids), prediction_threshold)
            )
    metrics = accumulator.get_aggregate_metrics()
    return {
        "val_loss": accumulator.get_average_loss(),
        "val_dice": metrics.get("mean_dice", 0.0),
        "val_iou": metrics.get("mean_iou", 0.0),
        "val_precision": metrics.get("mean_precision", 0.0),
        "val_recall": metrics.get("mean_recall", 0.0),
    }


def save_checkpoint(
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    epoch: int,
    val_dice: float,
    config: Dict[str, Any],
    checkpoint_path: str,
    scheduler: Optional[torch.optim.lr_scheduler.LRScheduler] = None,
    metadata: Optional[Dict[str, Any]] = None,
    best_metric_name: str = "val_dice",
    best_metric_value: Optional[float] = None,
    data_loader: Optional[DataLoader] = None,
) -> None:
    """Save weights, optimizer/scheduler state, configuration, and provenance."""

    checkpoint_file = Path(checkpoint_path)
    checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_data = {
        "checkpoint_version": "2.0",
        "epoch": epoch,
        "val_dice": float(val_dice),
        "best_metric_name": best_metric_name,
        "best_metric_value": float(best_metric_value if best_metric_value is not None else val_dice),
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "scheduler_state_dict": scheduler.state_dict() if scheduler is not None else None,
        "config": config,
        "metadata": metadata or {},
        "rng_state": _capture_rng_state(),
        "data_loader_generator_state": (
            data_loader.generator.get_state()
            if data_loader is not None and getattr(data_loader, "generator", None) is not None
            else None
        ),
    }
    temporary_file = checkpoint_file.with_name(f".{checkpoint_file.name}.tmp")
    try:
        torch.save(checkpoint_data, temporary_file)
        temporary_file.replace(checkpoint_file)
    except Exception as error:
        if temporary_file.exists():
            temporary_file.unlink()
        raise RuntimeError(f"Failed to save checkpoint to '{checkpoint_file}': {error}") from error


def load_checkpoint(
    checkpoint_path: str,
    model: nn.Module,
    device: torch.device,
    optimizer: Optional[torch.optim.Optimizer] = None,
    scheduler: Optional[torch.optim.lr_scheduler.LRScheduler] = None,
    data_loader: Optional[DataLoader] = None,
    restore_rng: bool = False,
) -> Dict[str, Any]:
    """Restore a checkpoint and optionally optimizer/scheduler state."""

    checkpoint_file = Path(checkpoint_path)
    if not checkpoint_file.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
    try:
        checkpoint = torch.load(checkpoint_file, map_location=device, weights_only=False)
    except Exception as error:
        raise RuntimeError(f"Failed to read checkpoint '{checkpoint_file}': {error}") from error
    if not isinstance(checkpoint, dict) or "model_state_dict" not in checkpoint:
        raise RuntimeError(
            f"Checkpoint '{checkpoint_file}' is malformed: model_state_dict is missing"
        )
    model.load_state_dict(checkpoint["model_state_dict"])
    if optimizer is not None and checkpoint.get("optimizer_state_dict"):
        optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        for state in optimizer.state.values():
            for key, value in state.items():
                if isinstance(value, torch.Tensor):
                    state[key] = value.to(device)
    if scheduler is not None and checkpoint.get("scheduler_state_dict"):
        scheduler.load_state_dict(checkpoint["scheduler_state_dict"])
    if restore_rng:
        _restore_rng_state(checkpoint.get("rng_state"))
        generator_state = checkpoint.get("data_loader_generator_state")
        if generator_state is not None:
            if data_loader is None or getattr(data_loader, "generator", None) is None:
                raise ValueError(
                    "Checkpoint contains a DataLoader generator state but no data_loader was provided"
                )
            data_loader.generator.set_state(generator_state)
    return {
        "epoch": checkpoint.get("epoch", 0),
        "val_dice": checkpoint.get("val_dice"),
        "best_metric_name": checkpoint.get("best_metric_name", "val_dice"),
        "best_metric_value": checkpoint.get("best_metric_value", checkpoint.get("val_dice")),
        "config": checkpoint.get("config", {}),
        "metadata": checkpoint.get("metadata", {}),
    }


def _capture_rng_state() -> Dict[str, Any]:
    """Capture all RNG streams used by the training process."""

    state: Dict[str, Any] = {
        "python": random.getstate(),
        "numpy": np.random.get_state(),
        "torch": torch.get_rng_state(),
    }
    if torch.cuda.is_available():
        state["cuda"] = torch.cuda.get_rng_state_all()
    return state


def _restore_rng_state(state: Optional[Dict[str, Any]]) -> None:
    """Restore RNG streams from a checkpoint when resuming training."""

    if not state:
        return
    random.setstate(state["python"])
    np.random.set_state(state["numpy"])
    torch.set_rng_state(state["torch"])
    if torch.cuda.is_available() and state.get("cuda") is not None:
        torch.cuda.set_rng_state_all(state["cuda"])


def _write_progress_log(
    config: Dict[str, Any],
    status: str,
    epoch_logs: List[Dict[str, Any]],
    checkpoint_path: str,
    latest_checkpoint_path: str,
    best_epoch: Optional[int],
    best_metric: float,
    best_val_metrics: Optional[Dict[str, float]],
    environment: Dict[str, Any],
) -> None:
    """Persist an interruption-safe structured progress log when configured."""

    output_path_value = config.get("output", {}).get("log_file")
    if not output_path_value:
        return
    output_path = Path(output_path_value)
    temporary_path = output_path.with_name(f".{output_path.name}.running.tmp")
    document = {
        "experiment_id": config.get("experiment_id", "unknown"),
        "specification": "SPEC-02-01",
        "status": status,
        "epoch_logs": epoch_logs,
        "best_epoch": best_epoch,
        "best_metric_name": "val_dice",
        "best_metric_value": None if best_epoch is None else round(best_metric, 7),
        "best_validation_metrics": best_val_metrics,
        "checkpoint_path": checkpoint_path,
        "latest_checkpoint_path": latest_checkpoint_path,
        "environment": environment,
        "test_evaluation": "NOT_RUN_BY_SPEC_02_01",
    }
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        temporary_path.replace(output_path)
    except (OSError, TypeError, ValueError) as error:
        # A logging mount failure must not discard a valid checkpoint.
        LOGGER.warning("Could not write progress log '%s': %s", output_path, error)
        if temporary_path.exists():
            temporary_path.unlink()


def _create_scheduler(
    optimizer: torch.optim.Optimizer,
    scheduler_config: Dict[str, Any],
) -> Optional[torch.optim.lr_scheduler.LRScheduler]:
    name = str(scheduler_config.get("name", "none")).lower()
    if name in {"", "none", "null"}:
        return None
    if name == "reducelronplateau":
        return torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer,
            mode=scheduler_config.get("mode", "max"),
            factor=float(scheduler_config.get("factor", 0.5)),
            patience=int(scheduler_config.get("patience", 3)),
            min_lr=float(scheduler_config.get("min_lr", 0.0)),
        )
    if name == "steplr":
        return torch.optim.lr_scheduler.StepLR(
            optimizer,
            step_size=int(scheduler_config.get("step_size", 10)),
            gamma=float(scheduler_config.get("gamma", 0.1)),
        )
    raise ValueError(f"Unsupported scheduler '{scheduler_config.get('name')}'")


def train_baseline_model(
    model: nn.Module,
    loss_fn: nn.Module,
    train_loader: DataLoader,
    val_loader: DataLoader,
    config: Dict[str, Any],
    device: torch.device,
) -> Dict[str, Any]:
    """Train using only train/validation loaders and select by validation Dice."""

    training_config = config.get("training", {})
    checkpoint_config = config.get("checkpointing", {})
    evaluation_config = config.get("evaluation", {})
    num_epochs = int(training_config.get("num_epochs", 20))
    if num_epochs <= 0:
        raise ValueError("num_epochs must be positive")
    seed = int(training_config.get("random_seed", 42))
    deterministic = bool(training_config.get("deterministic", True))
    set_random_seeds(seed, deterministic=deterministic)

    model.to(device)

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=float(training_config.get("learning_rate", 1e-3)),
        weight_decay=float(training_config.get("weight_decay", 1e-4)),
    )
    if training_config.get("optimizer", "Adam") != "Adam":
        raise ValueError("SPEC-02-01 supports the Adam optimizer only")
    scheduler = _create_scheduler(optimizer, training_config.get("scheduler", {}))
    checkpoint_metric = str(checkpoint_config.get("checkpoint_selection_metric", "val_dice"))
    checkpoint_mode = str(checkpoint_config.get("checkpoint_selection_mode", "max"))
    if checkpoint_metric != "val_dice" or checkpoint_mode != "max":
        raise ValueError("SPEC-02-01 checkpoint selection must use maximum validation Dice")
    checkpoint_path = str(
        Path(checkpoint_config.get("checkpoint_dir", "models/checkpoints"))
        / checkpoint_config.get("checkpoint_filename_template", "baseline_best.pth")
    )
    if checkpoint_config.get("save_latest_for_resume", True) is not True:
        raise ValueError("SPEC-02-01 requires save_latest_for_resume=true")
    if checkpoint_config.get("save_best_only", True) is not True:
        raise ValueError("SPEC-02-01 requires save_best_only=true")
    best_checkpoint_file = Path(checkpoint_path)
    latest_filename = checkpoint_config.get("latest_checkpoint_filename_template")
    if not latest_filename:
        latest_filename = best_checkpoint_file.name.replace("_best_", "_latest_").replace(
            "_best.", "_latest."
        )
    latest_checkpoint_path = str(best_checkpoint_file.parent / latest_filename)
    if Path(latest_checkpoint_path).resolve() == best_checkpoint_file.resolve():
        raise ValueError("Latest and best checkpoint paths must be different")
    environment = collect_environment_metadata(device)
    best_metric = -float("inf")
    best_epoch: Optional[int] = None
    best_val_metrics: Optional[Dict[str, float]] = None
    start_epoch = 1
    started_utc = datetime.now(timezone.utc).isoformat()

    resume_path = training_config.get("resume_checkpoint")
    if resume_path:
        resume_metadata = load_checkpoint(
            str(resume_path),
            model,
            device,
            optimizer=optimizer,
            scheduler=scheduler,
            data_loader=train_loader,
            restore_rng=True,
        )
        start_epoch = int(resume_metadata["epoch"]) + 1
        resume_best = resume_metadata.get("best_metric_value")
        if resume_best is not None:
            best_metric = float(resume_best)
        best_epoch_value = resume_metadata.get("metadata", {}).get("best_epoch")
        best_epoch = int(best_epoch_value) if best_epoch_value is not None else int(resume_metadata["epoch"])
        resume_best_metrics = resume_metadata.get("metadata", {}).get("best_validation_metrics")
        best_val_metrics = dict(resume_best_metrics) if resume_best_metrics else None
        resume_started_utc = resume_metadata.get("metadata", {}).get("run_started_utc")
        if isinstance(resume_started_utc, str) and resume_started_utc:
            started_utc = resume_started_utc
        LOGGER.info("Resuming from checkpoint %s at epoch %d", resume_path, start_epoch)
    if start_epoch > num_epochs:
        raise ValueError(
            f"Resume checkpoint is at epoch {start_epoch - 1}, but num_epochs={num_epochs}; "
            "increase num_epochs before resuming"
        )

    epoch_logs: List[Dict[str, Any]] = []
    if resume_path:
        saved_epoch_logs = resume_metadata.get("metadata", {}).get("epoch_logs", [])
        if isinstance(saved_epoch_logs, list):
            epoch_logs.extend(item for item in saved_epoch_logs if isinstance(item, dict))
    _write_progress_log(
        config,
        "RUNNING",
        epoch_logs,
        checkpoint_path,
        latest_checkpoint_path,
        best_epoch,
        best_metric,
        best_val_metrics,
        environment,
    )
    start_time = time.monotonic()
    last_completed_epoch = start_epoch - 1
    for epoch in range(start_epoch, num_epochs + 1):
        epoch_start = time.monotonic()
        train_metrics = run_training_epoch(
            model, train_loader, loss_fn, optimizer, device, epoch,
            evaluation_config.get("prediction_threshold", 0.5),
        )
        val_metrics = run_validation_epoch(
            model, val_loader, loss_fn, device,
            evaluation_config.get("prediction_threshold", 0.5),
        )
        if isinstance(scheduler, torch.optim.lr_scheduler.ReduceLROnPlateau):
            scheduler.step(val_metrics["val_dice"])
        elif scheduler is not None:
            scheduler.step()
        epoch_log = {
            "epoch": epoch,
            **{key: round(float(value), 7) for key, value in train_metrics.items()},
            **{key: round(float(value), 7) for key, value in val_metrics.items()},
            "learning_rate": float(optimizer.param_groups[0]["lr"]),
            "epoch_duration_seconds": round(time.monotonic() - epoch_start, 3),
        }
        epoch_logs.append(epoch_log)
        last_completed_epoch = epoch
        LOGGER.info(
            "epoch=%d train_loss=%.5f val_loss=%.5f val_dice=%.5f val_iou=%.5f",
            epoch,
            train_metrics["train_loss"],
            val_metrics["val_loss"],
            val_metrics["val_dice"],
            val_metrics["val_iou"],
        )
        current_metric = float(val_metrics["val_dice"])
        if current_metric > best_metric or not best_checkpoint_file.exists():
            best_metric = current_metric
            best_epoch = epoch
            best_val_metrics = dict(val_metrics)
            save_checkpoint(
                model=model,
                optimizer=optimizer,
                epoch=epoch,
                val_dice=current_metric,
                config=config,
                checkpoint_path=checkpoint_path,
                scheduler=scheduler,
                metadata={
                    "environment": environment,
                    "best_validation_metrics": best_val_metrics,
                    "best_epoch": best_epoch,
                    "epoch_logs": epoch_logs,
                    "run_started_utc": started_utc,
                    "run_status": "RUNNING",
                },
                best_metric_name=checkpoint_metric,
                best_metric_value=best_metric,
                data_loader=train_loader,
            )

        # The latest checkpoint is the resume point.  It is intentionally
        # separate from the validation-selected best checkpoint so an
        # interruption never resumes from an older, better-scoring epoch.
        save_checkpoint(
            model=model,
            optimizer=optimizer,
            epoch=epoch,
            val_dice=float(val_metrics["val_dice"]),
            config=config,
            checkpoint_path=latest_checkpoint_path,
            scheduler=scheduler,
            metadata={
                "environment": environment,
                "best_validation_metrics": best_val_metrics,
                "best_epoch": best_epoch,
                "epoch_logs": epoch_logs,
                "run_started_utc": started_utc,
                "run_status": "RUNNING",
            },
            best_metric_name=checkpoint_metric,
            best_metric_value=best_metric,
            data_loader=train_loader,
        )
        _write_progress_log(
            config,
            "RUNNING",
            epoch_logs,
            checkpoint_path,
            latest_checkpoint_path,
            best_epoch,
            best_metric,
            best_val_metrics,
            environment,
        )

    total_duration = time.monotonic() - start_time
    if best_epoch is None or not Path(checkpoint_path).exists():
        raise RuntimeError("Training completed without producing a best validation checkpoint")
    training_result = {
        "experiment_id": config.get("experiment_id", "unknown"),
        "status": "COMPLETED_SPEC_02_01",
        "started_utc": started_utc,
        "total_epochs_completed": last_completed_epoch,
        "best_epoch": best_epoch,
        "best_metric_name": checkpoint_metric,
        "best_metric_value": round(best_metric, 7),
        "best_validation_metrics": best_val_metrics,
        "checkpoint_path": checkpoint_path,
        "latest_checkpoint_path": latest_checkpoint_path,
        "resumed_from": str(resume_path) if resume_path else None,
        "total_training_time_seconds": round(total_duration, 3),
        "environment": environment,
        "epoch_logs": epoch_logs,
        "test_evaluation": "NOT_RUN_BY_SPEC_02_01",
    }
    _write_progress_log(
        config,
        "COMPLETED_SPEC_02_01",
        epoch_logs,
        checkpoint_path,
        latest_checkpoint_path,
        best_epoch,
        best_metric,
        best_val_metrics,
        environment,
    )
    return training_result
