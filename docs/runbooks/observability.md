# Observability runbook (P10-S01)

Every request gets one ID. It is in the `X-Request-ID` response header, in the
`request_id` field of every error body, in the job's stored request, and in each
API and worker log line. To follow one analysis, search the logs for that ID.

Logs are JSON on stderr (`DFU_LOG_FORMAT=plain` gives text for a terminal).
They never contain image bytes, tokens, signed URLs or the user's filename;
`src/observability/logs.py:scrub` removes them from the final text of each line.

Metrics (prefix `dfu_`) are served at `/metrics` on the API. The endpoint is
private: a private or loopback client only, or, when `DFU_METRICS_TOKEN` is set,
a scraper that sends `Authorization: Bearer <token>`. The worker serves the same
metrics on `DFU_WORKER_METRICS_PORT` (bound to `DFU_WORKER_METRICS_ADDR`,
default 127.0.0.1) when that is set.

Alert rules: `docker/production/observability/alerts.yml`, tested by
`alerts_test.yml`. Dashboard: `docker/production/observability/grafana-dashboard.json`.

## High error rate

`DfuHighErrorRate`: more than 5% of API requests failed with a MODEL, PERSISTENCE
or SERVICE failure for 10 minutes. INPUT errors (the caller's) and quality
rejections are not counted.

1. Break `dfu_errors_total` down by `failure_class` and `category`.
2. Take a `request_id` from a failing response or log line and follow it.
3. PERSISTENCE: check the database and object storage. MODEL: check `/health/ready`
   and the checkpoint hash. SERVICE: read the exception in the logs.

## Job failures

`DfuJobFailures`: more than 20% of finished jobs FAILED for 15 minutes. Look at
`dfu_errors_total{source="worker"}` and the worker's `job started` / `job finished`
log lines; each carries `analysis_id` and the original `request_id`.

## Queue backlog

`DfuQueueBacklog`: more than 20 jobs waited for 10 minutes. Check the worker is
running (`dfu_model_ready`, the worker heartbeat), then `dfu_job_duration_seconds`
for slow jobs. Add a worker if the load is real.

## Model not ready

`DfuModelNotReady`: no verified model for 5 minutes. The worker refuses to start
without one. Check its log for the checksum error and the model files on disk.
