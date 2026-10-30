"""Copy blobs from local disk to the configured store and verify every hash.

Run from the project root, with ``DFU_STORAGE_BACKEND=s3``, ``DFU_S3_BUCKET`` and
``DFU_S3_ENDPOINT`` set, plus the usual ``AWS_*`` credentials::

    python scripts/deployment/migrate_blobs.py --source runtime/blobs --verify

The source is never changed.  A file whose bytes do not match its name is
reported and not copied.  Exit code 0 means every file arrived intact.  The JSON
report on stdout holds keys and counts only, no credentials.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.api.service import ApiSettings  # noqa: E402
from src.storage.blobs import CONTENT_KEY, BlobStore, LocalBlobStore, create_blob_store  # noqa: E402
from src.storage.database import StorageError  # noqa: E402


def migrate_blobs(source: LocalBlobStore, target: BlobStore, verify: bool = False) -> dict[str, Any]:
    report: dict[str, Any] = {"files": 0, "copied": 0, "already_present": 0, "verified": 0, "failures": []}
    for path in sorted(item for item in source.root.rglob("*") if item.is_file()):
        key = path.relative_to(source.root).as_posix()
        if key.startswith("uploads/"):
            continue  # staged uploads expire and are not part of the record
        report["files"] += 1
        if CONTENT_KEY.match(key) is None:
            report["failures"].append({"key": key, "reason": "NOT_CONTENT_ADDRESSED"})
            continue
        try:
            data = source.get(key)
        except StorageError as error:
            report["failures"].append({"key": key, "reason": error.code})
            continue
        try:
            if target.exists(key):
                report["already_present"] += 1
            else:
                target.write(key, data)
                report["copied"] += 1
            if verify:
                target.get(key)
                report["verified"] += 1
        except StorageError as error:
            report["failures"].append({"key": key, "reason": error.code})
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, default=Path("runtime/blobs"))
    parser.add_argument("--verify", action="store_true", help="read every object back and check its hash")
    args = parser.parse_args()
    settings = ApiSettings()
    target = create_blob_store(settings.storage_backend, settings.data_dir, settings.s3_bucket, settings.s3_endpoint)
    if isinstance(target, LocalBlobStore) and target.root.resolve() == args.source.resolve():
        print("Source and target are the same directory", file=sys.stderr)
        return 2
    report = migrate_blobs(LocalBlobStore(args.source), target, args.verify)
    print(json.dumps(report, indent=2))
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    sys.exit(main())
