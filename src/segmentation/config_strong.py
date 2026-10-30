"""Strict validation for the SPEC-02-03 pretrained-encoder configuration.

The SPEC-02-01 validator in ``config.py`` is intentionally left unchanged so
the historical baseline configuration keeps its exact contract.
"""

from __future__ import annotations

from typing import Any

from src.segmentation.augmentation import validate_augmentation_config
from src.segmentation.config import _integer, _number, _probability
from src.segmentation.resnet_unet import SUPPORTED_ENCODERS

REQUIRED_SECTIONS = ("data", "preprocessing", "augmentation", "model", "loss", "training",
                     "checkpointing", "evaluation", "device", "output")
REQUIRED_OUTPUTS = ("log_file", "postprocessing_tuning", "test_evaluation", "external_evaluation",
                    "experiment_record", "figure_dir")


def validate_strong_config(config: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(config, dict):
        raise ValueError("Configuration must be a JSON object")
    if config.get("specification") != "SPEC-02-03":
        raise ValueError("specification must be 'SPEC-02-03'")
    for section in REQUIRED_SECTIONS:
        if not isinstance(config.get(section), dict):
            raise ValueError(f"Configuration field '{section}' must be an object")
    if not isinstance(config.get("experiment_id"), str) or not config["experiment_id"].strip():
        raise ValueError("experiment_id must be a non-empty string")

    data = config["data"]
    if data.get("dataset_name") != "FUSeg2021" or data.get("dataset_source_type") != "real":
        raise ValueError("SPEC-02-03 must target real FUSeg2021 data")
    if data.get("required_manifest_version") != "fuseg2021-heldout-v1":
        raise ValueError("SPEC-02-03 requires the held-out manifest (fuseg2021-heldout-v1)")
    if not isinstance(data.get("manifest_path"), str) or not data["manifest_path"].strip():
        raise ValueError("data.manifest_path must be a non-empty string")

    preprocessing = config["preprocessing"]
    for dimension in ("input_height", "input_width"):
        value = _integer(preprocessing.get(dimension), f"preprocessing.{dimension}", 64)
        if value % 32:
            raise ValueError(f"preprocessing.{dimension} must be divisible by 32")
    for name in ("normalize_mean", "normalize_std"):
        values = preprocessing.get(name)
        if not isinstance(values, list) or len(values) != 3:
            raise ValueError(f"preprocessing.{name} must contain three values")
    if any(_number(value, "preprocessing.normalize_std", strict=True) <= 0 for value in preprocessing["normalize_std"]):
        raise ValueError("preprocessing.normalize_std must be positive")

    augmentation = dict(config["augmentation"])
    if augmentation.pop("validation_and_test", "none") != "none":
        raise ValueError("Validation and test must not be augmented")
    validate_augmentation_config(augmentation)

    model = config["model"]
    if model.get("architecture") != "ResNetUNet":
        raise ValueError("SPEC-02-03 requires ResNetUNet")
    if model.get("encoder_name") not in SUPPORTED_ENCODERS:
        raise ValueError(f"model.encoder_name must be one of {sorted(SUPPORTED_ENCODERS)}")
    if type(model.get("pretrained")) is not bool:
        raise ValueError("model.pretrained must be boolean")
    if model.get("num_classes", 1) != 1:
        raise ValueError("SPEC-02-03 is binary segmentation (num_classes=1)")

    loss = config["loss"]
    if loss.get("name") != "BCEDiceLoss":
        raise ValueError("SPEC-02-03 uses BCEDiceLoss")

    training = config["training"]
    _integer(training.get("num_epochs"), "training.num_epochs")
    _integer(training.get("batch_size"), "training.batch_size", 2)
    _integer(training.get("num_workers", 0), "training.num_workers", 0)
    if training.get("optimizer") != "AdamW":
        raise ValueError("SPEC-02-03 uses AdamW")
    _number(training.get("learning_rate"), "training.learning_rate", strict=True)
    _number(training.get("encoder_lr_multiplier", 1.0), "training.encoder_lr_multiplier", strict=True)
    _number(training.get("weight_decay", 0), "training.weight_decay")
    scheduler = training.get("scheduler", {})
    if scheduler.get("name") != "warmup_cosine":
        raise ValueError("SPEC-02-03 uses the warmup_cosine scheduler")
    warmup = _integer(scheduler.get("warmup_epochs", 3), "scheduler.warmup_epochs", 0)
    if warmup >= training["num_epochs"]:
        raise ValueError("scheduler.warmup_epochs must be smaller than num_epochs")
    _probability(scheduler.get("min_lr_ratio", 0.01), "scheduler.min_lr_ratio")
    if training.get("ema_decay") is not None:
        decay = _probability(training["ema_decay"], "training.ema_decay")
        if decay in (0.0, 1.0):
            raise ValueError("training.ema_decay must be strictly between 0 and 1")
    if training.get("gradient_clip_norm") is not None:
        _number(training["gradient_clip_norm"], "training.gradient_clip_norm", strict=True)
    if training.get("early_stopping_patience") is not None:
        _integer(training["early_stopping_patience"], "training.early_stopping_patience")
    if training.get("persistent_workers") and training.get("num_workers", 0) == 0:
        raise ValueError("persistent_workers requires num_workers > 0")

    checkpointing = config["checkpointing"]
    if checkpointing.get("checkpoint_selection_metric") != "val_dice" or checkpointing.get(
        "checkpoint_selection_mode"
    ) != "max":
        raise ValueError("Checkpoint selection must maximize internal-validation Dice")
    for key in ("checkpoint_dir", "checkpoint_filename_template", "latest_checkpoint_filename_template"):
        if not isinstance(checkpointing.get(key), str) or not checkpointing[key]:
            raise ValueError(f"checkpointing.{key} must be a non-empty string")

    evaluation = config["evaluation"]
    _probability(evaluation.get("selection_threshold", 0.5), "evaluation.selection_threshold")
    if evaluation.get("tune_postprocessing_on") != "val":
        raise ValueError("Post-processing must be tuned on the internal validation split only")
    for threshold in evaluation.get("threshold_grid", []):
        _probability(threshold, "evaluation.threshold_grid")
    for area in evaluation.get("min_component_area_grid", []):
        _integer(area, "evaluation.min_component_area_grid", 0)

    for name in REQUIRED_OUTPUTS:
        if not isinstance(config["output"].get(name), str) or not config["output"][name].strip():
            raise ValueError(f"output.{name} must be a non-empty string")
    return config
