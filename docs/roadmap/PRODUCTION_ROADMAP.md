# Production platform roadmap (Phase 07, planned)

> Status: **PLANNED**. Nothing in this document is implemented yet. Each step below needs its own
> specification (from `specs/SPEC_TEMPLATE.md`) before implementation, as for Phases 00–06.

Phases 00–06 deliver a working single-machine research prototype: FastAPI service, SQLite + blob store,
static dashboard, Docker image. This roadmap turns it into a public, multi-user **research demo**. It is
still a research prototype: not a medical device, no real patient data.

## Target architecture

```
Browser ──▶ Frontend: Next.js + TypeScript (Vercel)
                 │ HTTPS + auth token
                 ▼
            API: FastAPI (existing service, containerised) ──▶ PostgreSQL (Neon / Supabase)
                 │                                         ──▶ Object storage (Cloudflare R2 / S3)
                 │ job queue (Redis)
                 ▼
            Inference worker(s): ONNX Runtime, autoscaled ◀── model from HF Hub (SHA-256 verified)

Monitoring: Sentry (errors), Prometheus/Grafana (latency), input-drift checks
CI/CD: GitHub Actions → tests → Docker build → deploy
```

Design reasons:

- **Asynchronous inference.** One analysis takes 3–6 s on CPU (`reports/final/p06_benchmark.json`). The API
  queues a job and returns at once; workers scale independently of the API.
- **ONNX Runtime.** Removes PyTorch from the serving image. Speed-up must be measured against the P06 benchmark
  and the exported model must match the PyTorch masks (same Dice on the FUSeg test set).
- **PostgreSQL and object storage.** SQLite and local disk cannot be shared by several API or worker instances.

## Stack

| Layer | Choice |
|---|---|
| Frontend | Next.js, TypeScript, Tailwind, shadcn/ui, Recharts, canvas mask editor |
| Backend | FastAPI (existing), SQLAlchemy, Alembic |
| Queue | Redis + arq (or Celery) |
| Database | PostgreSQL |
| Images | S3-compatible storage, browser upload via pre-signed URLs |
| Auth | Managed provider (Clerk or Supabase Auth); no self-stored passwords |
| Serving | ONNX Runtime |
| DevOps | Docker, GitHub Actions, Sentry |

## Steps

| Step | Work | Exit evidence |
|---|---|---|
| A. Publish | Hugging Face Space live (`docs/deployment/HUGGINGFACE.md`); GitHub Actions running `pytest` | Public URL; green CI run; closes REQ-P06-S03-001 (clean-environment install) |
| B. Backend | PostgreSQL + Alembic, object storage, auth, Redis queue + worker, ONNX export | Migration tests; ONNX parity report; latency before/after |
| C. Frontend | Login, cases, upload, overlay result, examination timeline, sample images | E2E browser test of the main flow |
| D. CV features | Reference-marker (ArUco) mm calibration, confidence heatmap, mask-correction editor | Calibration error on a measured test set; stored corrections |
| E. Production | Rate limiting, Sentry, load test (Locust), automatic deletion of uploads | Load-test report (concurrent users, p95 latency) |
| F. Showcase | README GIF, architecture diagram, demo video | — |

## Rules that stay in force

- "Not a medical device" notice on every page; no diagnostic wording.
- Uploads deleted automatically (e.g. after 24 h); consent before upload; EXIF stripped.
- Per-user rate limits.
- The external-validation limitation (LowerLimb Dice 0.26) stays visible on the model page.
