"""Kaggle-ready SPEC-02-01 entrypoint with writable runtime outputs.

Copy or mount this project on Kaggle, enable a CUDA accelerator, and pass the
FUSeg2021 directory that contains train/, validation/, and test/::

    python scripts/run_kaggle_spec_02_01.py \
        --data-root "/kaggle/input/fuseg2021/Foot Ulcer Segmentation Challenge" \
        --output-root /kaggle/working/spec-02-01 --train

This is the frozen from-scratch SPEC-02-01 baseline.  The main result is
SPEC-02-03 (pretrained ResNet34 U-Net, held-out split): use
``scripts/run_spec_02_03.py`` for that.

Omitting --train runs only the bounded sanity checks.  Resume later with
--resume-checkpoint <latest_epoch.pth>.  No test loader is constructed.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_phase_02_training import load_config
from scripts.run_phase_02_training import main as training_main
from src.segmentation.config import validate_training_config


def build_kaggle_config(
    base_config: dict,
    data_root: str,
    output_root: str,
    num_workers: int = 2,
    resume_checkpoint: str | None = None,
) -> dict:
    """Create a portable config with all outputs on Kaggle's writable mount."""

    config = copy.deepcopy(base_config)
    root = Path(output_root).resolve()
    config["data"]["data_root"] = str(Path(data_root).resolve())
    manifest = Path(config["data"]["manifest_path"])
    config["data"]["manifest_path"] = str(
        manifest if manifest.is_absolute() else PROJECT_ROOT / manifest
    )
    config["training"].update(
        num_workers=num_workers,
        pin_memory=True,
        persistent_workers=False,
        resume_checkpoint=str(Path(resume_checkpoint).resolve()) if resume_checkpoint else None,
    )
    config["device"] = {"preferred": "cuda", "fallback": "cpu"}
    config["checkpointing"]["checkpoint_dir"] = str(root / "checkpoints")
    for name in (
        "log_file",
        "model_metadata",
        "sanity_report",
        "sanity_panel",
        "experiment_record",
        "prediction_output_dir",
    ):
        configured_path = Path(config["output"][name])
        config["output"][name] = str(root / name / configured_path.name)
    return validate_training_config(config)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", required=True, help="FUSeg root containing official split directories")
    parser.add_argument("--output-root", default="/kaggle/working/spec-02-01")
    parser.add_argument("--config", default="configs/training/baseline_segmentation_real.json")
    parser.add_argument("--num-workers", type=int, default=2)
    parser.add_argument("--resume-checkpoint")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--train", action="store_true", help="Run full train/validation on CUDA")
    mode.add_argument("--sanity-only", action="store_true", help="Run bounded checks only (the default)")
    args = parser.parse_args()

    config = build_kaggle_config(
        load_config(args.config),
        args.data_root,
        args.output_root,
        args.num_workers,
        args.resume_checkpoint,
    )
    output_root = Path(args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    runtime_config = output_root / "runtime_config.json"
    runtime_config.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    previous_argv = sys.argv
    try:
        sys.argv = [str(__file__), "--config", str(runtime_config), "--train" if args.train else "--sanity-only"]
        training_main()
    finally:
        sys.argv = previous_argv


if __name__ == "__main__":
    main()
