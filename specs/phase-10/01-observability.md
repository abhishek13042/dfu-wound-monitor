# P10-S01 — Observability

**Status:** `IN_PROGRESS`. Request IDs, scrubbed JSON logs, `dfu_` metrics, alert rules, a dashboard and the runbook are built, and 29 local tests pass. The `observability` CI job passes (run 42478962863, 2026-11-08). Sentry and Grafana Cloud are `BLOCKED` on accounts the deployer owns, and frontend Sentry is not wired.

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

- 2026-11-04: `tests/worker/test_p10_s01_observability.py` (23 tests) and `tests/integration/test_p10_s01_alerts.py` (6 tests): 29 passed. They show:
  - an `X-Request-ID` supplied by the caller is kept, and a malformed one is replaced
  - the error body's `request_id` matches the header
  - the ID is stored in the job request, appears on the worker's `job started` and `job finished` log lines, and appears in the result provenance
  - planted Bearer tokens, JWTs, signed-URL parameters, filenames, `data:` URLs, base64 runs and raw byte reprs are removed from messages, arguments and tracebacks
  - an injected `MODEL_FAILURE` adds 1 to `dfu_errors_total{failure_class="MODEL",source="worker"}`, and its log lines lead to exactly one `analysis_id`
  - a quality rejection adds to `dfu_analyses_total{outcome="QUALITY_REJECTED"}` and not to `dfu_errors_total`
  - `/metrics` returns 404 to a public client and 200 to a private one or to the bearer token
  - the queue being down, or a metric that raises, does not fail a request
- Worker, API and integration suites after the change: 173 passed.
- Dashboard export: `docker/production/observability/grafana-dashboard.json`.
- Fault-injection record for alerts: `docker/production/observability/alerts_test.yml`, a `promtool` test in which each alert fires on an injected fault and stays quiet otherwise.
- Recorded on 2026-11-08. [Actions run 42478962863](https://github.com/abhishek13042/dfu-wound-monitor/actions/runs/42478962863) on [PR #1](https://github.com/abhishek13042/dfu-wound-monitor/pull/1), commit `7b1d999`. The `observability` job ran `promtool test rules`: SUCCESS.

## 17. Reproducibility

```bash
python -m pytest tests/worker/test_p10_s01_observability.py tests/integration/test_p10_s01_alerts.py -q
# with Docker:
docker run --rm -v "$PWD/docker/production/observability:/rules" -w /rules --entrypoint promtool prom/prometheus:v2.53.0 test rules alerts_test.yml
```

Runtime switches:
- `DFU_LOG_FORMAT=plain` and `DFU_LOG_LEVEL` control the logs.
- `DFU_METRICS_TOKEN` lets a scraper outside the private network read `/metrics`.
- `DFU_WORKER_METRICS_PORT` and `DFU_WORKER_METRICS_ADDR` set where the worker serves its metrics.
- `SENTRY_DSN` turns on error reporting, only when `sentry_sdk` is installed.

Runbook: `docs/runbooks/observability.md`.

## 18. Risks / Limitations

- Filenames can contain personal data, which is why they are scrubbed.
- Scrubbing works on patterns. A secret in a shape it does not know, such as a token without a `Bearer` prefix or key name, would pass through. To limit this, the code never logs request bodies or headers.
- `BLOCKED`: Sentry (API, worker and frontend) and a hosted Grafana need accounts the deployer owns. The API and worker hook is in place but inactive until `SENTRY_DSN` is set. The frontend has no Sentry wiring.
- The worker serves its metrics on its own port only when one is configured. Without that port, its job metrics are seen only by an in-process API (`LocalQueue`).

## 19. Traceability

| Requirement | Implementation | Test | Evidence | Status |
|---|---|---|---|---|
| `REQ-P10-S01-001` | `src/observability/context.py`, `src/observability/http.py`, `src/api/errors.py`, `src/api/analyses_v2.py`, `src/worker/tasks.py` | `test_the_id_follows_the_job_into_the_worker_and_the_result`, `test_error_body_names_the_same_id_as_the_header` | Test run 2026-11-04 | COMPLETED |
| `REQ-P10-S01-002` | `src/observability/metrics.py`, `/metrics` in `src/api/app.py` | `test_metrics_endpoint_reports_the_required_series`, `test_quality_rejection_is_an_outcome_not_an_error` | `grafana-dashboard.json`, test run | COMPLETED |
| `REQ-P10-S01-003` | `src/observability/logs.py`, `src/observability/errors.py` | `test_scrub_removes_planted_secrets`, `test_error_events_are_scrubbed_before_sending` | Test run 2026-11-04 | COMPLETED |
| `REQ-P10-S01-004` | `docker/production/observability/alerts.yml` | `alerts_test.yml` (promtool, CI), `test_every_alert_has_a_firing_promtool_case` | Actions run 42478962863: `observability` job, `promtool test rules` SUCCESS (4 rules) | COMPLETED |
