# P07-S01 — Public Demo and Continuous Integration

**Status:** `IN_PROGRESS`. CI runs on GitHub Actions, and REQ-001, 002, 003 and 005 are `COMPLETED` (run 42478962863, 2026-11-08). REQ-004 is `BLOCKED`: the weights are public at [abhishek1402/dfu-resnet34-unet](https://huggingface.co/abhishek1402/dfu-resnet34-unet) (2026-11-09), but Hugging Face refused to create the Docker Space (HTTP 402) because Docker Spaces on free CPU now need a PRO subscription.

## 1. Objective

Make the v1.0.0 prototype reachable at a public URL and check every change automatically. This closes the one open release item, REQ-P06-S03-001 (clean-environment install).

## 2. Scope

- GitHub Actions workflow for lint, types, tests and the Docker build
- Clean-environment install check on Linux and Windows
- Upload of the checkpoint to a Hugging Face model repo
- Publication of the Docker Space built by `scripts/deployment/build_hf_space.py`
- Status badges and the demo URL in the README

## 3. Non-Goals

- Multi-user features or accounts
- Any change to the model or its results
- Automatic deployment to the Space on every merge

## 4. Requirements

- `REQ-P07-S01-001`: CI SHALL run ruff, mypy and pytest on every push and pull request to `main`.
- `REQ-P07-S01-002`: A job SHALL install the project from a fresh clone in an empty environment and run the tests, on Linux and Windows. This closes REQ-P06-S03-001.
- `REQ-P07-S01-003`: CI SHALL build the production Docker image and confirm that `/health/live` answers.
- `REQ-P07-S01-004`: The Space SHALL serve the dashboard, report the model READY, and show the medical notice and the external Dice 0.26 limitation.
- `REQ-P07-S01-005`: A checkpoint whose SHA-256 differs from the pinned value SHALL leave the Space NOT_READY, and it SHALL refuse analyses.

## 5. Assumptions

- The repository owner runs `gh auth login` and `hf auth login`; tokens are never stored in the repository.
- The free Hugging Face CPU tier can run the image. A request takes about 5.8 s on a 2-core CPU and may be slower there.

## 6. Dependencies

- `P06-S03`

## 7. Inputs

- `docker/production/`
- `scripts/deployment/build_hf_space.py`
- Checkpoint `resnet34_unet_512_best.pth`
- GitHub secret `HF_TOKEN`, only if a publish workflow is added later

## 8. Outputs

- `.github/workflows/ci.yml`
- A public Space URL
- A model repo that holds the checkpoint
- README badges

## 9. Data / Interface Contract

The CI gate is: `python -m ruff check .`, `python -m mypy src`, `python -m pytest -q`. The Space keeps the `/api/v1` contract and the `DFU_CHECKPOINT_REPO`, `DFU_CHECKPOINT_FILENAME` and `DFU_CHECKPOINT_REVISION` settings.

## 10. Invariants

- CI needs no checkpoint, dataset or GPU.
- The Space accepts uploads that are deleted when it restarts, and it states this.
- No credential is written to the repository or a log.

## 11. Technical Design

CI uses one workflow with three jobs: `quality`, `install` (matrix) and `docker`. pip caching keeps runs short. Publishing stays a manual, documented step, so a release is a deliberate act. The storage on a free Space is temporary, which suits a demo that must not retain data.

## 12. Implementation Tasks

1. Add the CI workflow and fix anything a clean machine exposes. This includes the 36 mypy errors in `src/` counted on 2026-10-30, so that the type check can gate merges.
2. Pin the versions that the install job shows to be required.
3. Create the model repo and upload the checkpoint.
4. Publish the Space and run the smoke test against it.
5. Add the URL and badges to the README.

## 13. Failure Modes / Edge Cases

| Case | Required behaviour |
|---|---|
| A dependency has no wheel for a Python version | Pin the CI Python to 3.12 and record the limit in the development guide |
| The Space runs out of memory | Record the failure and move to paid CPU hardware or fix through P07-S06 |
| The Space sleeps when idle | Show the cold-start delay on the dashboard |

## 14. Tests

- Workflow runs on a test pull request
- Wrong-hash container start
- Remote smoke test

## 15. Acceptance Criteria

- A pull request shows all three jobs passing.
- REQ-P06-S03-001 is PASS in `specs/TRACEABILITY.md`.
- A stranger can open the URL and analyse a sample image.

## 16. Evidence

Recorded on 2026-11-08. [Actions run 42478962863](https://github.com/abhishek13042/dfu-wound-monitor/actions/runs/42478962863) on [PR #1](https://github.com/abhishek13042/dfu-wound-monitor/pull/1), commit `7b1d999`.

- `quality`, `install` (ubuntu and windows) and `docker` passed. The container refuses a checkpoint with the wrong hash.
- Earlier runs on the PR found and fixed two CI faults: OpenCV missing from `requirements.txt`, and a Trivy action tag that no longer resolved, now pinned to a commit.
- 2026-11-09: the checkpoint and model card are public at [abhishek1402/dfu-resnet34-unet](https://huggingface.co/abhishek1402/dfu-resnet34-unet), revision `870ad3b`. Creating `abhishek1402/dfu-woundmonitor` as a Docker Space returned HTTP 402: Hugging Face now requires PRO for Docker and Gradio Spaces on free CPU. `dist/hf_space/` is built (118 files) and ready to push once the Space exists.
- Still missing: the Space smoke test and screenshot (REQ-004, `BLOCKED` on the subscription).
- `reports/final/p07_s01_space_smoke.json`
- Screenshot of the running Space

## 17. Reproducibility

```bash
python scripts/deployment/build_hf_space.py
python scripts/deployment/smoke_test.py --url https://<user>-dfu-woundmonitor.hf.space
```

## 18. Risks / Limitations

- A public upload form attracts unsuitable images. Rate limits arrive in P10-S03, so the Space must say that no identifiable data may be uploaded.
- Publishing is outward-facing and needs the owner's approval.

## 19. Traceability

| Requirement | Implementation | Test | Evidence | Status |
|---|---|---|---|---|
| `REQ-P07-S01-001` | `.github/workflows/ci.yml` | Workflow run on a pull request | Actions run 42478962863 on PR #1 (commit `7b1d999`): `quality` job, ruff, mypy and pytest 518 passed, 9 skipped. The `security` job in the same workflow belongs to REQ-P10-S03-006 | COMPLETED |
| `REQ-P07-S01-002` | `.github/workflows/ci.yml` install job | Matrix job | Actions run 42478962863: `install` on ubuntu-latest (518 passed, 9 skipped) and windows-latest both passed from an empty environment | COMPLETED |
| `REQ-P07-S01-003` | `.github/workflows/ci.yml` docker job | Container start check | Actions run 42478962863: `docker` job built the API and worker images and the container answered liveness | COMPLETED |
| `REQ-P07-S01-004` | Published Space | `smoke_test.py --url <space>` | Model repo published 2026-11-09 (public, revision `870ad3b`, checkpoint 293,565,633 bytes). Creating the Docker Space returned HTTP 402: Docker Spaces on free CPU need a Hugging Face PRO subscription | BLOCKED: Docker Space needs a PRO subscription |
| `REQ-P07-S01-005` | `scripts/deployment/fetch_checkpoint.py`, `scripts/deployment/check_refuses_bad_model.py` | Container test with a wrong hash | Actions run 42478962863: `docker` job, a container and a worker given a checkpoint with the wrong hash both refused it (readiness and analysis 503, CHECKPOINT_CHECKSUM_MISMATCH) | COMPLETED |
