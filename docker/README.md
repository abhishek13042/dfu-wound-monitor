# Containerization & Deployment

- `production/Dockerfile`: CPU inference service and dashboard (python:3.12-slim, CPU torch, uid 1000, port 7860).
- `production/entrypoint.sh`: fetches and hash-verifies the checkpoint, then starts uvicorn.
- `production/space_README.md`: the Hugging Face Docker Space card.
- `development/`: not used yet. Local development runs uvicorn directly (see the root README).

Build: `docker build -f docker/production/Dockerfile -t dfu-woundmonitor .` (context = repo root).
Publishing guide: `docs/deployment/HUGGINGFACE.md`.
