# Service objectives and capacity

P10-S02. **Provisional.** These objectives were written after the first baseline (REQ-P10-S02-003). That baseline ran on one laptop, not on staging. Re-measure on staging before relying on them, and change this file only from a new report.

Source: `reports/final/p10_s02_load.json`, recorded 2026-11-05.

## What was measured

- **Hardware:** Intel Core, 2 physical and 4 logical cores at 2.9 GHz, 7.7 GB RAM. Windows 11, Python 3.14, PyTorch 2.14 on CPU with 2 threads. No GPU.
- **Setup:** the real API (`uvicorn src.api.app:app`) on SQLite, with the real segmentation model.
  - Jobs ran one at a time on the in-process queue, because Redis and separate workers are not available on this machine.
  - The load driver ran on the same machine and shared the CPU.
- **Load:** step load of 1, 4, 8 and 16 users, 60 s each, then the time each level took to finish its jobs.
- **User mix:** 7 in 10 actions are browsing (cases, one case, its trend, one analysis); 3 in 10 are a full upload and analysis (`tests/load/scenarios.py`).
- **Images:** synthetic only.

| Users | Requests/s | API p50 | API p95 | API p99 | Errors | Analyses done | Analyses/min | Submit-to-result p50 | p95 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 1.45 | 0.012 s | 0.10 s | 0.16 s | 0 % | 7 | 6.9 | 4.1 s | 5.8 s |
| 4 | 4.33 | 0.010 s | 0.06 s | 0.20 s | 0 % | 13 | 9.7 | 16.2 s | 22.2 s |
| 8 | 7.21 | 0.010 s | 0.05 s | 0.22 s | 0 % | 17 | 10.3 | 32.3 s | 39.4 s |
| 16 | 10.93 | 0.010 s | 0.04 s | 0.20 s | 0 % | 22 | 8.4 | 70.8 s | 101.0 s |

API latency counts every request, including the status polls. The slowest route is `POST /uploads/{id}/verify`, which decodes and checks the image: p95 0.52 s at 16 users.

**Overload, queue limit 3, burst of 12 submissions:**
- 6 were accepted (202) and 6 refused (429, `QUEUE_FULL`), each with `Retry-After: 30`.
- There were no timeouts and no other statuses.
- All 6 accepted jobs completed, and none were lost.

## Capacity per worker

- The API is not the bottleneck: its p95 stays under 0.25 s at every level.
- The worker is the bottleneck.
  - It finishes about **10 analyses a minute** on this machine.
  - That figure stops rising from 4 users on: 9.7, 10.3 and then 8.4 per minute as the driver takes more CPU.
  - Above it, submit-to-result time grows with the number of users waiting, not with work done. It is the queue.
- One analysis alone takes about 4 s from submit to result.

**Planning figure:** 8 analyses a minute per worker, which is 80 % of the measured 10. Choose

```text
workers = ceil(peak analyses per minute ÷ 8)
```

and never fewer than 1. On a 2-core machine, one worker per machine: two would share the same cores.

## Objectives

| Objective | Target | Baseline |
|---|---|---|
| API latency, all routes except upload verify | p95 under 0.25 s, p99 under 1 s | p95 ≤ 0.10 s, p99 ≤ 0.22 s |
| Upload verify latency | p95 under 1 s | p95 ≤ 0.52 s |
| Server errors (5xx) | under 0.1 % of requests | 0 of 2,868 |
| Submit to result, while load is within the planning figure | p95 under 30 s | p95 5.8 s at 1 user and 22.2 s at 4 users |
| Overload | every refusal is a 429 with `Retry-After`; no accepted job lost | 6 of 6 refusals; 0 lost |

Submit-to-result has no target above the planning figure, because the time is the queue. The queue limit and the 429 keep that wait bounded: the user is told to come back, and is not left waiting.

## Scaling rule (proposed, not yet shown)

- Add a worker when queue depth stays above 2 × workers for 2 minutes.
- Remove one when depth is 0 for 10 minutes.

This follows the capacity above, but it has not been run: there are no separate workers or Redis on this machine (REQ-P10-S02-005 is `BLOCKED`). Show it on staging before turning it on.

## Findings from the run

- **The queue limit is soft under bursts.** With a limit of 3, the burst got 6 accepted. Depth is read, then the job is enqueued; concurrent submits all see room. Nothing is lost, but the limit can be overshot by about the number of submits arriving at once. Make the check atomic, for example a Redis `INCR` against the limit, when the Redis queue is used.
- **Polling counts against the per-user rate limit.** In the overload phase one status poll got a 429. A client polling every second, with several jobs, can hit 120 requests a minute. The web app should poll less often, or back off on 429.
- The first baseline attempt crashed in the overload phase on that same 429, because the driver did not expect it. The driver was fixed and the whole run repeated. The numbers above are from the repeat.

## Limits of this baseline

- One laptop, with the load driver sharing the CPU. A dedicated worker machine will do better, so this is a lower bound.
- One source address, with the per-address limit lifted for the test.
- SQLite, not PostgreSQL.
- Short steps (60 s). No soak test.
