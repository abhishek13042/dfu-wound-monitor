"""P07-S06 export of the SPEC-02-03 checkpoint to ONNX (REQ-P07-S06-001).

Loads the checkpoint through ``InferenceEngine`` (so its pinned SHA-256 is
checked first), exports the bare network with dynamic batch, height and width,
checks the graph with ``onnx.checker``, and writes:

* ``models/onnx/spec-02-03/resnet34_unet_512.onnx``;
* ``configs/inference/spec_02_03_onnx_inference.json``: the frozen inference
  config unchanged except for an ``onnx`` block holding the ONNX file's SHA-256,
  the source checkpoint's SHA-256, the opset and the ONNX model version;
* ``reports/final/p07_s06_onnx_export.json``: the same facts plus versions.

TTA is not in the graph: the engine runs the session once per flip view.

Example::

    python scripts/deployment/export_onnx.py
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import torch  # noqa: E402

from src.inference.engine import DEFAULT_INFERENCE_CONFIG, InferenceEngine, sha256_file  # noqa: E402
from src.inference.onnx_engine import DEFAULT_ONNX_CONFIG  # noqa: E402

DEFAULT_OUTPUT = PROJECT_ROOT / "models" / "onnx" / "spec-02-03" / "resnet34_unet_512.onnx"
ONNX_MODEL_VERSION = "spec-02-03-resnet34-unet-512-onnx-v1"


def export(model: torch.nn.Module, output: Path, height: int, width: int, opset: int) -> None:
    import onnx

    output.parent.mkdir(parents=True, exist_ok=True)
    sample = torch.zeros(1, 3, height, width)
    torch.onnx.export(model.cpu().eval(), (sample,), str(output), input_names=["image"], output_names=["logits"],
                      dynamic_axes={"image": {0: "batch", 2: "height", 3: "width"},
                                    "logits": {0: "batch", 2: "height", 3: "width"}},
                      opset_version=opset, do_constant_folding=True, dynamo=False)
    onnx.checker.check_model(onnx.load(str(output)))


def relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix() if path.is_relative_to(PROJECT_ROOT) else str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_INFERENCE_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--onnx-config", type=Path, default=DEFAULT_ONNX_CONFIG)
    parser.add_argument("--opset", type=int, default=17)
    parser.add_argument("--report", type=Path, default=PROJECT_ROOT / "reports/final/p07_s06_onnx_export.json")
    args = parser.parse_args(argv)

    import onnx
    import onnxruntime

    engine = InferenceEngine.from_config(args.config)
    cfg = engine.config
    export(engine.model, args.output, cfg.input_height, cfg.input_width, args.opset)
    onnx_sha = sha256_file(args.output)

    block = {"model_path": relative(args.output), "model_sha256": onnx_sha, "model_version": ONNX_MODEL_VERSION,
             "opset": args.opset, "source_checkpoint_sha256": engine.checkpoint_info["checkpoint_sha256"],
             "source_inference_config_sha256": cfg.sha256,
             "note": "Same weights, preprocessing and post-processing as the PyTorch model. Flip TTA is applied "
                     "by the engine, one session call per view."}
    onnx_config = {**cfg.raw, "inference_config_version": f"{cfg.version}-onnx", "onnx": block}
    args.onnx_config.write_text(json.dumps(onnx_config, indent=2) + "\n", encoding="utf-8")

    report = {
        "report": "P07-S06 ONNX export",
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "command": "python scripts/deployment/export_onnx.py " + " ".join(argv if argv is not None else sys.argv[1:]),
        **block,
        "onnx_size_bytes": args.output.stat().st_size,
        "checkpoint_size_bytes": cfg.checkpoint_path.stat().st_size,
        "dynamic_axes": ["batch", "height", "width"],
        "onnx_config": relative(args.onnx_config),
        "versions": {"torch": torch.__version__, "onnx": onnx.__version__, "onnxruntime": onnxruntime.__version__,
                     "python": platform.python_version()},
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
