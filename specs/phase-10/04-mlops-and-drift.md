# P10-S04 — Model Lifecycle and Drift Monitoring

**Status:** `IN_PROGRESS`. The registry, gates, one-command rollback and the input-drift check are built and tested (REQ-001 to REQ-005 `COMPLETED` on this machine). Still to do: the canary and the staging acceptance run are `BLOCKED`. Canary routing needs separate worker pools, and staging is the deployment owner's. Scheduling the drift check daily is also the deployment owner's.

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
- As built (2026-11-05), the registry is a JSON file in git, not a database table. Each promotion is then a reviewed commit, and the history survives a database restore. The existing `model_versions` table is unchanged: it still names the model each analysis was made with.
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

As built:

- **`src/mlops/registry.py`:**
  - The registry is the file `configs/models/registry.json`, with a `models` list and an `events` log. See §5 for why it is a file.
  - `validate` refuses any record that lacks a contract field, has a malformed hash, has no dataset version or has no limitations.
  - At most one model is ACTIVE.
  - `verify_artifact` checks the artifact's SHA-256 against the record.
  - `promote` needs every gate passed and a named approver.
  - `rollback` puts back the model the active one replaced.
- **`src/mlops/gates.py`:** three gates. Missing evidence fails a gate.
  - parity: needs an ONNX parity report for this exact hash.
  - no_regression: pooled Dice may be at most 0.01 below the active model's on each fixed evaluation set.
  - benchmark: p50 total latency must be at most 1.2 × the active model's, and under 15 s.
- **`scripts/deployment/promote_model.py`:** the commands list, gates, promote (`--approved-by`, `--canary`, `--dry-run`), rollback, stop-canary and active-config.
  - `active-config` prints the inference config for `DFU_INFERENCE_CONFIG`, after a hash check.
- **`scripts/deployment/bootstrap_registry.py`:** writes the first registry.
  - The PyTorch model was serving before the registry existed. It is recorded as ACTIVE, with the approval marked as a bootstrap, not as a review.
  - The ONNX export is recorded as a CANDIDATE.
- **`src/mlops/drift.py`:** the measures are brightness, blur (Laplacian variance), megapixels and predicted area as a share of the image.
  - Each measure is compared with PSI over the reference's deciles: 0.10 or more is moderate, and 0.25 or more is a shift.
  - The quality-rejection rate is a shift when it changes by 10 points or more.
  - A measure with fewer than 50 analyses is reported as INSUFFICIENT_DATA, not judged.
  - A reference older than 180 days gets a note asking for a reviewed update.
  - The input is only the summary numbers already stored in `analyses.record_json`.
- **`scripts/monitoring/build_drift_reference.py`:** builds the reference from the FUSeg2021 held-out test images. It uses the quality gate's measures, plus the predicted areas from the P06 report.
- **`scripts/monitoring/check_drift.py`:** runs the daily check. Exit code 1 means drift.

## 12. Implementation Tasks

1. Add registry.
2. Add gates.
3. Add canary and rollback.
4. Add drift metrics.
5. Write the runbook.

## 13. Failure Modes / Edge Cases

| Case | Required behaviour |
|---|---|
| Gate data missing | Promotion is refused. The ONNX candidate is refused today: it has no external-set report |
| Canary shows errors | Automatic stop, and a person decides the next step. `stop-canary` exists; automatic stopping waits for canary routing (`BLOCKED`) |
| Reference out of date | Alert asks for a reviewed update. The drift report adds a note after 180 days |
| Too few analyses | The measure is INSUFFICIENT_DATA, not judged |
| Artifact replaced on disk | `active-config` and every promotion refuse on a hash mismatch |
| Approver name blank | Promotion and rollback are refused |

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

Recorded on 2026-11-05.

- **Tests:** `tests/unit/test_mlops.py`, 18 passed.
  - Required fields, one test per field.
  - Empty limitations, and a reused version.
  - A gate blocking a 0.04 Dice regression, missing evidence and a model 3 × slower.
  - An approver is required.
  - The rollback drill through the command line: promote, roll back, check the event log and `active-config`.
  - A tampered artifact is refused.
  - Simulated drift: darker, blurrier images with 30 % rejected raise a DRIFT alert, and the same distribution stays STABLE.
  - Too little data, and a stale reference.
  - Features read from a stored record.
  - `check_drift` against an SQLite analyses table, which ignores rows outside the window.
- **Registry:** `configs/models/registry.json` holds the two existing models.
- **Real gate run** on the ONNX candidate, `promote_model.py gates spec-02-03-resnet34-unet-512-onnx-v1`, exit 1:
  - parity: passed.
  - no_regression: FUSeg2021 test passes at 0.9222 against 0.9222, but the external lower-limb set fails because no ONNX report exists.
  - benchmark: passed, p50 2.07 s against a limit of 3.86 s.
  - The candidate stays a CANDIDATE.
- **Drift reference:** `configs/models/drift_reference_fuseg2021.json` from the 191 FUSeg2021 test images. Medians: brightness 127.4, blur 94.3, 0.26 megapixels, predicted area 0.71 % of the image. The quality-rejection rate is 0 %, so any rejections in production count as a change. Log: `reports/final/p10_s04_drift_reference.log`.
- **Runbook:** `docs/runbooks/model-promotion.md`.
- **Not done:**
  - A staging promotion and rollback with records (acceptance criterion 1).
  - A canary.
  - A drift dashboard: the drift check writes a JSON report and an exit code instead.

## 17. Reproducibility

```bash
python -m pytest tests/unit/test_mlops.py -q
python scripts/deployment/bootstrap_registry.py          # once; refuses if the registry exists
python scripts/deployment/promote_model.py list
python scripts/deployment/promote_model.py gates spec-02-03-resnet34-unet-512-onnx-v1
python scripts/deployment/promote_model.py promote <version> --approved-by "<name>" --dry-run
python scripts/deployment/promote_model.py rollback --approved-by "<name>"
python scripts/monitoring/build_drift_reference.py
python scripts/monitoring/check_drift.py --database-url "$DFU_DATABASE_URL" --days 7
```

## 18. Risks / Limitations

- Drift signals do not measure accuracy, and small traffic gives noisy metrics.
- The reference comes from the FUSeg2021 test images only, all from one dataset. Real uploads will probably differ at once, so expect early alerts, and review them rather than silencing them.
- The predicted area in the reference was measured at the model's 512 × 512 working size. Production masks are measured at the original size, so the area is compared as a share of the image, not in pixels.
- The registry being a file means two people promoting at once would conflict in git. That is accepted while promotions are rare.
- The bootstrap ACTIVE record was never through the gates. Its first real review happens when a candidate is compared with it.
- Correction review for retraining (§2) is not built here. The reviewed corrections from P09-S03 are where it would start.

## 19. Traceability

| Requirement | Implementation | Test | Evidence | Status |
|---|---|---|---|---|
| `REQ-P10-S04-001` | `src/mlops/registry.py`, `configs/models/registry.json` | `test_registry_requires_fields` | Test run 2026-11-05 | COMPLETED |
| `REQ-P10-S04-002` | `src/mlops/gates.py`, `scripts/deployment/promote_model.py` | `test_gate_blocks_regression` | ONNX gate run 2026-11-05 (refused) | COMPLETED |
| `REQ-P10-S04-003` | `scripts/deployment/promote_model.py` | `test_rollback_drill` | Drill in test run; staging drill `BLOCKED` | COMPLETED |
| `REQ-P10-S04-004` | `src/mlops/drift.py`, `scripts/monitoring/check_drift.py` | `test_drift_detects_shift` | Reference built 2026-11-05 | COMPLETED |
| `REQ-P10-S04-005` | `src/mlops/drift.py` (`ALERT_TEXT`) | `test_drift_detects_shift` | Alert text in test | COMPLETED |
