# Containerization & Deployment

- `production/Dockerfile`: CPU inference service and dashboard (python:3.12-slim, CPU torch, uid 1000, port 7860). The default target is `api`; `--target worker` builds the queue worker from the same base.
- `production/entrypoint.sh`: fetches and hash-verifies the checkpoint, then starts uvicorn, or arq when `DFU_ROLE=worker`.
- `production/space_README.md`: the Hugging Face Docker Space card.

Build: `docker build -f docker/production/Dockerfile -t dfu-woundmonitor .` (context = repo root).
Publishing guide: `docs/deployment/HUGGINGFACE.md`.
