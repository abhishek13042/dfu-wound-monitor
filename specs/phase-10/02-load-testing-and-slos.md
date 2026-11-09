# P10-S02 — Load Testing and Service Objectives

**Status:** `IN_PROGRESS`. The scenarios, a single-machine baseline, the provisional SLOs and the overload check are done (REQ-002 to REQ-004 `COMPLETED` on one machine). Still to do: the Locust run on staging (REQ-001's staging part) and the scaling run (REQ-005) are `BLOCKED`. Both need a staging deployment with Redis and separate workers, which is the deployment owner's.

## 1. Objective

State what the platform can handle, based on measurement.

## 2. Scope

- Locust scenarios for the main flow
- Service level objectives
- Capacity model per worker
- Autoscaling rules based on queue depth

## 3. Non-Goals

- Performance work without a measured need
- High-availability across regions

## 4. Requirements

- `REQ-P10-S02-001`: Locust scenarios SHALL cover browsing, upload and analysis, with a stated user mix.
- `REQ-P10-S02-002`: The report SHALL state throughput, p50, p95 and p99 latency, and error rate at each load level, with the hardware used.
- `REQ-P10-S02-003`: SLOs SHALL be written after the first baseline run, not before it.
- `REQ-P10-S02-004`: Overload SHALL produce 429 with a retry hint, not timeouts or lost jobs.
- `REQ-P10-S02-005`: Worker scaling SHALL follow queue depth and SHALL be shown to reduce wait time.

## 5. Assumptions

- Tests run on a staging deployment with a separate database, never on user data.
- As built (2026-11-05), there is no staging, so the baseline ran on one laptop. It used the real API, the real model and its own empty database (§16).

## 6. Dependencies

- `P10-S01`
- `P07-S06`

## 7. Inputs

- Staging deployment
- Licensed or synthetic test images

## 8. Outputs

- Locust suite
- Load report
- SLO document
- Capacity table

## 9. Data / Interface Contract

Job throughput is limited by workers, so the headline measure is time from submit to result, as well as API latency.

## 10. Invariants

- Published numbers cite the report and its hardware.
- No test touches production user data.

## 11. Technical Design

Run a step load until queue wait grows without limit. That point sets the capacity per worker. Fix only the bottleneck that the measurements name.

As built:

- **`tests/load/scenarios.py`:** the user flow, written once. The mix is 7 browsing actions to 3 upload-and-analyse actions, with synthetic images.
- **`tests/load/locustfile.py`:** drives those scenarios with Locust, for staging.
- **`scripts/evaluation/run_load_baseline.py`:** drives the same scenarios from threads, for one machine.
  - It starts the real API with its own data directory and sign-in keys.
  - It runs the step load, then restarts the API with a small queue limit and sends a burst.
  - The report records, per level: throughput, p50/p95/p99, error rate per route, analyses per minute and submit-to-result time.
- The measured bottleneck is the single worker, about 10 analyses a minute, so no API change was made.

## 12. Implementation Tasks

1. Write scenarios.
2. Run a baseline.
3. Write SLOs.
4. Test overload.
5. Test scaling.

## 13. Failure Modes / Edge Cases

| Case | Required behaviour |
|---|---|
| Test machine saturates first | Use a larger or distributed Locust setup |
| Free tiers throttle | Record it as a finding |

## 14. Tests

- Short load run in CI, on demand
- Overload behaviour

## 15. Acceptance Criteria

- The report exists and the capacity table explains the chosen worker count.

## 16. Evidence

- `reports/final/p10_s02_load.json`
- `docs/deployment/SLO.md`

Recorded on 2026-11-05.

- **Hardware:** 2-core, 4-thread Intel laptop at 2.9 GHz, 7.7 GB RAM, CPU only. It is in the report.
- **Baseline** (`reports/final/p10_s02_load.json`, log `reports/final/p10_s02_load_run.log`):

  | Users | Requests/s | API p95 | API p99 | Errors | Analyses/min | Submit-to-result p50 |
  |---|---|---|---|---|---|---|
  | 1 | 1.45 | 0.10 s | 0.16 s | 0 % | 6.9 | 4.1 s |
  | 4 | 4.33 | 0.06 s | 0.20 s | 0 % | 9.7 | 16.2 s |
  | 8 | 7.21 | 0.05 s | 0.22 s | 0 % | 10.3 | 32.3 s |
  | 16 | 10.93 | 0.04 s | 0.20 s | 0 % | 8.4 | 70.8 s |

  - Analyses per minute stop rising from 4 users on, while the wait keeps growing. One worker's capacity is about 10 a minute; the planning figure is 8.
- **Overload:** a burst of 12 against a queue limit of 3.
  - 6 were accepted and 6 refused with 429 `QUEUE_FULL` and `Retry-After: 30`.
  - All 6 accepted jobs completed, and none were lost. The report marks it `passed`.
- **SLOs:** `docs/deployment/SLO.md` (provisional), written from the baseline.
- **Tests:** `tests/load/test_scenarios.py`, 4 passed.
- **Not done:**
  - The Locust run on staging. Locust is not installed here, and installing it needs approval.
  - The scaling run.
  - A short load run in CI.

## 17. Reproducibility

```bash
python -m pytest tests/load -q
python scripts/evaluation/run_load_baseline.py --levels 1,4,8,16 --seconds 60 --burst 12 --overload-queue 3
# staging, once Locust is installed and staging exists (BLOCKED):
locust -f tests/load/locustfile.py --headless --host https://<staging> -u 50 -r 5 -t 10m
```

## 18. Risks / Limitations

- Staging may differ from production. Cost limits how far tests can go.
- The baseline driver shared the laptop's CPU with the API and the model, so the capacity is a lower bound.
- The baseline used one source address, so the per-address limit was lifted for the run. It also used SQLite, not PostgreSQL.
- **The queue limit is soft under bursts.** A limit of 3 accepted 6, because depth is read before the job is enqueued. No job was lost. An atomic check is needed when the Redis queue is used.
- **Status polling counts against the per-user limit** of 120 a minute. One poll got a 429 during the overload phase.
- The first baseline attempt crashed in the overload phase on that 429, because the driver did not handle it. The driver was fixed and the full run repeated; only the repeat is reported.

## 19. Traceability

| Requirement | Implementation | Test | Evidence | Status |
|---|---|---|---|---|
| `REQ-P10-S02-001` | `tests/load/scenarios.py`, `tests/load/locustfile.py` | `tests/load/test_scenarios.py`; staging Locust run `BLOCKED` | `reports/final/p10_s02_load.json` | IN_PROGRESS |
| `REQ-P10-S02-002` | `scripts/evaluation/run_load_baseline.py` | Baseline run 2026-11-05 | `reports/final/p10_s02_load.json` | COMPLETED |
| `REQ-P10-S02-003` | `docs/deployment/SLO.md` | Written after the baseline | SLO document (provisional) | COMPLETED |
| `REQ-P10-S02-004` | `src/api/analyses_v2.py` | Overload run 2026-11-05 | `overload` in the report | COMPLETED |
| `REQ-P10-S02-005` | `deploy/` | Scaling run | Report | BLOCKED |
