# P07-S06 — ONNX Export and Serving Parity

**Status:** `NOT_STARTED`. Nothing in this specification is implemented. It needs approval before work begins.

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

- `reports/final/p07_s06_onnx_parity.json`
- `reports/final/p07_s06_onnx_benchmark.json`

## 17. Reproducibility

Planned commands. These do not work until the specification is implemented.

```bash
python scripts/deployment/export_onnx.py
python scripts/evaluation/run_onnx_parity.py
python scripts/evaluation/run_phase_06_benchmark.py --engine onnx
```

## 18. Risks / Limitations

- The speed gain may be small on some CPUs. That result is still a valid finding.
- Numerical differences between runtimes can shift masks slightly.

## 19. Traceability

| Requirement | Planned implementation | Planned test | Planned evidence | Status |
|---|---|---|---|---|
| `REQ-P07-S06-001` | `scripts/deployment/export_onnx.py` | `test_export_records_provenance` | `models/metadata/` record | NOT_STARTED |
| `REQ-P07-S06-002` | `src/inference/onnx_engine.py` | `test_engine_interface_parity` | Test run | NOT_STARTED |
| `REQ-P07-S06-003` | `scripts/evaluation/run_onnx_parity.py` | Parity run | `reports/final/p07_s06_onnx_parity.json` | NOT_STARTED |
| `REQ-P07-S06-004` | `scripts/evaluation/run_phase_06_benchmark.py` | Benchmark run | `reports/final/p07_s06_onnx_benchmark.json` | NOT_STARTED |
| `REQ-P07-S06-005` | `configs/inference/` | Decision entry | `docs/architecture/decisions.md` | NOT_STARTED |
