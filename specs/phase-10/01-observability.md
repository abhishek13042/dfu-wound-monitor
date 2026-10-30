# P10-S01 — Observability

**Status:** `NOT_STARTED`. Nothing in this specification is implemented. It needs approval before work begins.

## 1. Objective

Make failures and slowdowns visible without logging user images or personal data.

## 2. Scope

- Structured JSON logs with request and job IDs
- Sentry for API, worker and frontend
- Prometheus metrics and Grafana dashboards
- Alert rules

## 3. Non-Goals

- Drift analysis, which belongs to P10-S04
- Paid on-call tooling

## 4. Requirements

- `REQ-P10-S01-001`: Every request and job SHALL carry one ID through API, queue and worker logs, and error bodies SHALL fill `request_id`.
- `REQ-P10-S01-002`: Metrics SHALL cover request rate, errors by failure class, latency, queue depth, job duration and quality-rejection rate.
- `REQ-P10-S01-003`: Logs and error reports SHALL NOT contain images, tokens, or filenames supplied by users.
- `REQ-P10-S01-004`: Alerts SHALL fire on sustained error rate, queue backlog and model-not-ready.

## 5. Assumptions

- The free tiers of Sentry and Grafana Cloud are enough for demo traffic.

## 6. Dependencies

- `P07-S05`

## 7. Inputs

- API and worker processes

## 8. Outputs

- Metrics endpoint
- Dashboards
- Alert rules

## 9. Data / Interface Contract

`/metrics` is private to the deployment network. Metric names use the prefix `dfu_`.

## 10. Invariants

- Telemetry failure never fails a user request.
- Quality rejections are not counted as errors.

## 11. Technical Design

Middleware sets a context ID, which passes in job metadata. Metric labels stay low-cardinality, so user and case IDs are never labels.

## 12. Implementation Tasks

1. Add structured logging.
2. Add metrics.
3. Connect Sentry.
4. Build dashboards.
5. Define alerts and inject faults.

## 13. Failure Modes / Edge Cases

| Case | Required behaviour |
|---|---|
| Sentry unavailable | Events are dropped and the service carries on |
| Metric store down | The service is unaffected |

## 14. Tests

- ID propagation
- Scrubbing with planted secrets
- Fault injection

## 15. Acceptance Criteria

- An injected fault appears as an alert, then traces to one job from its ID.

## 16. Evidence

- Dashboard export
- Fault-injection record

## 17. Reproducibility

Planned commands. These do not work until the specification is implemented.

```bash
python -m pytest tests/observability -q
```

## 18. Risks / Limitations

- Filenames can contain personal data, which is why they are scrubbed.

## 19. Traceability

| Requirement | Planned implementation | Planned test | Planned evidence | Status |
|---|---|---|---|---|
| `REQ-P10-S01-001` | `src/api/middleware.py` | `test_request_id_propagates` | Test run | NOT_STARTED |
| `REQ-P10-S01-002` | `src/observability/metrics.py` | `test_metrics_exposed` | Dashboard export | NOT_STARTED |
| `REQ-P10-S01-003` | `src/observability/scrub.py` | `test_log_scrubbing` | Test run | NOT_STARTED |
| `REQ-P10-S01-004` | `deploy/monitoring/alerts.yml` | Injected-fault test | Alert record | NOT_STARTED |
