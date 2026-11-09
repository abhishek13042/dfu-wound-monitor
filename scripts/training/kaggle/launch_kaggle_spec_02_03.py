"""Launch the SPEC-02-03 GPU run on Kaggle and fetch its results.

Needs the Kaggle CLI (``pip install kaggle``) already authenticated: either
``~/.kaggle/kaggle.json`` or the ``KAGGLE_USERNAME``/``KAGGLE_KEY`` (or
``KAGGLE_API_TOKEN``) environment variables. This script never reads or
prints the credentials themselves.

Steps (each one is idempotent and can be run on its own):

1. ``stage``    copy code + data into ``build/kaggle/`` (gitignored).
2. ``upload``   create or version three PRIVATE datasets:
                ``<user>/dfu-wound-monitor-code``, ``<user>/fuseg2021-dfu``
                and ``<user>/lowerlimb-v3-wounds``.
3. ``push``     push the private GPU kernel ``<user>/dfu-spec-02-03``.
4. ``wait``     poll until the kernel finishes.
5. ``download`` save outputs to ``reports/experiments/spec-02-03/kaggle/``.

Typical use (one command, then go to sleep)::

    python scripts/training/kaggle/launch_kaggle_spec_02_03.py --username YOUR_KAGGLE_NAME --all

Re-push after a code change without re-uploading the data::

    python scripts/training/kaggle/launch_kaggle_spec_02_03.py --username NAME --stage --upload --push --wait --download --code-only
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BUILD = PROJECT_ROOT / "build" / "kaggle"
FUSEG_SOURCE = PROJECT_ROOT / "data/raw/FUSeg2021/source/data/Foot Ulcer Segmentation Challenge"
LOWERLIMB_SOURCE = PROJECT_ROOT / "data/raw/LowerLimbFeetWound/V3/extracted"
KERNEL_SOURCE = PROJECT_ROOT / "scripts/training/kaggle/spec_02_03_kernel.py"
RESULTS = PROJECT_ROOT / "reports/experiments/spec-02-03/kaggle"

CODE_SLUG = "dfu-wound-monitor-code"
FUSEG_SLUG = "fuseg2021-dfu"
LOWERLIMB_SLUG = "lowerlimb-v3-wounds"
KERNEL_SLUG = "dfu-spec-02-03"

CODE_ITEMS = [
    "src", "scripts", "configs", "requirements.txt",
    "data/manifests/fuseg2021_heldout_manifest.json",
    "data/manifests/lowerlimb_v3_external_manifest.json",
]


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def kaggle(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    command = [sys.executable, "-m", "kaggle", *args]
    log("kaggle " + " ".join(args))
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    output = (result.stdout + result.stderr).strip()
    if output:
        # Kaggle progress bars use block characters the Windows console code page cannot encode.
        print(output.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8"))
    if check and result.returncode != 0:
        raise SystemExit(f"kaggle command failed ({result.returncode})")
    return result


def _link_or_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def _mirror(source: Path, target: Path, ignore=("__pycache__", ".pyc")) -> None:
    for path in source.rglob("*"):
        if path.is_file() and not any(token in str(path) for token in ignore):
            _link_or_copy(path, target / path.relative_to(source))


def _write_dataset_metadata(folder: Path, username: str, slug: str, title: str) -> None:
    metadata = {"title": title, "id": f"{username}/{slug}", "licenses": [{"name": "other"}]}
    (folder / "dataset-metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def stage(username: str, code_only: bool) -> None:
    code_dir = BUILD / CODE_SLUG
    if code_dir.exists():
        shutil.rmtree(code_dir)  # code is small and must always be fresh
    for item in CODE_ITEMS:
        source = PROJECT_ROOT / item
        if source.is_dir():
            _mirror(source, code_dir / "repo" / item)
        else:
            _link_or_copy(source, code_dir / "repo" / item)
    _write_dataset_metadata(code_dir, username, CODE_SLUG, "DFU wound monitor code")
    log(f"staged code -> {code_dir}")
    if code_only:
        return

    fuseg_dir = BUILD / FUSEG_SLUG
    for split in ("train", "validation"):
        _mirror(FUSEG_SOURCE / split, fuseg_dir / "Foot Ulcer Segmentation Challenge" / split)
    _write_dataset_metadata(fuseg_dir, username, FUSEG_SLUG, "FUSeg2021 DFU train+validation")
    log(f"staged FUSeg2021 -> {fuseg_dir}")

    lowerlimb_dir = BUILD / LOWERLIMB_SLUG
    for folder in ("wound_main", "wound_mask"):
        _mirror(LOWERLIMB_SOURCE / folder, lowerlimb_dir / "extracted" / folder)
    _write_dataset_metadata(lowerlimb_dir, username, LOWERLIMB_SLUG, "LowerLimb Feet Wound V3")
    log(f"staged LowerLimb V3 -> {lowerlimb_dir}")


def _dataset_exists(username: str, slug: str) -> bool:
    return kaggle("datasets", "status", f"{username}/{slug}", check=False).returncode == 0


def _wait_dataset_ready(username: str, slug: str, timeout_s: int = 3600) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        result = kaggle("datasets", "status", f"{username}/{slug}", check=False)
        if "ready" in result.stdout.lower():
            return
        time.sleep(30)
    raise SystemExit(f"dataset {username}/{slug} not ready after {timeout_s}s")


def upload(username: str, code_only: bool) -> None:
    slugs = [CODE_SLUG] if code_only else [CODE_SLUG, FUSEG_SLUG, LOWERLIMB_SLUG]
    for slug in slugs:
        folder = str(BUILD / slug)
        if _dataset_exists(username, slug):
            if slug != CODE_SLUG:
                log(f"{slug} already exists; data is unchanged, skipping upload")
                continue
            kaggle("datasets", "version", "-p", folder, "-m", "code update", "-r", "zip", "-q")
        else:
            kaggle("datasets", "create", "-p", folder, "-r", "zip", "-q")
    for slug in slugs:
        _wait_dataset_ready(username, slug)
    log("datasets ready")


def push(username: str, accelerator: str) -> None:
    kernel_dir = BUILD / KERNEL_SLUG
    kernel_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(KERNEL_SOURCE, kernel_dir / "run_kernel.py")
    metadata = {
        "id": f"{username}/{KERNEL_SLUG}",
        "title": KERNEL_SLUG,
        "code_file": "run_kernel.py",
        "language": "python",
        "kernel_type": "script",
        "is_private": True,
        "enable_gpu": True,
        "enable_internet": True,  # ImageNet ResNet34 weights are downloaded by torchvision
        "dataset_sources": [f"{username}/{slug}" for slug in (CODE_SLUG, FUSEG_SLUG, LOWERLIMB_SLUG)],
        "competition_sources": [],
        "kernel_sources": [],
    }
    (kernel_dir / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    args: list[str] = ["kernels", "push", "-p", str(kernel_dir)]
    if accelerator:
        args += ["--accelerator", accelerator]
    kaggle(*args)


def wait(username: str, poll_s: int = 300, timeout_h: float = 12.5) -> str:
    deadline = time.time() + timeout_h * 3600
    while time.time() < deadline:
        status = kaggle("kernels", "status", f"{username}/{KERNEL_SLUG}", check=False).stdout.lower()
        for final in ("complete", "error", "cancel"):
            if final in status:
                log(f"kernel finished: {final}")
                return final
        time.sleep(poll_s)
    return "timeout"


def download(username: str) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    kaggle("kernels", "output", f"{username}/{KERNEL_SLUG}", "-p", str(RESULTS), "-o")
    log(f"outputs saved to {RESULTS}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--username", default=os.environ.get("KAGGLE_USERNAME"), help="Kaggle account name")
    parser.add_argument("--all", action="store_true", help="stage + upload + push + wait + download")
    for step in ("stage", "upload", "push", "wait", "download"):
        parser.add_argument(f"--{step}", action="store_true")
    parser.add_argument("--code-only", action="store_true", help="Only re-stage/re-upload the code bundle")
    parser.add_argument("--accelerator", default="", help="e.g. NvidiaTeslaT4 or NvidiaTeslaP100; default = Kaggle GPU")
    args = parser.parse_args()
    if not args.username:
        parser.error("--username (or KAGGLE_USERNAME) is required")
    steps = {s for s in ("stage", "upload", "push", "wait", "download") if args.all or getattr(args, s)}
    if not steps:
        parser.error("choose --all or at least one step")

    if "stage" in steps:
        stage(args.username, args.code_only)
    if "upload" in steps:
        upload(args.username, args.code_only)
    if "push" in steps:
        push(args.username, args.accelerator)
    outcome = wait(args.username) if "wait" in steps else None
    if "download" in steps:
        download(args.username)
    if outcome and outcome != "complete":
        raise SystemExit(f"kernel ended with status '{outcome}'; see {RESULTS}/kaggle_run_log.txt or the Kaggle log")


if __name__ == "__main__":
    main()
