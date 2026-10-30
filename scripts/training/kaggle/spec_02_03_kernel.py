"""Kaggle GPU entry point for SPEC-02-03 (pushed by scripts/training/kaggle/launch_kaggle_spec_02_03.py).

Runs inside a Kaggle kernel with three private datasets attached:
the repository code bundle, FUSeg2021 (train + validation) and
LowerLimbFeetWound V3 (wound_main + wound_mask).

Steps: locate inputs -> copy code to /kaggle/working/repo -> train ->
tune on internal val -> score held-out test once -> LowerLimb external check.
Every output lands in /kaggle/working/spec-02-03.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import zipfile
from collections.abc import Callable
from pathlib import Path

INPUT = Path(os.environ.get("SPEC_KAGGLE_INPUT", "/kaggle/input"))
WORK = Path(os.environ.get("SPEC_KAGGLE_WORKING", "/kaggle/working"))
REPO = WORK / "repo"
OUTPUT = WORK / "spec-02-03"
UNZIP = WORK.parent / "tmp" / "unzipped"
DRY_RUN = os.environ.get("SPEC_KAGGLE_DRY_RUN") == "1"


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def find_dir(predicate: Callable[[Path], bool], roots) -> Path | None:
    for root in roots:
        if not root.exists():
            continue
        for current, _, _ in os.walk(root):
            path = Path(current)
            if predicate(path):
                return path
    return None


def unzip_archives() -> None:
    """Extract any uploaded .zip that Kaggle did not unpack itself."""

    for archive in INPUT.rglob("*.zip"):
        target = UNZIP / archive.stem
        if not target.exists():
            log(f"extracting {archive}")
            with zipfile.ZipFile(archive) as handle:
                handle.extractall(target)


def locate(predicate: Callable[[Path], bool], what: str) -> Path:
    found = find_dir(predicate, [INPUT])
    if found is None:
        unzip_archives()
        found = find_dir(predicate, [UNZIP])
    if found is None:
        raise SystemExit(f"Could not find {what} under /kaggle/input")
    log(f"{what}: {found}")
    return found


def main() -> None:
    code = locate(lambda p: (p / "scripts" / "run_spec_02_03.py").is_file(), "code bundle")
    fuseg = locate(lambda p: (p / "train" / "images").is_dir() and (p / "validation" / "images").is_dir(),
                   "FUSeg2021 root")
    lowerlimb = locate(lambda p: (p / "wound_main").is_dir() and (p / "wound_mask").is_dir(), "LowerLimb V3 root")

    if REPO.exists():
        shutil.rmtree(REPO)
    shutil.copytree(code, REPO)
    OUTPUT.mkdir(parents=True, exist_ok=True)

    try:
        import scipy  # noqa: F401
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "scipy"])

    if shutil.which("nvidia-smi"):
        subprocess.call(["nvidia-smi"])
    command = [
        sys.executable, "scripts/training/run_spec_02_03.py", "--train", "--evaluate", "--external",
        "--data-root", str(fuseg),
        "--external-data-root", str(lowerlimb),
        "--output-root", str(OUTPUT),
        "--num-workers", str(min(4, os.cpu_count() or 2)),
    ]
    log("running: " + " ".join(command))
    if DRY_RUN:
        return
    started = time.time()
    with open(OUTPUT / "kaggle_run_log.txt", "w", encoding="utf-8") as log_file:
        process = subprocess.Popen(command, cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            sys.stdout.write(line)
            log_file.write(line)
            log_file.flush()
        code_ = process.wait()
    log(f"finished with exit code {code_} after {(time.time() - started) / 60:.1f} min")

    # Keep the downloadable output small: the best (EMA) checkpoint is enough for
    # Phase 03; the latest checkpoint only matters for resuming an interrupted run.
    if code_ == 0:
        for latest in (OUTPUT / "checkpoints").glob("*_latest.pth"):
            latest.unlink()
    shutil.rmtree(REPO, ignore_errors=True)
    if code_ != 0:
        raise SystemExit(code_)


if __name__ == "__main__":
    main()
