"""Place the pinned SPEC-02-03 checkpoint where the inference config expects it.

The 293 MB checkpoint is not in git.  In a container it is fetched at start-up
from a Hugging Face model repository (or copied from a local file) and is only
kept if its SHA-256 matches the value pinned in the inference config.  The
service itself re-verifies the hash when it loads the model, so a bad file can
never be served; this script exists so a container can obtain the file at all.

Environment (all optional):
    DFU_CHECKPOINT_REPO      Hugging Face model repo id, e.g. ``user/dfu-resnet34-unet``
    DFU_CHECKPOINT_FILENAME  file inside that repo (default: the config's file name)
    DFU_CHECKPOINT_REVISION  branch, tag or commit to pin (default: ``main``)
    HF_TOKEN                 only needed for a private repo (set it as a Space secret)

Exit codes: 0 checkpoint present and verified, 1 not available, 2 hash mismatch.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.inference.engine import DEFAULT_INFERENCE_CONFIG, InferenceConfig  # noqa: E402


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _install(candidate: Path, target: Path, expected: str) -> int:
    actual = sha256_of(candidate)
    if actual != expected:
        print(f"[fetch_checkpoint] SHA-256 mismatch: expected {expected}, got {actual}", file=sys.stderr)
        return 2
    target.parent.mkdir(parents=True, exist_ok=True)
    if candidate.resolve() != target.resolve():
        partial = target.with_suffix(target.suffix + ".partial")
        shutil.copyfile(candidate, partial)
        os.replace(partial, target)
    print(f"[fetch_checkpoint] verified {target} ({expected[:12]}...)")
    return 0


def _download(repo_id: str, filename: str, revision: str) -> Path:
    from huggingface_hub import hf_hub_download

    cache_dir = Path(tempfile.gettempdir()) / "dfu_checkpoint_download"
    return Path(hf_hub_download(repo_id=repo_id, filename=filename, revision=revision, cache_dir=cache_dir,
                                token=os.environ.get("HF_TOKEN") or None))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_INFERENCE_CONFIG)
    parser.add_argument("--source", type=Path, help="copy from this local file instead of downloading")
    parser.add_argument("--repo", default=os.environ.get("DFU_CHECKPOINT_REPO"))
    parser.add_argument("--filename", default=os.environ.get("DFU_CHECKPOINT_FILENAME"))
    parser.add_argument("--revision", default=os.environ.get("DFU_CHECKPOINT_REVISION", "main"))
    args = parser.parse_args(argv)

    config = InferenceConfig.load(args.config)
    target, expected = config.checkpoint_path, config.checkpoint_sha256

    if target.is_file() and sha256_of(target) == expected:
        print(f"[fetch_checkpoint] already present and verified: {target}")
        return 0
    if args.source:
        return _install(args.source, target, expected)
    if not args.repo:
        print("[fetch_checkpoint] checkpoint missing and DFU_CHECKPOINT_REPO is not set; "
              "the service will start with the model NOT_READY", file=sys.stderr)
        return 1
    try:
        downloaded = _download(args.repo, args.filename or target.name, args.revision)
    except Exception as error:  # network, auth or missing-file errors all mean "not available"
        print(f"[fetch_checkpoint] download from {args.repo} failed: {error}", file=sys.stderr)
        return 1
    return _install(downloaded, target, expected)


if __name__ == "__main__":
    sys.exit(main())
