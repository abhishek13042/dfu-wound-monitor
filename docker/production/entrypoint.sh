#!/bin/sh
# Fetch + verify the checkpoint, then serve.  A failed fetch does not stop the
# server: /health/ready then reports the model as NOT_READY with the reason.
# A worker with no verified model exits instead, because it must take no jobs.
# With DFU_REDIS_URL set the API holds no model, so it fetches none.
set -u
mkdir -p "${DFU_DATA_DIR:-/tmp/dfu}"
if [ "${DFU_ROLE:-api}" = "worker" ]; then
    python scripts/deployment/fetch_checkpoint.py || echo "[entrypoint] no verified checkpoint fetched"
    exec python -m arq src.worker.settings.WorkerSettings
fi
if [ -z "${DFU_REDIS_URL:-}" ]; then
    python scripts/deployment/fetch_checkpoint.py || echo "[entrypoint] continuing without a verified checkpoint"
fi
if [ -n "${DFU_DATABASE_URL:-}" ]; then
    python scripts/deployment/migrate_db.py || echo "[entrypoint] migration failed; /health/ready will report it"
fi
exec python -m uvicorn src.api.app:app --host 0.0.0.0 --port "${PORT:-7860}" --proxy-headers --forwarded-allow-ips="*"
