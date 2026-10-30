# P07-S05 — Asynchronous Inference Queue and Workers

**Status:** `IN_PROGRESS`. Code, tests and the real-model parity report are done. The CI Redis job and the worker Docker image have not run, because they need a push and Docker.

## 1. Objective

Run analyses in separate workers, so that API requests return at once and inference scales on its own.

## 2. Scope

- Redis queue with arq
- Worker process that runs the existing pipeline
- `/api/v2/analyses` job lifecycle
- Retries, timeouts and dead-letter handling
- Sequential worker concurrency per process

## 3. Non-Goals

- GPU workers
- Autoscaling rules, which depend on P10-S02
- Batch upload

## 4. Requirements

- `REQ-P07-S05-001`: `POST /api/v2/analyses` SHALL return 202 with an `analysis_id` within 500 ms at normal load, without running the model.
- `REQ-P07-S05-002`: Analyses SHALL move through `QUEUED`, `RUNNING`, then `COMPLETED`, `QUALITY_REJECTED` or `FAILED`. Other transitions SHALL be refused.
- `REQ-P07-S05-003`: A job SHALL be idempotent: a redelivered job SHALL NOT produce a second result.
- `REQ-P07-S05-004`: Infrastructure failures SHALL retry with back-off up to three times. Quality rejections and model errors on an input SHALL NOT retry.
- `REQ-P07-S05-005`: Worker results SHALL match the synchronous pipeline for the same image and model.
- `REQ-P07-S05-006`: Readiness SHALL cover the queue, and `GET /api/v1/model` SHALL still report the served model version.

## 5. Assumptions

- arq is chosen over Celery because it is small and needs only Redis. The job body is plain Python, so a later change stays cheap.
- A managed Redis service is available.

## 6. Dependencies

- `P07-S02`
- `P07-S03`

## 7. Inputs

- Verified `upload_id` from P07-S03
- `DFU_REDIS_URL`

## 8. Outputs

- `src/worker/`
- Worker Docker target
- `/api/v2/analyses` routes

## 9. Data / Interface Contract

`POST /api/v2/analyses` takes `{upload_id, examination_id?, pixels_per_mm?, calibration_method?, calibration_source?}` and returns 202 `{analysis_id, status}`. `GET /api/v2/analyses/{id}` returns the status, and the result once finished. The error body from `/api/v1` is reused.

## 10. Invariants

- The quality gate runs before the model.
- The model SHA-256 is verified before a worker takes jobs.
- A stored result records the model version that produced it.

## 11. Technical Design

The API writes a `QUEUED` row, then enqueues the ID. A worker claims the row with a conditional update, which gives idempotency. Each worker holds one model in memory and handles one job at a time. A sweeper marks jobs stuck in `RUNNING` past a timeout as failed.

As built:

- A `FAILED` row with `error_json` is the dead-letter record.
- The sweeper re-queues a lost job once, then fails it with `WORKER_LOST`. It also re-sends `QUEUED` jobs whose message was lost.
- With `DFU_REDIS_URL` set, the API holds no model, so `POST /api/v1/analyses` answers 503.
- With the local blob backend, the API and worker must share a disk.

## 12. Implementation Tasks

1. Add the worker package around `AnalysisPipeline`.
2. Add the state machine and claim step.
3. Add v2 routes.
4. Add retry, timeout and the sweeper.
5. Add the worker image target.

## 13. Failure Modes / Edge Cases

| Case | Required behaviour |
|---|---|
| Worker dies mid-job | The sweeper re-queues the job, once |
| Redis down at submit | `INFRASTRUCTURE_FAILURE` 503; no orphan row |
| Queue too long | Submit returns 429 with a retry hint |
| Model not loaded | The worker takes no jobs and readiness reports it |

## 14. Tests

- State machine
- Redelivery
- Worker killed mid-job
- Parity with the synchronous path
- Integration test with real Redis, locally and in CI (the CI job has not run yet)

## 15. Acceptance Criteria

- With two workers, a burst of jobs all finish with no duplicates or losses.
- Results match the synchronous path exactly on the fixture model.

## 16. Evidence

- Integration test log
- Parity report

## 17. Reproducibility

```bash
python -m arq src.worker.settings.WorkerSettings
python -m pytest tests/worker -q
```

## 18. Risks / Limitations

- Model memory limits the workers per machine.
- Polling adds load; P08-S02 uses a modest interval.
- On Windows, `Worker.close()` needs `SIGUSR1`, which does not exist. A real worker needs Linux, macOS or Docker.
- The parity report skips the 10 minute sweep wait by back-dating the row. The kill itself is real.

## 19. Traceability

| Requirement | Implementation | Test | Evidence | Status |
|---|---|---|---|---|
| `REQ-P07-S05-001` | `src/api/analyses_v2.py` | `test_submit_does_not_run_model` | Test run, with the queue stubbed. Real Redis submits are covered by `tests/worker/test_redis.py` | COMPLETED |
| `REQ-P07-S05-002` | `src/worker/state.py` | `test_state_machine`, `test_a_job_only_moves_from_the_state_it_is_in` | Test run | COMPLETED |
| `REQ-P07-S05-003` | `src/worker/tasks.py` | `test_redelivery_is_idempotent`, `test_only_one_worker_can_claim_a_job`, `test_two_workers_finish_a_burst_with_no_duplicates_or_losses` | Test run | COMPLETED |
| `REQ-P07-S05-004` | `src/worker/tasks.py` | `test_retry_policy`, `test_input_and_model_errors_do_not_retry`, `test_a_retry_is_delivered_after_its_back_off` | Test run | COMPLETED |
| `REQ-P07-S05-005` | `src/worker/tasks.py` | `test_worker_matches_pipeline` | `reports/deployment/p07_s05_parity_report.json`: 5 real images, identical results and mask hashes | COMPLETED |
| `REQ-P07-S05-006` | `src/api/app.py` | `test_readiness_covers_the_queue`, `test_model_route_works_without_a_model_in_the_api` | Test run | COMPLETED |
