# P10-S02 — Load Testing and Service Objectives

**Status:** `NOT_STARTED`. Nothing in this specification is implemented. It needs approval before work begins.

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

## 17. Reproducibility

Planned commands. These do not work until the specification is implemented.

```bash
locust -f tests/load/locustfile.py --headless --host https://<staging> -u 50 -r 5 -t 10m
```

## 18. Risks / Limitations

- Staging may differ from production. Cost limits how far tests can go.

## 19. Traceability

| Requirement | Planned implementation | Planned test | Planned evidence | Status |
|---|---|---|---|---|
| `REQ-P10-S02-001` | `tests/load/locustfile.py` | Load run | `reports/final/p10_s02_load.json` | NOT_STARTED |
| `REQ-P10-S02-002` | `scripts/evaluation/` | Load run | `reports/final/p10_s02_load.json` | NOT_STARTED |
| `REQ-P10-S02-003` | `docs/deployment/SLO.md` | Document review | SLO document | NOT_STARTED |
| `REQ-P10-S02-004` | `src/api/analyses_v2.py` | Overload run | Report | NOT_STARTED |
| `REQ-P10-S02-005` | `deploy/` | Scaling run | Report | NOT_STARTED |
