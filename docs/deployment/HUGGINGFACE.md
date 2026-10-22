# Deploying the demo: Docker and Hugging Face Spaces

The demo is the normal service: the FastAPI API, the `/dashboard/` page, and the pinned SPEC-02-03 model.
It runs in one CPU container. The 293 MB checkpoint is **not** in git and not in the image. At
start-up, `docker/production/entrypoint.sh` runs `scripts/deployment/fetch_checkpoint.py`, which downloads
the checkpoint from a Hugging Face **model repo**. It keeps the file only if its SHA-256 matches
`configs/inference/spec_02_03_inference.json`. Uvicorn then starts on port 7860.
If the fetch fails, the server still starts, and `/health/ready` reports the model as `NOT_READY` with the reason.

| File | Role |
|---|---|
| `docker/production/Dockerfile` | python:3.12-slim, CPU torch wheels, non-root uid 1000, port 7860 |
| `docker/production/entrypoint.sh` | fetch and verify the checkpoint, then `uvicorn src.api.app:app` |
| `docker/production/space_README.md` | Space card (`sdk: docker`, `app_port: 7860`) |
| `scripts/deployment/fetch_checkpoint.py` | hash-gated download (`DFU_CHECKPOINT_REPO`, `_FILENAME`, `_REVISION`, `HF_TOKEN`) |
| `scripts/deployment/build_hf_space.py` | assembles `dist/hf_space/`, about 0.5 MB and 82 files, ready to push |
| `docs/deployment/MODEL_CARD.md` | README for the model repo |

Verified here: the bundle in `dist/hf_space/` was served directly with uvicorn, and
`scripts/deployment/smoke_test.py --url` passed 8/8 checks. The `docker build` itself has
not been run on this machine (Docker is not installed), so the first build on the Space is
the first container build.

## Run locally with Docker

```bash
docker build -f docker/production/Dockerfile -t dfu-woundmonitor .
docker run --rm -p 7860:7860 -v "$PWD/models:/home/user/app/models" dfu-woundmonitor
```

With the checkpoint mounted, the fetch step finds and verifies it, so no download is needed. Open
<http://localhost:7860/>, which redirects to the dashboard.

## Publish to Hugging Face (you do these steps; they need your account)

1. **Log in** once: `pip install -U huggingface_hub`, then `hf auth login` (use a token with write access).
2. **Model repo for the weights.** Create one and upload the checkpoint and the model card:
   ```bash
   hf repo create <user>/dfu-resnet34-unet --repo-type model
   hf upload <user>/dfu-resnet34-unet models/checkpoints/spec-02-03/resnet34_unet_512_best.pth resnet34_unet_512_best.pth
   hf upload <user>/dfu-resnet34-unet docs/deployment/MODEL_CARD.md README.md
   ```
3. **Docker Space.** Create it:
   ```bash
   hf repo create <user>/dfu-woundmonitor --repo-type space --space-sdk docker
   ```
4. **Set Space variables.** In the Space, open *Settings → Variables and secrets* and add:
   - variable `DFU_CHECKPOINT_REPO` = `<user>/dfu-resnet34-unet`;
   - optionally `DFU_CHECKPOINT_REVISION` = a commit hash, to pin the exact upload;
   - the secret `HF_TOKEN`, only if the model repo is private.
5. **Build and push the Space contents:**
   ```bash
   python scripts/deployment/build_hf_space.py
   hf upload <user>/dfu-woundmonitor dist/hf_space . --repo-type space
   ```
   The Space builds the image (about 5–10 minutes, mostly the torch install). It then fetches and hashes
   the checkpoint and loads the model, which takes about 1–2 minutes more. When the Space shows *Running*, check
   `https://<user>-dfu-woundmonitor.hf.space/health/ready`.

To skip the model repo, run `build_hf_space.py --with-checkpoint` instead. This puts the `.pth` inside the Space
as a git-lfs file. The bundled `.gitattributes` already marks `*.pth` for LFS.

## Demo behaviour to know

- **Storage is temporary.** `DFU_DATA_DIR=/tmp/dfu` is wiped whenever the Space restarts or sleeps.
  For persistent records, enable Space persistent storage and set `DFU_DATA_DIR=/data/dfu`.
- **Hardware.** On the free CPU tier, expect one analysis to take tens of seconds, because flip TTA runs two forward passes at 512 px.
  This machine takes about 9 s.
- **Uploads.** The Space is public by default. The card warns users not to upload identifiable patient images. Make the
  Space private if that cannot be guaranteed.
