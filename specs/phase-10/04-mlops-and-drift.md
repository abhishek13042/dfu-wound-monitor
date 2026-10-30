# P10-S04 — Model Lifecycle and Drift Monitoring

**Status:** `NOT_STARTED`. Nothing in this specification is implemented. It needs approval before work begins.

## 1. Objective

Change models safely and notice when uploads no longer resemble the training data.

## 2. Scope

- Model registry records
- Promotion gates and rollback
- Canary release
- Input and output drift metrics
- Correction review for retraining

## 3. Non-Goals

- Automatic retraining or automatic promotion
- Claiming accuracy on production data, which has no ground truth

## 4. Requirements

- `REQ-P10-S04-001`: Each model version SHALL have a registry record with artifact hash, data versions, metrics and limitations.
- `REQ-P10-S04-002`: Promotion SHALL require passing gates and a human approval. Gates SHALL include parity, no-regression on fixed evaluation sets, and the benchmark.
- `REQ-P10-S04-003`: Rollback to the previous version SHALL take one command, and results SHALL keep the version that made them.
- `REQ-P10-S04-004`: Drift metrics SHALL cover image brightness, blur, size, quality-rejection rate and predicted area, compared with a stored reference.
- `REQ-P10-S04-005`: A drift alert SHALL be labelled as a change in inputs and SHALL NOT be reported as a change in accuracy.

## 5. Assumptions

- Hugging Face Hub stores artifacts. MLflow is added only if the simple registry proves too limited.
- Drift metrics hold summary numbers and no images.

## 6. Dependencies

- `P07-S06`
- `P09-S03`
- `P10-S01`

## 7. Inputs

- Evaluation reports
- Telemetry from P10-S01
- Reviewed corrections from P09-S03

## 8. Outputs

- Registry
- Promotion tool
- Drift dashboard
- Runbook

## 9. Data / Interface Contract

A registry record has `model_version`, `sha256`, `runtime`, `dataset_refs`, `metrics`, `limitations`, `status` and `approved_by`. `status` is `CANDIDATE`, `CANARY`, `ACTIVE` or `RETIRED`.

## 10. Invariants

- The active version is always known and hash-verified.
- A promotion leaves a record.
- Longitudinal comparisons respect model version.

## 11. Technical Design

Start with a small database-backed registry, since there are few models. Canary sends a small share of jobs to the candidate and compares summary outputs. Drift uses population stability index over the reference distribution, computed daily.

## 12. Implementation Tasks

1. Add registry.
2. Add gates.
3. Add canary and rollback.
4. Add drift metrics.
5. Write the runbook.

## 13. Failure Modes / Edge Cases

| Case | Required behaviour |
|---|---|
| Gate data missing | Promotion is refused |
| Canary shows errors | Automatic stop, and a person decides the next step |
| Reference out of date | Alert asks for a reviewed update |

## 14. Tests

- Gate blocking
- Rollback drill
- Simulated drift

## 15. Acceptance Criteria

- A candidate passes through promotion and rollback in staging, with records for each step.
- A simulated shift raises an alert.

## 16. Evidence

- Promotion and rollback records
- Drift dashboard export

## 17. Reproducibility

Planned commands. These do not work until the specification is implemented.

```bash
python scripts/deployment/promote_model.py --candidate <version> --dry-run
```

## 18. Risks / Limitations

- Drift signals do not measure accuracy, and small traffic gives noisy metrics.

## 19. Traceability

| Requirement | Planned implementation | Planned test | Planned evidence | Status |
|---|---|---|---|---|
| `REQ-P10-S04-001` | `src/mlops/registry.py` | `test_registry_requires_fields` | Test run | NOT_STARTED |
| `REQ-P10-S04-002` | `scripts/deployment/promote_model.py` | `test_gate_blocks_regression` | Promotion record | NOT_STARTED |
| `REQ-P10-S04-003` | `scripts/deployment/promote_model.py` | Rollback drill | Drill record | NOT_STARTED |
| `REQ-P10-S04-004` | `src/mlops/drift.py` | `test_drift_detects_shift` | Dashboard export | NOT_STARTED |
| `REQ-P10-S04-005` | `src/mlops/drift.py` | Text review | Alert sample | NOT_STARTED |
