# P06-S02 — Reliability, Reproducibility, and Performance

## Status

`COMPLETED` — `scripts/evaluation/run_phase_06_benchmark.py` produces `reports/final/p06_benchmark.json`, covering hardware, cold start, per-stage latency, memory, repeatability, and boundary inputs with their failure class. No optimisation was applied, because there is no latency requirement (REQ-P06-S02-004).

## Objective

Measure repeatability and practical runtime behavior before release or
optimization.

## Scope

Repeatability, malformed inputs, latency, memory, artifact verification,
bounded robustness checks, and measured bottleneck decisions.

## Non-Goals

Premature ONNX/TensorRT optimization, clinical safety claims, or infrastructure
scaling without evidence.

## Requirements

- **REQ-P06-S02-001:** Repeated runs SHALL follow the declared reproducibility
  policy.
- **REQ-P06-S02-002:** Latency and memory SHALL be measured with hardware and
  configuration recorded.
- **REQ-P06-S02-003:** Failures SHALL be categorized as input, quality, model,
  persistence, or service failures.
- **REQ-P06-S02-004:** Optimization SHALL require a recorded measured
  bottleneck and before/after verification.

## Tests and Acceptance

Repeatability, stress/boundary, resource, artifact-integrity, and performance
benchmark tests SHALL pass with reproducible commands.
