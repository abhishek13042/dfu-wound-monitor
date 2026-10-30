"""SPEC-02-03 entrypoint: pretrained ResNet34 U-Net on the held-out FUSeg2021 split.

Stages (run in order; each can be invoked separately):

``--train``
    Train on ``train`` with strong augmentation; select the checkpoint on
    ``internal_val`` (split ``val``).  The held-out test split is not loaded.
``--evaluate``
    Load the best checkpoint, tune threshold + minimum component area on
    internal validation at native resolution, freeze them, then score the
    held-out test split (official FUSeg validation) exactly once.
``--external``
    Score the LowerLimbFeetWound V3 external manifest with the frozen
    post-processing from ``--evaluate``.  No tuning on external data.

Kaggle (GPU)::

    python scripts/training/run_spec_02_03.py --train --evaluate \
        --data-root "/kaggle/input/fuseg2021/Foot Ulcer Segmentation Challenge" \
        --output-root /kaggle/working/spec-02-03

Local paths from the config are used when ``--data-root``/``--output-root``
are omitted.
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import torch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.segmentation.augmentation import SegmentationAugmenter  # noqa: E402
from src.segmentation.config_strong import validate_strong_config  # noqa: E402
from src.segmentation.dataset import WoundSegmentationDataset, _make_loader, load_manifest_samples  # noqa: E402
from src.segmentation.inference import (  # noqa: E402
    load_binary_mask,
    predict_native_probabilities,
    remove_small_components,
    score_predictions,
    tune_postprocessing,
)
from src.segmentation.model import BCEDiceLoss  # noqa: E402
from src.segmentation.resnet_unet import ResNetUNet  # noqa: E402
from src.segmentation.strong_trainer import train_strong_model  # noqa: E402
from src.segmentation.trainer import collect_environment_metadata, select_device  # noqa: E402

LOGGER = logging.getLogger("spec_02_03")
OUTPUT_PATH_KEYS = ("log_file", "postprocessing_tuning", "test_evaluation", "external_evaluation",
                    "experiment_record", "figure_dir")


def _absolute(path_value: str) -> str:
    path = Path(path_value)
    return str(path if path.is_absolute() else PROJECT_ROOT / path)


def prepare_config(
    base_config: dict[str, Any],
    data_root: str | None = None,
    output_root: str | None = None,
    num_workers: int | None = None,
    resume_checkpoint: str | None = None,
    num_epochs: int | None = None,
) -> dict[str, Any]:
    """Resolve paths and apply runtime overrides, then validate."""

    config = copy.deepcopy(base_config)
    config["data"]["manifest_path"] = _absolute(config["data"]["manifest_path"])
    if data_root:
        config["data"]["data_root"] = str(Path(data_root).resolve())
    if output_root:
        root = Path(output_root).resolve()
        config["checkpointing"]["checkpoint_dir"] = str(root / "checkpoints")
        for key in OUTPUT_PATH_KEYS:
            name = "figures" if key == "figure_dir" else Path(config["output"][key]).name
            config["output"][key] = str(root / name)
    else:
        config["checkpointing"]["checkpoint_dir"] = _absolute(config["checkpointing"]["checkpoint_dir"])
        for key in OUTPUT_PATH_KEYS:
            config["output"][key] = _absolute(config["output"][key])
    training = config["training"]
    if num_workers is not None:
        training["num_workers"] = num_workers
        training["persistent_workers"] = bool(training.get("persistent_workers")) and num_workers > 0
    if resume_checkpoint:
        training["resume_checkpoint"] = str(Path(resume_checkpoint).resolve())
    if num_epochs is not None:
        training["num_epochs"] = num_epochs
    return validate_strong_config(config)


def check_manifest_version(config: dict[str, Any]) -> dict[str, Any]:
    manifest = json.loads(Path(config["data"]["manifest_path"]).read_text(encoding="utf-8"))
    if manifest.get("manifest_version") != config["data"]["required_manifest_version"]:
        raise RuntimeError(
            f"Manifest version {manifest.get('manifest_version')!r} != "
            f"{config['data']['required_manifest_version']!r}; run scripts/data/build_fuseg2021_heldout_manifest.py"
        )
    return manifest


def build_model(config: dict[str, Any], pretrained: bool | None = None) -> ResNetUNet:
    model_cfg = config["model"]
    return ResNetUNet(
        encoder_name=model_cfg["encoder_name"],
        pretrained=model_cfg["pretrained"] if pretrained is None else pretrained,
        num_classes=1,
        decoder_channels=tuple(model_cfg.get("decoder_channels", (256, 128, 64, 32, 16))),
    )


def build_train_val_loaders(config: dict[str, Any]):
    data, prep, training = config["data"], config["preprocessing"], config["training"]
    common = dict(
        input_height=prep["input_height"],
        input_width=prep["input_width"],
        normalize_mean=prep["normalize_mean"],
        normalize_std=prep["normalize_std"],
        mask_threshold=prep.get("mask_threshold", 128),
        random_seed=int(training.get("random_seed", 42)),
        expected_source_mask_values=prep.get("source_mask_values", (0, 255)),
    )
    augmentation = {key: value for key, value in config["augmentation"].items() if key != "validation_and_test"}
    train_samples = load_manifest_samples(data["manifest_path"], "train", data_root=data.get("data_root"))
    val_samples = load_manifest_samples(data["manifest_path"], "val", data_root=data.get("data_root"))
    if not train_samples or not val_samples:
        raise RuntimeError(f"Empty split: train={len(train_samples)} val={len(val_samples)}")
    train_dataset = WoundSegmentationDataset(train_samples, is_training=True,
                                             augmenter=SegmentationAugmenter(augmentation), **common)
    val_dataset = WoundSegmentationDataset(val_samples, is_training=False, **common)
    loader_args = dict(
        num_workers=int(training.get("num_workers", 0)),
        pin_memory=bool(training.get("pin_memory", False)),
        persistent_workers=bool(training.get("persistent_workers", False)),
    )
    seed = common["random_seed"]
    train_loader = _make_loader(train_dataset, int(training["batch_size"]), shuffle=True, seed=seed, **loader_args)
    val_loader = _make_loader(val_dataset, int(training["batch_size"]), shuffle=False, seed=seed + 1, **loader_args)
    return train_loader, val_loader


def run_training(config: dict[str, Any], device: torch.device) -> dict[str, Any]:
    train_loader, val_loader = build_train_val_loaders(config)
    loss_cfg = config["loss"]
    loss_fn = BCEDiceLoss(loss_cfg.get("bce_weight", 0.5), loss_cfg.get("dice_weight", 0.5),
                          loss_cfg.get("epsilon", 1e-6))
    LOGGER.info("Training: train=%d internal_val=%d device=%s",
                len(train_loader.dataset), len(val_loader.dataset), device)
    return train_strong_model(build_model(config), loss_fn, train_loader, val_loader, config, device)


def load_best_model(config: dict[str, Any], device: torch.device) -> tuple[ResNetUNet, dict[str, Any]]:
    checkpointing = config["checkpointing"]
    path = Path(checkpointing["checkpoint_dir"]) / checkpointing["checkpoint_filename_template"]
    checkpoint = torch.load(path, map_location=device, weights_only=False)
    model = build_model(config, pretrained=False)
    state = checkpoint["model_state_dict"]
    # EMA checkpoints are saved from AveragedModel.module; strip a stray prefix defensively.
    state = {key.removeprefix("module."): value for key, value in state.items() if key != "n_averaged"}
    model.load_state_dict(state)
    model.to(device).eval()
    info = {
        "checkpoint_path": str(path),
        "checkpoint_epoch": checkpoint.get("epoch"),
        "checkpoint_val_dice": checkpoint.get("best_metric_value", checkpoint.get("val_dice")),
        "weights": (checkpoint.get("metadata") or {}).get("weights"),
    }
    return model, info


def _predict_records(
    model: torch.nn.Module,
    records: list[dict[str, Any]],
    config: dict[str, Any],
    device: torch.device,
) -> tuple[list[str], list[np.ndarray], list[np.ndarray]]:
    prep, evaluation = config["preprocessing"], config["evaluation"]
    paths = [Path(record["image_path"]) for record in records]
    probabilities = predict_native_probabilities(
        model, paths, prep["input_height"], prep["input_width"], prep["normalize_mean"], prep["normalize_std"],
        device, tta=bool(evaluation.get("tta", True)),
        use_amp=bool(config["training"].get("mixed_precision", True)),
        batch_size=int(evaluation.get("batch_size", 4)),
    )
    ground_truths = [
        load_binary_mask(Path(record["annotation_path"]), target_size=(prob.shape[1], prob.shape[0]),
                         threshold=int(prep.get("mask_threshold", 128)))
        for record, prob in zip(records, probabilities)
    ]
    sample_ids = [str(record["source_sample_id"]) for record in records]
    return sample_ids, probabilities, ground_truths


def _write_json(path_value: str, document: dict[str, Any]) -> None:
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, default=float) + "\n", encoding="utf-8")
    LOGGER.info("Wrote %s", path)


def _frozen_postprocessing(config: dict[str, Any]) -> dict[str, Any]:
    tuning_path = Path(config["output"]["postprocessing_tuning"])
    if not tuning_path.exists():
        raise FileNotFoundError(f"{tuning_path} missing; run --evaluate first")
    return json.loads(tuning_path.read_text(encoding="utf-8"))["frozen"]


def run_evaluation(config: dict[str, Any], device: torch.device) -> dict[str, Any]:
    evaluation = config["evaluation"]
    data = config["data"]
    model, checkpoint_info = load_best_model(config, device)

    val_records = load_manifest_samples(data["manifest_path"], "val", data_root=data.get("data_root"))
    val_ids, val_probs, val_gts = _predict_records(model, val_records, config, device)
    tuning = tune_postprocessing(val_ids, val_probs, val_gts,
                                 thresholds=evaluation["threshold_grid"],
                                 min_areas=evaluation["min_component_area_grid"])
    frozen = {"threshold": tuning["best"]["threshold"],
              "min_component_area": tuning["best"]["min_component_area"]}
    val_default, _ = score_predictions(val_ids, val_probs, val_gts, float(evaluation["selection_threshold"]), 0)
    val_tuned, _ = score_predictions(val_ids, val_probs, val_gts, frozen["threshold"], frozen["min_component_area"])
    _write_json(config["output"]["postprocessing_tuning"], {
        "experiment_id": config["experiment_id"],
        "tuned_on": "internal_val",
        "num_samples": len(val_ids),
        "frozen": frozen,
        "internal_val_at_default": val_default,
        "internal_val_at_frozen": val_tuned,
        **tuning,
    })
    del val_probs, val_gts

    test_records = load_manifest_samples(data["manifest_path"], "test", data_root=data.get("data_root"))
    test_ids, test_probs, test_gts = _predict_records(model, test_records, config, device)
    include_hd95 = bool(evaluation.get("include_hd95", True))
    test_aggregate, test_per_sample = score_predictions(
        test_ids, test_probs, test_gts, frozen["threshold"], frozen["min_component_area"], include_hd95
    )
    test_default, _ = score_predictions(test_ids, test_probs, test_gts, float(evaluation["selection_threshold"]), 0)
    result = {
        "experiment_id": config["experiment_id"],
        "specification": "SPEC-02-03",
        "evaluated_split": "heldout_test (official FUSeg2021 validation)",
        "evaluated_utc": datetime.now(UTC).isoformat(),
        "num_samples": len(test_ids),
        "frozen_postprocessing": frozen,
        "tta": bool(evaluation.get("tta", True)),
        "native_resolution": True,
        "checkpoint": checkpoint_info,
        "aggregate_metrics": test_aggregate,
        "aggregate_metrics_at_default_threshold_no_postprocessing": test_default,
        "per_sample_metrics": test_per_sample,
        "caveat": "Official FUSeg train and validation share patients; pHash only removes near-identical "
                  "re-shots, so held-out scores may be optimistic relative to unseen patients.",
    }
    _write_json(config["output"]["test_evaluation"], result)
    _maybe_save_figures(config, test_ids, test_records, test_probs, test_gts, test_per_sample, frozen)
    return result


def _maybe_save_figures(config, sample_ids, records, probabilities, ground_truths, per_sample, frozen) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from PIL import Image
    except ImportError:  # pragma: no cover - matplotlib is in requirements
        return
    figure_dir = Path(config["output"]["figure_dir"])
    figure_dir.mkdir(parents=True, exist_ok=True)
    order = sorted(range(len(per_sample)), key=lambda index: per_sample[index]["dice"])
    picks = {"worst": order[:6], "best": order[-6:]}
    for name, indices in picks.items():
        figure, axes = plt.subplots(len(indices), 3, figsize=(9, 3 * len(indices)))
        for row, index in enumerate(indices):
            with Image.open(records[index]["image_path"]) as image_file:
                image = np.asarray(image_file.convert("RGB"))
            # Draw exactly what was scored: threshold, then small-component removal.
            prediction = remove_small_components(
                (probabilities[index].astype(np.float32) >= frozen["threshold"]).astype(np.uint8),
                frozen["min_component_area"],
            )
            for column, (panel, title) in enumerate(
                ((image, sample_ids[index]), (ground_truths[index], "ground truth"),
                 (prediction, f"pred dice={per_sample[index]['dice']:.3f}"))
            ):
                axes[row, column].imshow(panel, cmap=None if column == 0 else "gray")
                axes[row, column].set_title(title, fontsize=8)
                axes[row, column].axis("off")
        figure.tight_layout()
        figure.savefig(figure_dir / f"heldout_test_{name}.png", dpi=100)
        plt.close(figure)


def run_external(config: dict[str, Any], device: torch.device, manifest_path: str,
                 data_root: str | None) -> dict[str, Any]:
    frozen = _frozen_postprocessing(config)
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    records = []
    for sample in manifest["samples"]:
        if sample.get("validation_status") != "VALID":
            continue
        record = dict(sample)
        for field in ("image_path", "annotation_path"):
            value = Path(sample[field])
            if data_root:
                value = Path(data_root) / Path(sample[field]).relative_to(manifest["source_root"])
            elif not value.is_absolute():
                value = PROJECT_ROOT / value
            record[field] = str(value)
        records.append(record)
    model, checkpoint_info = load_best_model(config, device)
    sample_ids, probabilities, ground_truths = _predict_records(model, records, config, device)
    aggregate, per_sample = score_predictions(
        sample_ids, probabilities, ground_truths, frozen["threshold"], frozen["min_component_area"],
        bool(config["evaluation"].get("include_hd95", True)),
    )
    result = {
        "experiment_id": config["experiment_id"],
        "evaluated_dataset": manifest.get("dataset_name"),
        "manifest_version": manifest.get("manifest_version"),
        "role": "external_evaluation_only (no tuning)",
        "num_samples": len(sample_ids),
        "frozen_postprocessing_from": "FUSeg2021 internal validation",
        "frozen_postprocessing": frozen,
        "preprocessing_decisions": manifest.get("preprocessing_decisions"),
        "checkpoint": checkpoint_info,
        "aggregate_metrics": aggregate,
        "per_sample_metrics": per_sample,
        "license_status": "NOT_VERIFIED - research-only external check; do not redistribute",
    }
    _write_json(config["output"]["external_evaluation"], result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="configs/training/segmentation_resnet34_unet_512.json")
    parser.add_argument("--data-root", help="FUSeg2021 root containing train/ validation/ test/")
    parser.add_argument("--output-root", help="Writable directory for checkpoints and reports")
    parser.add_argument("--num-workers", type=int)
    parser.add_argument("--num-epochs", type=int, help="Override for smoke runs only")
    parser.add_argument("--resume-checkpoint")
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--evaluate", action="store_true")
    parser.add_argument("--external", action="store_true")
    parser.add_argument("--external-manifest", default="data/manifests/lowerlimb_v3_external_manifest.json")
    parser.add_argument("--external-data-root", help="Remap LowerLimb paths relative to its source_root")
    args = parser.parse_args()
    if not (args.train or args.evaluate or args.external):
        parser.error("Choose at least one of --train, --evaluate, --external")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    base = json.loads(Path(_absolute(args.config)).read_text(encoding="utf-8"))
    config = prepare_config(base, args.data_root, args.output_root, args.num_workers,
                            args.resume_checkpoint, args.num_epochs)
    manifest = check_manifest_version(config)
    device = select_device(config["device"].get("preferred", "cuda"), config["device"].get("fallback", "cpu"))

    record: dict[str, Any] = {
        "experiment_id": config["experiment_id"],
        "specification": "SPEC-02-03",
        "config": config,
        "manifest_version": manifest["manifest_version"],
        "split_summary": {key: manifest["split_summary"].get(key) for key in
                          ("train_samples", "val_samples", "test_samples", "empty_mask_samples",
                           "quarantined_near_duplicate_of_test")},
        "environment": collect_environment_metadata(device),
        "reproducibility": "Seeds fixed; deterministic=false (cuDNN autotune + AMP), so reruns agree closely "
                           "but not bit-for-bit.",
    }
    record_path = Path(config["output"]["experiment_record"])
    if record_path.exists():
        previous = json.loads(record_path.read_text(encoding="utf-8"))
        record = {**previous, **record}
    if args.train:
        summary = run_training(config, device)
        record["training"] = {key: value for key, value in summary.items() if key != "epoch_logs"}
    if args.evaluate:
        result = run_evaluation(config, device)
        record["heldout_test"] = {"frozen_postprocessing": result["frozen_postprocessing"],
                                  "aggregate_metrics": result["aggregate_metrics"]}
    if args.external:
        result = run_external(config, device, _absolute(args.external_manifest), args.external_data_root)
        record["external"] = {"dataset": result["evaluated_dataset"], "aggregate_metrics": result["aggregate_metrics"]}
    _write_json(str(record_path), record)


if __name__ == "__main__":
    main()
