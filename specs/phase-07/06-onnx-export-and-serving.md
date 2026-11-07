# P07-S06 — ONNX Export and Serving Parity

**Status:** `IN_PROGRESS`. Export, engine, parity and the latency and memory benchmarks are done, and PyTorch stays the default (decision 23). Every requirement has local evidence; it waits on a CI run.

## 1. Objective

Serve the model with ONNX Runtime to drop PyTorch from the serving image, but only if measured parity and speed justify it.

## 2. Scope

- Export of the ResNet34 U-Net to ONNX
- `OnnxEngine` behind the existing engine interface
- Parity check on the FUSeg held-out set
- Latency, memory and image-size comparison

## 3. Non-Goals

- Retraining
- Changing the threshold or minimum area
- Quantisation, unless parity is kept and it is run as a separate measured step

## 4. Requirements

- `REQ-P07-S06-001`: The export SHALL be reproducible from the pinned checkpoint and SHALL record its own SHA-256, the source checkpoint hash and the opset.
- `REQ-P07-S06-002`: `OnnxEngine` SHALL produce the same result type as the PyTorch engine, including flip TTA.
- `REQ-P07-S06-003`: On the 191 held-out images, pooled Dice SHALL differ by at most 0.001 from the PyTorch result, using the threshold and area already fixed.
- `REQ-P07-S06-004`: Latency, peak memory and image size SHALL be measured with the P06 benchmark method on the same class of hardware.
- `REQ-P07-S06-005`: ONNX SHALL become the default only if parity passes and the report shows a gain. Otherwise PyTorch stays and the result is recorded.

## 5. Assumptions

- ONNX Runtime has a wheel for the serving Python version; the image uses Python 3.12.
- The FUSeg held-out set is available for this one parity comparison. It compares two engines and tunes nothing.

## 6. Dependencies

- `P03-S01`
- `P07-S01`

## 7. Inputs

- `models/checkpoints/spec-02-03/resnet34_unet_512_best.pth`
- `configs/inference/spec_02_03_inference.json`

## 8. Outputs

- ONNX model
- `src/inference/onnx_engine.py`
- Parity and benchmark reports

## 9. Data / Interface Contract

`DFU_INFERENCE_ENGINE` is `pytorch` or `onnx`, defaulting to `pytorch`. `model_version` changes when the runtime changes, for example `spec-02-03-resnet34-unet-512-onnx-v1`, so stored results stay attributable.

## 10. Invariants

- Preprocessing stays identical to training.
- The ONNX file is hash-pinned as the checkpoint is.
- Comparisons between runtimes follow the compatibility policy in `src/longitudinal/comparison.py`.

## 11. Technical Design

Export with a dynamic height and width, to match native-size inference. Run the second TTA pass as a second session call, not inside the graph, so that the model stays simple. Compare probability maps as well as Dice, to find any divergence early.

## 12. Implementation Tasks

1. Write the export script.
2. Add `OnnxEngine`.
3. Run parity.
4. Run the benchmark.
5. Record the decision.

## 13. Failure Modes / Edge Cases

| Case | Required behaviour |
|---|---|
| Parity fails | Keep PyTorch, record the cause, and do not adjust the threshold to compensate |
| Hash mismatch at load | Engine refuses to load, as with the checkpoint |
| Unsupported operator | Change the export path, not the model weights |

## 14. Tests

- Tiny-model export and round trip in CI
- Interface parity
- Hash refusal

## 15. Acceptance Criteria

- The parity report exists and the requirement threshold is met, or the decision to stay on PyTorch is recorded.
- Latency claims come only from the benchmark report.

## 16. Evidence

- 2026-11-04, `reports/final/p07_s06_onnx_export.json`: opset 17, ONNX SHA-256 `d3738aed…b698`, source checkpoint `26aca52e…cf04`.
- 2026-11-04, `reports/final/p07_s06_onnx_parity.json`: 191 held-out images, pooled Dice difference 0.0, maximum probability difference 7.63e-6, no mask pixel differs, `parity_passed: true`.
- 2026-11-04, `reports/final/p07_s06_onnx_benchmark.json` and `reports/final/p07_s06_pytorch_benchmark.json`, P06 method on the same CPU machine:

  | Measure | ONNX | PyTorch |
  |---|---|---|
  | Segmentation p50 (flip TTA) | 1.932 s | 3.098 s |
  | Segmentation p50 (no TTA) | 0.484 s | 0.663 s |
  | Total p50 | 2.067 s | 3.217 s |
  | API end-to-end mean | 1.991 s | 2.921 s |
  | RSS after load | 412 MB | 680 MB |
  | Peak working set | 609 MB | 913 MB |

- `tests/integration/test_p07_s06_onnx.py`: 10 tests.
- 2026-11-01, `reports/final/p07_s06_image_size.json`, Docker in WSL Ubuntu 24.04: the serving image is 2.04 GB, 2.14 GB with `onnxruntime` added, and would be 0.91 GB without torch, which cannot serve yet. The ONNX file is not in the image, so the size does not depend on which export is used.

## 17. Reproducibility

```bash
python scripts/deployment/export_onnx.py
python scripts/evaluation/run_onnx_parity.py
python scripts/evaluation/run_phase_06_benchmark.py --engine onnx
python -m pytest tests/integration/test_p07_s06_onnx.py -q
```

The `.onnx` file is ignored by git. Export it from the pinned checkpoint before selecting `DFU_INFERENCE_ENGINE=onnx`; the engine refuses a file whose hash differs from the config.

## 18. Risks / Limitations

- The speed gain may be small on some CPUs. That result is still a valid finding.
- Numerical differences between runtimes can shift masks slightly.
- The benchmark is one machine and one run. A busy machine changes absolute numbers, so read the two engines side by side, not as SLOs.
- Torch stays in the image while `engine.py` imports it, so ONNX saves memory and time but not image size yet.

## 19. Traceability

| Requirement | Implementation | Test | Evidence | Status |
|---|---|---|---|---|
| `REQ-P07-S06-001` | `scripts/deployment/export_onnx.py` | `test_export_records_provenance` | `reports/final/p07_s06_onnx_export.json` | COMPLETED |
| `REQ-P07-S06-002` | `src/inference/onnx_engine.py` | `test_engine_interface_parity` | Test run 2026-11-04 | COMPLETED |
| `REQ-P07-S06-003` | `scripts/evaluation/run_onnx_parity.py` | Parity run | `reports/final/p07_s06_onnx_parity.json` | COMPLETED |
| `REQ-P07-S06-004` | `scripts/evaluation/run_phase_06_benchmark.py` | Benchmark run | `reports/final/p07_s06_onnx_benchmark.json`, `reports/final/p07_s06_pytorch_benchmark.json` , `reports/final/p07_s06_image_size.json` | COMPLETED |
| `REQ-P07-S06-005` | `src/inference/onnx_engine.py` (`engine_choice`) | `test_engine_choice_defaults_to_pytorch` | `docs/architecture/decisions.md`, decision 23 | COMPLETED |
