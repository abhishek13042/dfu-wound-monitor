"""Strict validation for the single SPEC-02-01 FUSeg2021 baseline."""

from __future__ import annotations

import math
from typing import Any


def _number(value: Any, name: str, minimum: float = 0, *, strict: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    if not math.isfinite(value) or value < minimum or (strict and value == minimum):
        raise ValueError(f"{name} must be finite and {'greater than' if strict else 'at least'} {minimum}")
    return float(value)


def _integer(value: Any, name: str, minimum: int = 1) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _probability(value: Any, name: str) -> float:
    result = _number(value, name)
    if result > 1:
        raise ValueError(f"{name} must be in [0, 1]")
    return result


def validate_training_config(config: dict[str, Any]) -> dict[str, Any]:
    """Reject unsupported settings instead of silently ignoring them.

    The model uses four pooling levels; a minimum resolution of 32 also keeps
    BatchNorm valid for a final training batch containing just one image.
    """
    if not isinstance(config, dict):
        raise ValueError("Training configuration must be a JSON object")
    for section in ("data", "preprocessing", "augmentation", "model", "loss", "training",
                    "checkpointing", "evaluation", "device", "output"):
        if not isinstance(config.get(section), dict):
            raise ValueError(f"Configuration field '{section}' must be an object")
    if not isinstance(config.get("experiment_id"), str) or not config["experiment_id"].strip():
        raise ValueError("experiment_id must be a non-empty string")

    data = config["data"]
    if data.get("dataset_name") != "FUSeg2021" or data.get("dataset_source_type") != "real":
        raise ValueError("SPEC-02-01 configuration must target real FUSeg2021 data")
    if data.get("annotation_type") != "wound_segmentation":
        raise ValueError("SPEC-02-01 requires wound_segmentation annotations")
    if not isinstance(data.get("manifest_path"), str) or not data["manifest_path"].strip():
        raise ValueError("data.manifest_path must be a non-empty string")
    data_root = data.get("data_root")
    if data_root is not None and (not isinstance(data_root, str) or not data_root.strip()):
        raise ValueError("data.data_root must be null or a non-empty string")

    preprocessing = config["preprocessing"]
    for dimension in ("input_height", "input_width"):
        _integer(preprocessing.get(dimension), f"preprocessing.{dimension}", 32)
    for name in ("normalize_mean", "normalize_std"):
        values = preprocessing.get(name)
        if not isinstance(values, list) or len(values) != 3:
            raise ValueError(f"preprocessing.{name} must contain three values")
        for value in values:
            _number(value, f"preprocessing.{name}", -float("inf") if name == "normalize_mean" else 0,
                    strict=name == "normalize_std")
    threshold = _integer(preprocessing.get("mask_threshold", 128), "preprocessing.mask_threshold")
    if threshold > 255:
        raise ValueError("preprocessing.mask_threshold must be in [1, 255]")
    if preprocessing.get("source_mask_values", [0, 255]) != [0, 255]:
        raise ValueError("FUSeg2021 source_mask_values must be [0, 255]")
    for name, expected in (("image_resize", "bilinear"), ("mask_resize", "nearest")):
        if preprocessing.get(name, expected) != expected:
            raise ValueError(f"preprocessing.{name} must be '{expected}'")

    augmentation = config["augmentation"]
    for name in ("train_horizontal_flip_prob", "train_vertical_flip_prob"):
        _probability(augmentation.get(name, 0), f"augmentation.{name}")
    if augmentation.get("validation_and_test", "none") != "none":
        raise ValueError("Validation preprocessing must have no augmentation")

    model = config["model"]
    if model.get("architecture") != "LightweightUNet":
        raise ValueError("SPEC-02-01 requires LightweightUNet")
    channels = model.get("encoder_channels")
    if not isinstance(channels, list) or len(channels) != 4:
        raise ValueError("model.encoder_channels must contain four positive integers")
    for channel in channels:
        _integer(channel, "model.encoder_channels")
    if model.get("num_classes", 1) != 1:
        raise ValueError("SPEC-02-01 requires one binary output channel")
    if model.get("pretrained_weights") is not None or model.get("freeze_encoder", False):
        raise ValueError("SPEC-02-01 uses random initialization and a trainable encoder")

    loss = config["loss"]
    if loss.get("name") != "BCEDiceLoss":
        raise ValueError("SPEC-02-01 requires BCEDiceLoss")
    weights = [_number(loss.get(name, 0.5), f"loss.{name}") for name in ("bce_weight", "dice_weight")]
    if sum(weights) <= 0:
        raise ValueError("loss weights cannot both be zero")
    _number(loss.get("epsilon", 1e-6), "loss.epsilon", strict=True)

    training = config["training"]
    _integer(training.get("num_epochs"), "training.num_epochs")
    _integer(training.get("batch_size"), "training.batch_size")
    _integer(training.get("num_workers", 0), "training.num_workers", 0)
    seed = _integer(training.get("random_seed", 42), "training.random_seed", 0)
    if seed >= 2**32:
        raise ValueError("training.random_seed must be less than 2**32")
    for flag in ("deterministic", "pin_memory", "persistent_workers"):
        if type(training.get(flag, False)) is not bool:
            raise ValueError(f"training.{flag} must be boolean")
    if training.get("persistent_workers") and training.get("num_workers", 0) == 0:
        raise ValueError("persistent_workers requires num_workers > 0")
    resume_checkpoint = training.get("resume_checkpoint")
    if resume_checkpoint is not None and (
        not isinstance(resume_checkpoint, str) or not resume_checkpoint.strip()
    ):
        raise ValueError("training.resume_checkpoint must be null or a non-empty string")
    if training.get("optimizer", "Adam") != "Adam":
        raise ValueError("SPEC-02-01 supports Adam only")
    _number(training.get("learning_rate", 1e-3), "training.learning_rate", strict=True)
    _number(training.get("weight_decay", 0), "training.weight_decay")
    scheduler = training.get("scheduler", {})
    if not isinstance(scheduler, dict):
        raise ValueError("training.scheduler must be an object")
    scheduler_name = str(scheduler.get("name", "none")).lower()
    if scheduler_name not in {"none", "reducelronplateau", "steplr"}:
        raise ValueError(f"Unsupported scheduler '{scheduler_name}'")
    if scheduler_name == "reducelronplateau":
        if scheduler.get("mode", "max") != "max":
            raise ValueError("ReduceLROnPlateau must monitor validation Dice in max mode")
        factor = _probability(scheduler.get("factor", 0.5), "scheduler.factor")
        if factor in (0, 1):
            raise ValueError("scheduler.factor must be between 0 and 1")
        _integer(scheduler.get("patience", 3), "scheduler.patience", 0)
        _number(scheduler.get("min_lr", 0), "scheduler.min_lr")
    if scheduler_name == "steplr":
        _integer(scheduler.get("step_size", 10), "scheduler.step_size")
        gamma = _probability(scheduler.get("gamma", 0.1), "scheduler.gamma")
        if gamma == 0:
            raise ValueError("scheduler.gamma must be positive")

    checkpointing = config["checkpointing"]
    if not isinstance(checkpointing.get("checkpoint_dir", "models/checkpoints"), str):
        raise ValueError("checkpointing.checkpoint_dir must be a string")
    if checkpointing.get("checkpoint_selection_metric", "val_dice") != "val_dice":
        raise ValueError("SPEC-02-01 selects checkpoints using validation Dice")
    if checkpointing.get("checkpoint_selection_mode", "max") != "max":
        raise ValueError("SPEC-02-01 selects the maximum validation Dice")
    if type(checkpointing.get("save_best_only", True)) is not bool:
        raise ValueError("checkpointing.save_best_only must be boolean")
    if checkpointing.get("save_best_only", True) is not True:
        raise ValueError("SPEC-02-01 requires save_best_only=true")
    if type(checkpointing.get("save_latest_for_resume", True)) is not bool:
        raise ValueError("checkpointing.save_latest_for_resume must be boolean")
    for filename_key in ("checkpoint_filename_template", "latest_checkpoint_filename_template"):
        name = checkpointing.get(filename_key)
        if name is not None and (not isinstance(name, str) or not name or "/" in name or "\\" in name):
            raise ValueError(f"checkpointing.{filename_key} must be a filename")
    _probability(config["evaluation"].get("prediction_threshold", 0.5), "evaluation.prediction_threshold")
    for name in ("preferred", "fallback"):
        device = config["device"].get(name)
        if not isinstance(device, str) or not device:
            raise ValueError(f"device.{name} must be a non-empty string")
    for name in ("log_file", "model_metadata", "sanity_report", "sanity_panel", "experiment_record",
                 "prediction_output_dir"):
        if not isinstance(config["output"].get(name), str) or not config["output"][name].strip():
            raise ValueError(f"output.{name} must be a non-empty string")
    if "representative_prediction_count" in config["output"]:
        _integer(
            config["output"]["representative_prediction_count"],
            "output.representative_prediction_count",
        )
    return config
