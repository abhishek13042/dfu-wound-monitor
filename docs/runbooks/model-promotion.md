# Model promotion, rollback and drift

P10-S04. The registry is `configs/models/registry.json`, kept in git. Every change to it is a commit, and its `events` list records who did what and when.

## What is in the registry

| Version | Runtime | Status | Notes |
|---|---|---|---|
| `spec-02-03-resnet34-unet-512-v1` | pytorch | ACTIVE | Serving before the registry existed. Its approval is marked as a bootstrap, not a gate review. |
| `spec-02-03-resnet34-unet-512-onnx-v1` | onnx | CANDIDATE | Passes parity and the benchmark. Refused by the no-regression gate, because it has not been scored on the external lower-limb set. |

```bash
python scripts/deployment/promote_model.py list
```

## The service follows the registry

```bash
DFU_INFERENCE_CONFIG=$(python scripts/deployment/promote_model.py active-config)
```

`active-config` checks the active artifact's SHA-256 before printing its config. If the file on disk does not match, it refuses (exit 2), and the service should not start. Every analysis stores the `model_version` that made it, so changing the active model never changes an existing result.

## Promote a candidate

1. Register it. Add a record with the artifact hash, dataset versions, metrics, limitations and evidence report paths, then commit it. A record with any field missing is refused.
2. Check the gates:
   ```bash
   python scripts/deployment/promote_model.py gates <version>
   ```
   | Gate | Passes when | Missing data |
   |---|---|---|
   | parity | an ONNX model has a passing parity report for this exact hash (PyTorch: not applicable) | refused |
   | no_regression | pooled Dice on every fixed evaluation set the active model has is at most 0.01 below it | refused |
   | benchmark | p50 total latency is at most 1.2 × the active model's, and under 15 s | refused |
3. A named person promotes it. The command reruns the gates and refuses if any fails:
   ```bash
   python scripts/deployment/promote_model.py promote <version> --approved-by "<name>" --dry-run
   python scripts/deployment/promote_model.py promote <version> --approved-by "<name>"
   ```
4. Commit the registry and restart the service with the new `active-config`.

To make the ONNX candidate promotable, score it on the external set with the P06 validation method, add that report to its `evidence.validation.lowerlimb_external`, and run the gates again.

## Roll back: one command

```bash
python scripts/deployment/promote_model.py rollback --approved-by "<name>"
```

This puts back the model the active one replaced, marks the replaced one RETIRED, checks the restored artifact's hash and logs a ROLLBACK event. Commit, then restart with `active-config`. The drill is `tests/unit/test_mlops.py::test_rollback_drill`.

## Canary

The registry has the CANARY status (`promote --canary`), and `stop-canary <version> --reason "<why>"` returns a canary to CANDIDATE. Sending a share of jobs to a canary needs separate worker pools, which do not exist yet. Until they do, promote straight to ACTIVE after the gates, and keep rollback ready.

## Drift

The reference is `configs/models/drift_reference_fuseg2021.json`, built from the FUSeg2021 held-out test images:

```bash
python scripts/monitoring/build_drift_reference.py
```

Run the check daily. It reads only summary numbers from the analyses table and never opens an image:

```bash
python scripts/monitoring/check_drift.py --database-url "$DFU_DATABASE_URL" --days 7 --output reports/monitoring/drift_<date>.json
```

| Exit code | Meaning |
|---|---|
| 0 | STABLE, or INSUFFICIENT_DATA (fewer than 50 analyses for a measure) |
| 1 | DRIFT |
| 2 | refused (no database or reference) |

Each measure is compared with the population stability index over the reference's deciles: below 0.10 is stable, 0.10–0.25 moderate, and 0.25 or more a shift. The quality-rejection rate is compared directly: a change of 10 points is a shift. The measures are:

- brightness
- blur (Laplacian variance)
- image size
- predicted wound area as a share of the image

### When it reports DRIFT

The alert says the images coming in have changed. **It does not say accuracy changed: there is no ground truth in production.** When it fires:

1. Look at which measures shifted, and at their medians against the reference.
2. Review a sample of recent images, with consent and access rules applied, and find the cause: a new camera, new lighting, or a new kind of wound or clinic.
3. If the inputs are outside what the model was validated on, say so to users. Plan an evaluation on labelled images like them; reviewed corrections from P09-S03 are one source.
4. If the new inputs are expected and fine, rebuild the reference only after a person has reviewed it, and commit it.

The check also notes when the reference is older than 180 days, so a person can confirm it still describes the intended inputs.
