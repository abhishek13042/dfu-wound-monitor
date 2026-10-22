"""Run SPEC-02-01's real FUSeg2021 train/validation baseline.

The script does not construct a test loader because the public FUSeg2021 test
images have no usable ground-truth masks.  Test prediction/evaluation belongs
to a later specification and is deliberately not performed here.
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.data.splitting import validate_manifest_for_training  # noqa: E402
from src.segmentation.dataset import create_dataloaders  # noqa: E402
from src.segmentation.config import validate_training_config  # noqa: E402
from src.segmentation.model import (  # noqa: E402
    BCEDiceLoss,
    LightweightUNet,
    count_model_parameters,
    verify_model_forward_pass,
)
from src.segmentation.trainer import (  # noqa: E402
    collect_environment_metadata,
    load_checkpoint,
    select_device,
    set_random_seeds,
    train_baseline_model,
)


LOGGER = logging.getLogger("spec_02_01")


def load_config(config_path: str) -> Dict[str, Any]:
    """Load and validate a JSON training configuration."""

    path = Path(config_path)
    if not path.exists() and not path.is_absolute():
        path = project_root / path
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with path.open("r", encoding="utf-8") as config_handle:
        config = json.load(config_handle)
    validate_training_config(config)
    return config


def resolve_runtime_path(path_value: str) -> Path:
    """Resolve a configured artifact/data path from the project root."""

    path = Path(path_value)
    return path if path.is_absolute() else project_root / path


def _write_json(path: str | Path, document: Dict[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _display_image(image: torch.Tensor, mean: List[float], std: List[float]) -> np.ndarray:
    array = image.detach().cpu().numpy()
    mean_array = np.asarray(mean, dtype=np.float32).reshape(3, 1, 1)
    std_array = np.asarray(std, dtype=np.float32).reshape(3, 1, 1)
    return np.transpose(np.clip(array * std_array + mean_array, 0.0, 1.0), (1, 2, 0))


def run_sanity_checks(
    train_loader: torch.utils.data.DataLoader,
    val_loader: torch.utils.data.DataLoader,
    model: LightweightUNet,
    loss_fn: BCEDiceLoss,
    device: torch.device,
    config: Dict[str, Any],
    output_path: str,
) -> Dict[str, Any]:
    """Run real-sample, augmentation, forward, gradient, and checkpoint checks."""

    preprocessing = config["preprocessing"]
    model_state_before = copy.deepcopy(model.state_dict())
    model_was_training = model.training
    loader_generator_states = {
        id(loader): loader.generator.get_state().clone()
        for loader in (train_loader, val_loader)
        if getattr(loader, "generator", None) is not None
    }
    images, masks, sample_ids = next(iter(train_loader))
    if images.shape[1:] != (3, preprocessing["input_height"], preprocessing["input_width"]):
        raise RuntimeError(f"Unexpected real training image shape: {tuple(images.shape)}")
    if masks.shape[1:] != (1, preprocessing["input_height"], preprocessing["input_width"]):
        raise RuntimeError(f"Unexpected real training mask shape: {tuple(masks.shape)}")
    if not torch.all((masks == 0) | (masks == 1)):
        raise RuntimeError("Real training batch contains a non-binary mask")

    val_images_a, val_masks_a, val_ids_a = next(iter(val_loader))
    val_images_b, val_masks_b, val_ids_b = next(iter(val_loader))
    deterministic_val = bool(
        torch.equal(val_images_a, val_images_b)
        and torch.equal(val_masks_a, val_masks_b)
        and list(val_ids_a) == list(val_ids_b)
    )
    if not deterministic_val:
        raise RuntimeError("Validation preprocessing is not deterministic")

    # Model forward and one real batch backward pass.
    model.train()
    model.zero_grad(set_to_none=True)
    logits = model(images.to(device))
    batch_loss = loss_fn(logits, masks.to(device))
    if not torch.isfinite(batch_loss):
        raise RuntimeError("Sanity-check loss is non-finite")
    batch_loss.backward()
    finite_gradients = all(
        parameter.grad is None or bool(torch.isfinite(parameter.grad).all())
        for parameter in model.parameters()
    )
    if not finite_gradients:
        raise RuntimeError("Sanity-check gradients are non-finite")
    model.zero_grad(set_to_none=True)

    forward_check = verify_model_forward_pass(
        model,
        input_height=preprocessing["input_height"],
        input_width=preprocessing["input_width"],
        batch_size=min(2, images.shape[0]),
        device=device,
    )
    if not forward_check["forward_pass_success"]:
        raise RuntimeError(f"Model forward sanity check failed: {forward_check}")

    # Evidence panel from real training samples before optimization.
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure, axes = plt.subplots(2, min(4, images.shape[0]), figsize=(12, 6), squeeze=False)
    columns = min(4, images.shape[0])
    for column in range(columns):
        axes[0, column].imshow(_display_image(images[column], preprocessing["normalize_mean"], preprocessing["normalize_std"]))
        axes[0, column].set_title(str(sample_ids[column]))
        axes[1, column].imshow(masks[column, 0].numpy(), cmap="gray", vmin=0, vmax=1)
        axes[1, column].set_title("binary mask")
        axes[0, column].axis("off")
        axes[1, column].axis("off")
    figure.suptitle("FUSeg2021 real training samples: image / aligned mask")
    figure.tight_layout()
    figure.savefig(output, dpi=150)
    plt.close(figure)

    result = {
        "status": "PASS",
        "real_training_sample_ids": list(sample_ids),
        "train_image_shape": list(images.shape),
        "train_mask_shape": list(masks.shape),
        "mask_values": sorted(float(value) for value in torch.unique(masks)),
        "validation_deterministic": deterministic_val,
        "validation_sample_ids": list(val_ids_a),
        "one_real_batch_loss": float(batch_loss.item()),
        "one_real_batch_loss_finite": bool(torch.isfinite(batch_loss).item()),
        "one_real_batch_gradients_finite": finite_gradients,
        "forward_pass": forward_check,
        "real_sample_panel": str(output),
    }
    # A sanity pass must not alter the initial model (BatchNorm buffers included)
    # or consume the shuffle streams used by the subsequent training run.
    model.load_state_dict(model_state_before)
    model.train(model_was_training)
    for loader in (train_loader, val_loader):
        state = loader_generator_states.get(id(loader))
        if state is not None:
            loader.generator.set_state(state)
    return result


def save_validation_predictions(
    model: LightweightUNet,
    val_loader: torch.utils.data.DataLoader,
    device: torch.device,
    config: Dict[str, Any],
    output_dir: str,
    max_samples: int = 8,
) -> Dict[str, Any]:
    """Save representative validation prediction panels and arrays."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    preprocessing = config["preprocessing"]
    threshold = config["evaluation"]["prediction_threshold"]
    model.eval()
    saved: List[str] = []
    seen = 0
    with torch.no_grad():
        for images, masks, sample_ids in val_loader:
            probabilities = torch.sigmoid(model(images.to(device))).cpu()
            for index, sample_id in enumerate(sample_ids):
                if seen >= max_samples:
                    break
                probability = probabilities[index, 0].numpy()
                target = masks[index, 0].numpy()
                binary = (probability >= threshold).astype(np.uint8)
                npz_path = output_path / f"{sample_id}.npz"
                np.savez_compressed(
                    npz_path,
                    sample_id=np.asarray(sample_id),
                    prediction_probability=probability.astype(np.float32),
                    prediction_binary=binary,
                    ground_truth_mask=target.astype(np.uint8),
                )
                figure, axes = plt.subplots(1, 4, figsize=(12, 3))
                axes[0].imshow(_display_image(images[index], preprocessing["normalize_mean"], preprocessing["normalize_std"]))
                axes[0].set_title("image")
                axes[1].imshow(target, cmap="gray", vmin=0, vmax=1)
                axes[1].set_title("ground truth")
                axes[2].imshow(probability, cmap="viridis", vmin=0, vmax=1)
                axes[2].set_title("probability")
                axes[3].imshow(binary, cmap="gray", vmin=0, vmax=1)
                axes[3].set_title("thresholded")
                for axis in axes:
                    axis.axis("off")
                figure.suptitle(str(sample_id))
                figure.tight_layout()
                figure_path = output_path / f"{sample_id}.png"
                figure.savefig(figure_path, dpi=150)
                plt.close(figure)
                saved.append(str(npz_path))
                seen += 1
            if seen >= max_samples:
                break
    return {"count": len(saved), "paths": saved, "split": "validation"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default="configs/training/baseline_segmentation_real.json",
        help="SPEC-02-01 FUSeg2021 training configuration",
    )
    parser.add_argument(
        "--sanity-only",
        action="store_true",
        help="Run real-data loader/model/gradient checks without training.",
    )
    parser.add_argument(
        "--train",
        action="store_true",
        help="Run the configured multi-epoch train/validation job. Omit for sanity checks only.",
    )
    parser.add_argument(
        "--data-root",
        default=None,
        help="Optional Kaggle root containing train/validation/test below manifest.source_root.",
    )
    parser.add_argument(
        "--resume-checkpoint",
        default=None,
        help="Optional latest SPEC-02-01 checkpoint to resume from (normally used on Kaggle).",
    )
    parser.add_argument(
        "--allow-cpu-training",
        action="store_true",
        help="Explicitly allow --train on CPU; normal full training requires a CUDA GPU.",
    )
    args = parser.parse_args()
    if args.sanity_only and args.train:
        parser.error("--sanity-only and --train cannot be used together")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = load_config(args.config)
    if args.resume_checkpoint:
        config["training"]["resume_checkpoint"] = str(
            resolve_runtime_path(args.resume_checkpoint)
        )
        validate_training_config(config)
    experiment_id = config["experiment_id"]
    data_config = config["data"]
    preprocessing = config["preprocessing"]
    training = config["training"]
    model_config = config["model"]
    output_config = config["output"]
    seed = int(training["random_seed"])
    set_random_seeds(seed, deterministic=training.get("deterministic", True))
    device = select_device(config["device"]["preferred"], config["device"]["fallback"])
    LOGGER.info("Experiment %s on device %s", experiment_id, device)
    if args.train and device.type != "cuda" and not args.allow_cpu_training:
        raise RuntimeError(
            "Full SPEC-02-01 training is GPU-only by default. Run --sanity-only locally "
            "and run --train on a Kaggle CUDA runtime, or pass --allow-cpu-training "
            "only for an explicitly intentional CPU experiment."
        )

    manifest_path = str(resolve_runtime_path(data_config["manifest_path"]))
    data_root = args.data_root or data_config.get("data_root")
    if data_root:
        data_root = str(resolve_runtime_path(data_root))
    manifest = validate_manifest_for_training(manifest_path, require_real_data=True)
    if manifest.get("dataset_name") != "FUSeg2021":
        raise RuntimeError("Manifest dataset is not FUSeg2021")
    if manifest.get("split_summary", {}).get("usable_test_samples", 0) != 0:
        raise RuntimeError("SPEC-02-01 must not evaluate public FUSeg test images without masks")

    train_loader, val_loader, test_loader = create_dataloaders(
        manifest_path=manifest_path,
        input_height=preprocessing["input_height"],
        input_width=preprocessing["input_width"],
        normalize_mean=preprocessing["normalize_mean"],
        normalize_std=preprocessing["normalize_std"],
        mask_threshold=preprocessing["mask_threshold"],
        batch_size=training["batch_size"],
        horizontal_flip_prob=config["augmentation"]["train_horizontal_flip_prob"],
        vertical_flip_prob=config["augmentation"].get("train_vertical_flip_prob", 0.0),
        expected_source_mask_values=preprocessing.get("source_mask_values", [0, 255]),
        random_seed=seed,
        num_workers=training.get("num_workers", 0),
        pin_memory=training.get("pin_memory", False),
        persistent_workers=training.get("persistent_workers", False),
        test_batch_size=1,
        data_root=data_root,
        include_test=False,
    )
    if test_loader is not None:
        raise RuntimeError("Unlabeled public FUSeg test samples must not be loaded for supervised evaluation")

    model = LightweightUNet(
        encoder_channels=model_config["encoder_channels"],
        num_classes=model_config["num_classes"],
    ).to(device)
    loss_config = config["loss"]
    loss_fn = BCEDiceLoss(
        bce_weight=loss_config["bce_weight"],
        dice_weight=loss_config["dice_weight"],
        epsilon=loss_config["epsilon"],
    )
    sanity = run_sanity_checks(
        train_loader,
        val_loader,
        model,
        loss_fn,
        device,
        config,
        str(resolve_runtime_path(output_config["sanity_panel"])),
    )
    _write_json(resolve_runtime_path(output_config["sanity_report"]), sanity)

    if args.sanity_only or not args.train:
        LOGGER.info("Sanity checks passed; full training was not requested")
        return

    runtime_config = copy.deepcopy(config)
    runtime_config["data"]["manifest_path"] = manifest_path
    runtime_config["data"]["data_root"] = data_root
    runtime_config["checkpointing"]["checkpoint_dir"] = str(
        resolve_runtime_path(runtime_config["checkpointing"].get("checkpoint_dir", "models/checkpoints"))
    )
    if runtime_config["training"].get("resume_checkpoint"):
        runtime_config["training"]["resume_checkpoint"] = str(
            resolve_runtime_path(runtime_config["training"]["resume_checkpoint"])
        )
    for output_name in (
        "log_file",
        "model_metadata",
        "sanity_report",
        "sanity_panel",
        "experiment_record",
        "prediction_output_dir",
    ):
        runtime_config["output"][output_name] = str(
            resolve_runtime_path(runtime_config["output"][output_name])
        )

    training_start = time.monotonic()
    training_log = train_baseline_model(
        model, loss_fn, train_loader, val_loader, runtime_config, device
    )
    training_log["config"] = runtime_config
    training_log["dataset_manifest_summary"] = manifest["split_summary"]
    training_log["model_parameters"] = count_model_parameters(model)
    training_log["sanity_checks"] = sanity
    training_log["training_wall_time_seconds"] = round(time.monotonic() - training_start, 3)
    _write_json(resolve_runtime_path(output_config["log_file"]), training_log)

    checkpoint_metadata = {
        "experiment_id": experiment_id,
        "dataset": runtime_config["data"],
        "manifest_reference": manifest_path,
        "model": model_config,
        "model_parameters": count_model_parameters(model),
        "loss": loss_config,
        "preprocessing": preprocessing,
        "augmentation": config["augmentation"],
        "environment": collect_environment_metadata(device),
        "best_epoch": training_log["best_epoch"],
        "best_validation_metrics": training_log["best_validation_metrics"],
        "checkpoint_path": training_log["checkpoint_path"],
    }
    _write_json(resolve_runtime_path(output_config["model_metadata"]), checkpoint_metadata)

    # Reload the saved best checkpoint before creating qualitative artifacts.
    load_checkpoint(training_log["checkpoint_path"], model, device)
    prediction_artifacts = save_validation_predictions(
        model,
        val_loader,
        device,
        config,
        str(resolve_runtime_path(output_config["prediction_output_dir"])),
        max_samples=output_config.get("representative_prediction_count", 8),
    )
    training_log["representative_predictions"] = prediction_artifacts
    _write_json(resolve_runtime_path(output_config["log_file"]), training_log)

    experiment_record = {
        "experiment_id": experiment_id,
        "status": "PASS_SPEC_02_01_REAL_FUSEG2021",
        "specification": "SPEC-02-01",
        "dataset": runtime_config["data"],
        "manifest_path": manifest_path,
        "official_test_evaluation": "NOT_PERFORMED_PUBLIC_TEST_MASKS_UNAVAILABLE",
        "model": checkpoint_metadata,
        "training": training_log,
        "sanity_checks": sanity,
        "representative_predictions": prediction_artifacts,
        "phase_boundary": "SPEC-02-02 and Phase 03 not started",
        "remaining_issues": [
            "Patient/examination identifiers are unavailable; patient-level isolation cannot be claimed.",
            "The public FUSeg2021 test images have no usable ground-truth masks and were not evaluated.",
            "One validation mask with unexpected value 32 was excluded without modifying raw data.",
        ],
    }
    _write_json(resolve_runtime_path(output_config["experiment_record"]), experiment_record)
    LOGGER.info("SPEC-02-01 training complete; best checkpoint=%s", training_log["checkpoint_path"])


if __name__ == "__main__":
    main()
