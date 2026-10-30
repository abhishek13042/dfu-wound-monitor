"""SPEC-02-03 training engine: AdamW, warmup + cosine LR, AMP, gradient
clipping, EMA weights and early stopping.

Model selection uses the internal validation split only (macro Dice at the
network input size, threshold 0.5).  The held-out test split is never seen
here.  The best checkpoint stores the EMA weights when EMA is enabled, because
those are the weights that were validated.

Reproducibility: seeds are fixed and recorded, but ``deterministic`` is false
by default because cuDNN autotuning and AMP give a large speed-up.  Repeated
runs therefore agree closely but not bit-for-bit; this is documented in the
experiment record.
"""

from __future__ import annotations

import json
import logging
import math
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import torch
import torch.nn as nn
from torch.optim.swa_utils import AveragedModel
from torch.utils.data import DataLoader

from src.segmentation.metrics import EpochMetricAccumulator, evaluate_batch
from src.segmentation.trainer import (
    collect_environment_metadata,
    load_checkpoint,
    run_validation_epoch,
    save_checkpoint,
    set_random_seeds,
)

LOGGER = logging.getLogger(__name__)
SPECIFICATION = "SPEC-02-03"


def build_optimizer(model: nn.Module, training: dict[str, Any]) -> torch.optim.Optimizer:
    """AdamW with an optional lower learning rate for the pretrained encoder."""

    learning_rate = float(training["learning_rate"])
    weight_decay = float(training.get("weight_decay", 1e-4))
    multiplier = float(training.get("encoder_lr_multiplier", 1.0))
    if hasattr(model, "encoder_parameters") and multiplier != 1.0:
        split_model = cast(Any, model)
        groups = [
            {"params": split_model.encoder_parameters(), "lr": learning_rate * multiplier},
            {"params": split_model.decoder_parameters(), "lr": learning_rate},
        ]
    else:
        groups = [{"params": list(model.parameters()), "lr": learning_rate}]
    return torch.optim.AdamW(groups, lr=learning_rate, weight_decay=weight_decay)


def build_warmup_cosine_scheduler(
    optimizer: torch.optim.Optimizer,
    total_steps: int,
    warmup_steps: int,
    min_lr_ratio: float,
) -> torch.optim.lr_scheduler.LambdaLR:
    """Linear warmup to the base LR, then cosine decay to ``min_lr_ratio``."""

    if total_steps <= 0 or warmup_steps < 0 or warmup_steps >= total_steps:
        raise ValueError("Require 0 <= warmup_steps < total_steps")

    def factor(step: int) -> float:
        if step < warmup_steps:
            return (step + 1) / warmup_steps
        progress = min(1.0, (step - warmup_steps) / max(1, total_steps - warmup_steps))
        return min_lr_ratio + (1.0 - min_lr_ratio) * 0.5 * (1.0 + math.cos(math.pi * progress))

    return torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda=factor)


def build_ema(model: nn.Module, decay: float) -> AveragedModel:
    """EMA of parameters and buffers with a warmup on the decay.

    ``decay_t = min(decay, (1 + n) / (10 + n))`` lets the average track the
    rapidly changing early weights, so internal-validation selection is
    meaningful from the first epochs instead of scoring near-initial weights.
    """

    def average(averaged: torch.Tensor, current: torch.Tensor, num_averaged: torch.Tensor | int) -> torch.Tensor:
        step = float(num_averaged)
        decay_t = min(decay, (1.0 + step) / (10.0 + step))
        if not averaged.is_floating_point():
            return current
        return averaged * decay_t + current * (1.0 - decay_t)

    return AveragedModel(model, avg_fn=average, use_buffers=True)


def _write_log(path_value: str | None, document: dict[str, Any]) -> None:
    if not path_value:
        return
    path = Path(path_value)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    except (OSError, TypeError, ValueError) as error:
        LOGGER.warning("Could not write progress log '%s': %s", path, error)


def train_strong_model(
    model: nn.Module,
    loss_fn: nn.Module,
    train_loader: DataLoader,
    val_loader: DataLoader,
    config: dict[str, Any],
    device: torch.device,
) -> dict[str, Any]:
    """Train with internal-validation model selection; returns a run summary."""

    training = config["training"]
    checkpointing = config["checkpointing"]
    num_epochs = int(training["num_epochs"])
    seed = int(training.get("random_seed", 42))
    set_random_seeds(seed, deterministic=bool(training.get("deterministic", False)))
    model.to(device)

    use_amp = bool(training.get("mixed_precision", True)) and device.type == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    optimizer = build_optimizer(model, training)
    steps_per_epoch = len(train_loader)
    if steps_per_epoch == 0:
        raise RuntimeError("Training DataLoader is empty")
    scheduler_cfg = training.get("scheduler", {})
    scheduler = build_warmup_cosine_scheduler(
        optimizer,
        total_steps=num_epochs * steps_per_epoch,
        warmup_steps=int(scheduler_cfg.get("warmup_epochs", 3)) * steps_per_epoch,
        min_lr_ratio=float(scheduler_cfg.get("min_lr_ratio", 0.01)),
    )
    ema_decay = training.get("ema_decay")
    ema = build_ema(model, float(ema_decay)) if ema_decay else None
    gradient_clip = training.get("gradient_clip_norm")
    patience = training.get("early_stopping_patience")
    threshold = float(config["evaluation"].get("selection_threshold", 0.5))

    checkpoint_dir = Path(checkpointing["checkpoint_dir"])
    best_path = checkpoint_dir / checkpointing["checkpoint_filename_template"]
    latest_path = checkpoint_dir / checkpointing["latest_checkpoint_filename_template"]
    if best_path.resolve() == latest_path.resolve():
        raise ValueError("Latest and best checkpoint paths must be different")
    environment = collect_environment_metadata(device)
    environment["mixed_precision"] = use_amp

    start_epoch = 1
    best_metric = -float("inf")
    best_epoch: int | None = None
    best_val_metrics: dict[str, float] | None = None
    epoch_logs: list[dict[str, Any]] = []
    started_utc = datetime.now(UTC).isoformat()
    resume_path = training.get("resume_checkpoint")
    if resume_path:
        resumed = load_checkpoint(
            str(resume_path), model, device, optimizer=optimizer, scheduler=scheduler,
            data_loader=train_loader, restore_rng=True,
        )
        metadata = resumed.get("metadata", {})
        start_epoch = int(resumed["epoch"]) + 1
        best_metric = float(resumed.get("best_metric_value") or -float("inf"))
        best_epoch = metadata.get("best_epoch")
        best_val_metrics = metadata.get("best_validation_metrics")
        epoch_logs = list(metadata.get("epoch_logs", []))
        started_utc = metadata.get("run_started_utc", started_utc)
        if ema is not None and metadata.get("ema_state_dict"):
            ema.load_state_dict(metadata["ema_state_dict"])
        if metadata.get("scaler_state_dict"):
            scaler.load_state_dict(metadata["scaler_state_dict"])
        LOGGER.info("Resuming %s from epoch %d", resume_path, start_epoch)

    def progress(status: str) -> dict[str, Any]:
        document = {
            "experiment_id": config["experiment_id"],
            "specification": SPECIFICATION,
            "status": status,
            "selection_split": "internal_val",
            "best_epoch": best_epoch,
            "best_metric_name": "val_dice",
            "best_metric_value": None if best_epoch is None else round(best_metric, 7),
            "best_validation_metrics": best_val_metrics,
            "checkpoint_path": str(best_path),
            "latest_checkpoint_path": str(latest_path),
            "environment": environment,
            "epoch_logs": epoch_logs,
            "test_evaluation": "NOT_RUN_DURING_TRAINING",
        }
        _write_log(config["output"].get("log_file"), document)
        return document

    epochs_without_improvement = 0
    run_start = time.monotonic()
    for epoch in range(start_epoch, num_epochs + 1):
        epoch_start = time.monotonic()
        model.train()
        if hasattr(train_loader.dataset, "set_epoch"):
            train_loader.dataset.set_epoch(epoch)
        accumulator = EpochMetricAccumulator()
        for batch_index, (images, masks, sample_ids) in enumerate(train_loader):
            images = images.to(device, non_blocking=True)
            masks = masks.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=use_amp):
                logits = model(images)
            loss = loss_fn(logits.float(), masks)
            if not torch.isfinite(loss):
                raise RuntimeError(f"Non-finite loss at epoch {epoch}, batch {batch_index}")
            scaler.scale(loss).backward()
            if gradient_clip:
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), float(gradient_clip))
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()
            if ema is not None:
                ema.update_parameters(model)
            accumulator.update_loss(float(loss.item()), images.shape[0])
            accumulator.update_sample_metrics(
                evaluate_batch(torch.sigmoid(logits.detach().float()), masks, list(sample_ids), threshold)
            )

        eval_model = ema.module if ema is not None else model
        val_metrics = run_validation_epoch(eval_model, val_loader, loss_fn, device, threshold)
        train_metrics = accumulator.get_aggregate_metrics()
        epoch_log = {
            "epoch": epoch,
            "train_loss": round(accumulator.get_average_loss(), 7),
            "train_dice": round(train_metrics.get("mean_dice", 0.0), 7),
            **{key: round(float(value), 7) for key, value in val_metrics.items()},
            "learning_rate": float(optimizer.param_groups[-1]["lr"]),
            "epoch_duration_seconds": round(time.monotonic() - epoch_start, 3),
        }
        epoch_logs.append(epoch_log)
        LOGGER.info("epoch=%d train_loss=%.4f val_loss=%.4f val_dice=%.4f", epoch,
                    epoch_log["train_loss"], val_metrics["val_loss"], val_metrics["val_dice"])

        metadata = {
            "environment": environment,
            "best_epoch": best_epoch,
            "best_validation_metrics": best_val_metrics,
            "epoch_logs": epoch_logs,
            "run_started_utc": started_utc,
            "weights": "ema" if ema is not None else "raw",
        }
        current = float(val_metrics["val_dice"])
        if current > best_metric:
            best_metric, best_epoch, best_val_metrics = current, epoch, dict(val_metrics)
            epochs_without_improvement = 0
            metadata.update(best_epoch=best_epoch, best_validation_metrics=best_val_metrics)
            save_checkpoint(eval_model, optimizer, epoch, current, config, str(best_path),
                            scheduler=scheduler, metadata=metadata, best_metric_value=best_metric)
        else:
            epochs_without_improvement += 1
        resume_metadata = {
            **metadata,
            "ema_state_dict": ema.state_dict() if ema is not None else None,
            "scaler_state_dict": scaler.state_dict(),
        }
        save_checkpoint(model, optimizer, epoch, current, config, str(latest_path), scheduler=scheduler,
                        metadata=resume_metadata, best_metric_value=best_metric, data_loader=train_loader)
        progress("RUNNING")
        if patience and epochs_without_improvement >= int(patience):
            LOGGER.info("Early stopping at epoch %d (patience %s)", epoch, patience)
            break

    if best_epoch is None or not best_path.exists():
        raise RuntimeError("Training finished without a best validation checkpoint")
    summary = progress("COMPLETED_TRAINING")
    summary["total_training_time_seconds"] = round(time.monotonic() - run_start, 3)
    summary["total_epochs_completed"] = epoch_logs[-1]["epoch"] if epoch_logs else 0
    return summary
