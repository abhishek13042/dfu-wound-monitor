"""P06-S02 reliability and performance benchmark.

Measures, on the machine it runs on, with hardware and configuration recorded
(REQ-P06-S02-002):

* cold start: config load + checkpoint SHA-256 + weight load;
* per-stage latency (decode, quality gate, segmentation, measurement) over
  ``--images`` held-out test images after ``--warmup`` warm-up runs;
* API end-to-end latency (multipart upload -> stored record) in-process;
* process memory (RSS and peak working set);
* repeatability: one image analysed ``--repeats`` times, mask and
  probability hashes compared (REQ-P06-S02-001);
* boundary inputs through the API (empty, truncated, wrong format, oversize,
  tiny, extreme aspect) with their failure class (REQ-P06-S02-003).

The output records the dominant stage.  No optimisation is applied by this
script: REQ-P06-S02-004 requires a measured bottleneck *and* a stated latency
requirement that it violates before any change is made.

Example::

    python scripts/evaluation/run_phase_06_benchmark.py --images 20
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import io
import json
import os
import platform
import sys
import tempfile
import time
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import psutil
import torch
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.inference.engine import DEFAULT_INFERENCE_CONFIG, InferenceEngine, InferenceRequest  # noqa: E402
from src.measurement.engine import measure  # noqa: E402
from src.quality.gate import QualityGate  # noqa: E402

PROCESS = psutil.Process()


def rss_mb() -> float:
    return PROCESS.memory_info().rss / 2 ** 20


def peak_mb() -> float | None:
    info = PROCESS.memory_info()
    peak = getattr(info, "peak_wset", None) or getattr(info, "peak_rss", None)
    return peak / 2 ** 20 if peak else None


def stats(values: list[float]) -> dict[str, float]:
    arr = np.asarray(values, dtype=np.float64)
    return {"n": int(arr.size), "mean": round(float(arr.mean()), 4), "p50": round(float(np.median(arr)), 4),
            "p90": round(float(np.percentile(arr, 90)), 4), "min": round(float(arr.min()), 4),
            "max": round(float(arr.max()), 4)}


def hardware() -> dict[str, Any]:
    freq = psutil.cpu_freq()
    return {
        "platform": platform.platform(), "processor": platform.processor(), "machine": platform.machine(),
        "physical_cores": psutil.cpu_count(logical=False), "logical_cores": psutil.cpu_count(logical=True),
        "cpu_max_mhz": round(freq.max) if freq else None,
        "total_ram_gb": round(psutil.virtual_memory().total / 2 ** 30, 1),
        "python": platform.python_version(), "torch": torch.__version__,
        "torch_threads": torch.get_num_threads(), "cuda_available": torch.cuda.is_available(),
    }


def png_bytes(array: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(array).save(buffer, format="PNG")
    return buffer.getvalue()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", type=Path, default=PROJECT_ROOT / "data/manifests/fuseg2021_heldout_manifest.json")
    parser.add_argument("--config", type=Path, default=DEFAULT_INFERENCE_CONFIG)
    parser.add_argument("--images", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--api-images", type=int, default=5)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "reports/final/p06_benchmark.json")
    args = parser.parse_args(argv)

    samples = [s for s in json.loads(args.manifest.read_text())["samples"] if s["split"] == "test"]
    idx = np.linspace(0, len(samples) - 1, args.images).round().astype(int)
    payloads = [(PROJECT_ROOT / samples[i]["image_path"]).read_bytes() for i in idx]

    memory = {"rss_before_load_mb": round(rss_mb(), 1)}
    t0 = time.perf_counter()
    engine = InferenceEngine.from_config(args.config)
    cold_start = time.perf_counter() - t0
    memory["rss_after_load_mb"] = round(rss_mb(), 1)
    gate = QualityGate()

    for data in payloads[: args.warmup]:
        engine.predict(InferenceRequest(engine.decode(data)))

    stages: dict[str, list[float]] = {"decode": [], "quality_gate": [], "segmentation": [], "measurement": [],
                                      "total": []}
    for data in payloads:
        t = time.perf_counter()
        decoded = engine.decode(data)
        t1 = time.perf_counter()
        quality = gate.evaluate(decoded)
        t2 = time.perf_counter()
        result = engine.predict(InferenceRequest(decoded))
        t3 = time.perf_counter()
        measure(result.binary_mask, probability_mask=result.probability_mask)
        t4 = time.perf_counter()
        for name, value in (("decode", t1 - t), ("quality_gate", t2 - t1), ("segmentation", t3 - t2),
                            ("measurement", t4 - t3), ("total", t4 - t)):
            stages[name].append(value)
        assert quality.status in ("ACCEPTED", "REJECTED")
    memory["rss_after_inference_mb"] = round(rss_mb(), 1)
    latency = {name: stats(values) for name, values in stages.items()}
    shares = {name: round(sum(stages[name]) / sum(stages["total"]), 4) for name in stages if name != "total"}
    bottleneck = max(shares, key=shares.get)

    # TTA cost, measured rather than assumed (informs, does not change, the frozen config)
    tta_off = []
    frozen_config = engine.config
    try:
        engine.config = dataclasses.replace(frozen_config, tta=False)
        for data in payloads[: min(5, len(payloads))]:
            decoded = engine.decode(data)
            t = time.perf_counter()
            engine.predict(InferenceRequest(decoded))
            tta_off.append(time.perf_counter() - t)
    except Exception as error:  # noqa: BLE001 - informational only
        tta_off = []
        print(f"TTA-off measurement skipped: {error}")
    finally:
        engine.config = frozen_config

    repeat_hashes = set()
    for _ in range(args.repeats):
        result = engine.predict(InferenceRequest(engine.decode(payloads[0])))
        repeat_hashes.add((hashlib.sha256(result.binary_mask.tobytes()).hexdigest(),
                           hashlib.sha256(result.probability_mask.tobytes()).hexdigest()))

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from fastapi.testclient import TestClient

        from src.api.app import ApiSettings, create_app

    api_latency, boundary = [], []
    with tempfile.TemporaryDirectory() as tmp:
        settings = ApiSettings(data_dir=Path(tmp), load_model=False, max_upload_bytes=8 * 2 ** 20)
        with TestClient(create_app(settings, engine=engine)) as client:
            for data in payloads[: args.api_images]:
                t = time.perf_counter()
                response = client.post("/api/v1/analyses", files={"file": ("x.png", data, "image/png")})
                api_latency.append(time.perf_counter() - t)
                assert response.status_code in (201, 422), response.text
            rng = np.random.default_rng(0)
            cases = {
                "empty_payload": b"",
                "truncated_png": payloads[0][: len(payloads[0]) // 3],
                "text_file": b"hello, not an image",
                "gif_format": b"GIF89a" + b"\x00" * 100,
                "oversize_upload": b"\x00" * (8 * 2 ** 20 + 1),
                "tiny_image_32px": png_bytes(rng.integers(0, 255, (32, 32, 3), dtype=np.uint8)),
                "extreme_aspect_2000x100": png_bytes(rng.integers(0, 255, (100, 2000, 3), dtype=np.uint8)),
                "uniform_grey": png_bytes(np.full((400, 400, 3), 128, dtype=np.uint8)),
            }
            for name, data in cases.items():
                response = client.post("/api/v1/analyses", files={"file": ("x.png", data, "image/png")})
                body = response.json()
                boundary.append({"case": name, "http_status": response.status_code,
                                 "category": body.get("error", {}).get("category"),
                                 "failure_class": body.get("error", {}).get("failure_class"),
                                 "code": body.get("error", {}).get("code")})
            ready = client.get("/health/ready").status_code
    memory["rss_end_mb"] = round(rss_mb(), 1)
    memory["peak_working_set_mb"] = round(peak_mb(), 1) if peak_mb() else None

    report = {
        "report": "P06-S02 reliability and performance benchmark",
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "command": "python scripts/evaluation/run_phase_06_benchmark.py " + " ".join(argv if argv is not None else sys.argv[1:]),
        "hardware": hardware(),
        "configuration": {"model_version": engine.config.model_version, "inference_config": engine.config.version,
                          "input_size": engine.describe()["preprocessing"], "tta": engine.config.tta,
                          "threshold": engine.config.threshold, "device": str(engine.device),
                          "images": int(len(payloads)), "warmup": args.warmup,
                          "image_size": "512x512 FUSeg2021 held-out test images (evenly spaced selection)",
                          "env_omp_threads": os.environ.get("OMP_NUM_THREADS")},
        "cold_start_s": round(cold_start, 3),
        "latency_s": latency,
        "stage_share_of_total": shares,
        "measured_bottleneck": bottleneck,
        "segmentation_without_tta_s": stats(tta_off) if tta_off else None,
        "api_end_to_end_s": stats(api_latency),
        "memory": memory,
        "repeatability": {"runs": args.repeats, "distinct_mask_and_probability_hashes": len(repeat_hashes),
                          "deterministic": len(repeat_hashes) == 1},
        "boundary_inputs": boundary,
        "service_ready_after_boundary_inputs": ready == 200,
        "optimisation_decision": (
            "No optimisation applied. The measured bottleneck is recorded, but no latency requirement exists "
            "for this research prototype, so REQ-P06-S02-004's precondition (a measured bottleneck that "
            "violates a stated requirement) is not met."),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("cold_start_s", "stage_share_of_total", "measured_bottleneck",
                                             "memory", "repeatability")}, indent=2))
    print(json.dumps(report["latency_s"]["total"]), json.dumps(report["api_end_to_end_s"]))
    for row in boundary:
        print(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
