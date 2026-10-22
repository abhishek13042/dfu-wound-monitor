"""Assemble a ready-to-push Hugging Face Docker Space in ``dist/hf_space``.

A Docker Space needs the ``Dockerfile`` and a ``README.md`` with ``sdk: docker``
front-matter at its root.  This copies only what the container needs, using the
same relative layout as the repo so ``docker/production/Dockerfile`` works
unchanged in both places.

    python scripts/deployment/build_hf_space.py                 # checkpoint fetched at start-up
    python scripts/deployment/build_hf_space.py --with-checkpoint   # also copy the .pth (pushed via git-lfs)

Nothing is uploaded; pushing is done by you (see docs/deployment/HUGGINGFACE.md).
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.deployment.fetch_checkpoint import sha256_of  # noqa: E402
from src.inference.engine import DEFAULT_INFERENCE_CONFIG, InferenceConfig  # noqa: E402

COPY_TREES = ["src", "configs", "scripts/deployment"]
COPY_FILES = ["requirements.txt", "docker/production/entrypoint.sh", "docker/production/Dockerfile"]
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pth", "*.pt")
GITATTRIBUTES = "*.pth filter=lfs diff=lfs merge=lfs -text\n*.sh text eol=lf\n"


def build(output: Path, with_checkpoint: bool = False) -> Path:
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    for tree in COPY_TREES:
        shutil.copytree(PROJECT_ROOT / tree, output / tree, ignore=IGNORE)
    for name in COPY_FILES:
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        data = (PROJECT_ROOT / name).read_bytes()
        if name.endswith(".sh"):
            data = data.replace(b"\r\n", b"\n")  # sh in the container rejects CRLF
        destination.write_bytes(data)
    shutil.copyfile(output / "docker/production/Dockerfile", output / "Dockerfile")
    shutil.copyfile(PROJECT_ROOT / "docker/production/space_README.md", output / "README.md")
    (output / ".gitattributes").write_text(GITATTRIBUTES, encoding="utf-8", newline="\n")

    if with_checkpoint:
        config = InferenceConfig.load(DEFAULT_INFERENCE_CONFIG)
        source = config.checkpoint_path
        if not source.is_file() or sha256_of(source) != config.checkpoint_sha256:
            raise SystemExit(f"checkpoint missing or hash mismatch: {source}")
        destination = output / source.relative_to(PROJECT_ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    return output


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "dist" / "hf_space")
    parser.add_argument("--with-checkpoint", action="store_true")
    args = parser.parse_args(argv)
    output = build(args.output, args.with_checkpoint)
    files = sum(1 for path in output.rglob("*") if path.is_file())
    print(f"Space assembled in {output} ({files} files). Next steps: docs/deployment/HUGGINGFACE.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
