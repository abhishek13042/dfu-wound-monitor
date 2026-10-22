#!/bin/sh
# Fetch + verify the checkpoint, then serve.  A failed fetch does not stop the
# server: /health/ready then reports the model as NOT_READY with the reason.
set -u
python scripts/deployment/fetch_checkpoint.py || echo "[entrypoint] continuing without a verified checkpoint"
mkdir -p "${DFU_DATA_DIR:-/tmp/dfu}"
exec python -m uvicorn src.api.app:app --host 0.0.0.0 --port "${PORT:-7860}" --proxy-headers --forwarded-allow-ips="*"
