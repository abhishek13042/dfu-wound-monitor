# DFU-WoundMonitor: CPU inference service + dashboard (research prototype).
#
# Local build (context = repo root):
#   docker build -f docker/production/Dockerfile -t dfu-woundmonitor .
#   docker build -f docker/production/Dockerfile --target worker -t dfu-woundmonitor-worker .
#   docker run -p 7860:7860 -v "$PWD/models:/home/user/app/models:ro" dfu-woundmonitor
# Hugging Face Space: scripts/deployment/build_hf_space.py copies this file to
# the Space root with the same relative layout (see docs/deployment/HUGGINGFACE.md).
#
# The checkpoint is not baked into the image.  At start-up the entrypoint
# fetches it from DFU_CHECKPOINT_REPO (if set) and keeps it only when its
# SHA-256 matches configs/inference/spec_02_03_inference.json.
#
# The api stage is last, so a build with no --target, which is what a Hugging
# Face Space does, stays the single-process service.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Hugging Face Spaces run the container as uid 1000
RUN useradd --create-home --uid 1000 user
WORKDIR /home/user/app

# CPU-only torch wheels first (much smaller than the default CUDA build); the
# requirements file then finds torch/torchvision already satisfied.
COPY --chown=user requirements.txt ./
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision \
 && pip install -r requirements.txt "huggingface_hub>=0.30"

COPY --chown=user src ./src
COPY --chown=user configs ./configs
COPY --chown=user scripts/deployment ./scripts/deployment
COPY --chown=user docker/production/entrypoint.sh ./entrypoint.sh
RUN mkdir -p models/checkpoints/spec-02-03 && chown -R user:user models

USER user
ENV HOME=/home/user \
    HF_HOME=/home/user/.cache/huggingface \
    DFU_DATA_DIR=/tmp/dfu \
    PORT=7860

FROM base AS worker
ENV DFU_ROLE=worker
# A worker has no port.  Its liveness is the heartbeat the API reads from Redis.
HEALTHCHECK NONE
CMD ["sh", "./entrypoint.sh"]

FROM base AS api
EXPOSE 7860
# readiness, not liveness: the model takes 1-2 minutes to hash and load
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
  CMD python -c "import os,urllib.request;urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health/ready',timeout=4)"

CMD ["sh", "./entrypoint.sh"]
